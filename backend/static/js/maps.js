/* ============================================================
 * Canteen Express - Unified Map Engine (maps.js)
 *
 * A thin engine-agnostic facade so every page talks to one small
 * API. Uses Google Maps JS when the API script is loaded (a key is
 * configured in backend/.env), otherwise falls back to Leaflet +
 * free OpenStreetMap tiles (offline/dev mode).
 *
 * Templates must set window.CE_MAP_ENGINE ('google' or 'leaflet')
 * BEFORE this file loads, and load the Google Maps bootstrap with
 * `&callback=ceGoogleMapsReady` when using Google.
 *
 * Exposed namespace: window.Maps
 * ============================================================ */
(function (global) {
    'use strict';

    /* Pending inits queue while the Google bootstrap finishes loading. */
    var pending = [];

    function usingGoogle() {
        return global.CE_MAP_ENGINE === 'google';
    }
    function engineReady() {
        if (usingGoogle()) {
            return typeof global.google !== 'undefined' && global.google.maps;
        }
        return typeof global.L !== 'undefined';
    }

    /* ---------- shared helpers ---------- */
    function toGLatLng(ll) {
        return { lat: ll[0], lng: ll[1] };
    }
    function getLength(arr) { return arr ? arr.length : 0; }

    /* Dark theme map styling (Google style array). Mirrors the app's
     * dark glassmorphism look; Leaflet achieves it via CSS invert. */
    var DARK_STYLES = [
        { elementType: 'geometry', stylers: [{ color: '#141419' }] },
        { elementType: 'labels.text.stroke', stylers: [{ color: '#1d1d24' }] },
        { elementType: 'labels.text.fill', stylers: [{ color: '#8a8a93' }] },
        { featureType: 'administrative', elementType: 'geometry', stylers: [{ color: '#232329' }, { weight: 1.2 }] },
        { featureType: 'poi.park', elementType: 'geometry', stylers: [{ color: '#1a2318' }] },
        { featureType: 'road', elementType: 'geometry', stylers: [{ color: '#26262d' }] },
        { featureType: 'road', elementType: 'geometry.stroke', stylers: [{ color: '#32323a' }] },
        { featureType: 'road.highway', elementType: 'geometry', stylers: [{ color: '#383840' }] },
        { featureType: 'water', elementType: 'geometry', stylers: [{ color: '#0e131e' }] },
        { featureType: 'transit', elementType: 'geometry', stylers: [{ color: '#232329' }] }
    ];

    function googleMapOptions(opts) {
        var opt = {
            center: opts.center ? toGLatLng(opts.center) : { lat: 14.5995, lng: 120.9842 },
            zoom: opts.zoom || 15,
            disableDefaultUI: false,
            gestureHandling: 'greedy',
            backgroundColor: '#121218',
            mapTypeControl: false,
            streetViewControl: false,
            fullscreenControl: false,
            zoomControlOptions: { position: global.google.maps.ControlPosition.BOTTOM_RIGHT },
            styles: DARK_STYLES
        };
        if (opts.minZoom != null) opt.minZoom = opts.minZoom;
        if (opts.maxZoom != null) opt.maxZoom = opts.maxZoom;
        return opt;
    }

    function getFieldPos(field) {
        var p = field.position;
        return typeof p.lat === 'function' ? { lat: p.lat(), lng: p.lng() } : { lat: p.lat, lng: p.lng };
    }

    function fallbackGoogleIcon() {
        return {
            url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(
                '<svg xmlns="http://www.w3.org/2000/svg" width="36" height="44">' +
                '<path d="M18 0 C8 0 2 8 2 16 C2 26 18 44 18 44 C18 44 34 26 34 16 C34 8 28 0 18 0 Z"' +
                ' fill="#FF6117" stroke="#fff" stroke-width="1.5"/></svg>'
            ),
            anchor: new global.google.maps.Point(18, 44)
        };
    }

    /* ============ Google implementation ============ */
    function createGoogleMap(el, opts) {
        var map = new global.google.maps.Map(el, googleMapOptions(opts));
        return macGoogle(map);
    }

    function makeGoogleOverlay(map, latlng, html) {
        var node = document.createElement('div');
        node.innerHTML = html || '';
        var content = node.firstChild || node;
        content.style.transform = 'translate(-50%, -50%)';
        var field;
        if (typeof global.google.maps.marker !== 'undefined' &&
                global.google.maps.marker.AdvancedMarkerElement) {
            field = new global.google.maps.marker.AdvancedMarkerElement({
                map: map,
                position: toGLatLng(latlng),
                content: content
            });
        } else {
            field = new global.google.maps.Marker({
                map: map,
                position: toGLatLng(latlng),
                icon: fallbackGoogleIcon()
            });
        }
        var wrap = {
            _field: field,
            _google: field,
            setLatLng: function (ll) { field.position = toGLatLng(ll); },
            getLatLng: function () {
                var p = getFieldPos(field);
                return [p.lat, p.lng];
            },
            remove: function () { field.map = null; },
            bindPopup: function (text) {
                var info = new global.google.maps.InfoWindow({ content: text });
                field.addListener('click', function () {
                    info.setPosition(getFieldPos(field));
                    info.open({ map: map });
                });
                return { openPopup: function () {
                    info.setPosition(getFieldPos(field));
                    info.open({ map: map });
                } };
            },
            on: function (evt, cb) {
                var gEvt = evt === 'dragend' ? 'dragend' : evt;
                field.addListener(gEvt, function (e) {
                    if (evt === 'click') {
                        cb({ latlng: getFieldPos(field) });
                    } else {
                        cb(e);
                    }
                });
            }
        };
        return wrap;
    }

    function macGoogle(map) {
        var layers = [];
        return {
            _engine: 'google',
            _map: map,
            fitTo: function (pts, padding) {
                if (!Array.isArray(pts) || pts.length === 0) return;
                var bounds = new global.google.maps.LatLngBounds();
                pts.forEach(function (p) { bounds.extend(toGLatLng(p)); });
                map.fitBounds(bounds, typeof padding === 'object' && padding ? padding : {});
            },
            setView: function (ll, zoom) {
                map.setCenter(toGLatLng(ll));
                if (zoom != null) map.setZoom(zoom);
            },
            invalidateSize: function () {
                global.google.maps.event.trigger(map, 'resize');
                if (map.getCenter) map.setCenter(map.getCenter());
            },
            onClick: function (cb) {
                map.addListener('click', function (e) {
                    cb({ latlng: { lat: e.latLng.lat(), lng: e.latLng.lng() } });
                });
            },
            addMarker: function (latlng, html, draggable) {
                var m = makeGoogleOverlay(map, latlng, html || '');
                if (draggable && m._field.setDraggable) m._field.setDraggable(true);
                layers.push(m);
                return m;
            },
            addPolyline: function (pts, style) {
                var line = new global.google.maps.Polyline({
                    path: pts.map(toGLatLng),
                    strokeColor: style.color || '#FF6117',
                    strokeWeight: style.weight || 3,
                    strokeOpacity: style.opacity != null ? style.opacity : 0.8
                });
                line.setMap(map);
                layers.push(line);
                return { setLatLngs: function (np) { line.setPath(np.map(toGLatLng)); } };
            },
            addCircle: function (center, radiusM, style) {
                var circle = new global.google.maps.Circle({
                    center: toGLatLng(center),
                    radius: radiusM,
                    strokeColor: style.color || '#f97316',
                    strokeWeight: style.weight || 1.5,
                    strokeOpacity: 0.8,
                    fillColor: style.fillColor || '#f97316',
                    fillOpacity: style.fillOpacity != null ? style.fillOpacity : 0.05
                });
                circle.setMap(map);
                layers.push(circle);
                return circle;
            },
            addPolygon: function (pts, style) {
                var poly = new global.google.maps.Polygon({
                    paths: pts.map(toGLatLng),
                    strokeColor: style.color || '#FF6117',
                    strokeWeight: style.weight || 1.6,
                    strokeOpacity: 0.9,
                    fillColor: style.fillColor || '#FF6117',
                    fillOpacity: style.fillOpacity != null ? style.fillOpacity : 0.06
                });
                poly.setMap(map);
                layers.push(poly);
                return poly;
            }
        };
    }

    /* ============ Leaflet implementation (fallback) ============ */
    function macLeaflet(map) {
        var layers = [];
        return {
            _engine: 'leaflet',
            _map: map,
            fitTo: function (pts, padding) {
                if (!Array.isArray(pts) || pts.length === 0) return;
                map.fitBounds(pts, padding || {});
            },
            setView: function (ll, zoom) {
                map.setView(ll, zoom);
            },
            invalidateSize: function () { map.invalidateSize(); },
            onClick: function (cb) {
                map.on('click', function (e) { cb({ latlng: e.latlng }); });
            },
            addMarker: function (latlng, html, draggable) {
                var icon = L.divIcon({
                    className: '',
                    html: html || '',
                    iconSize: [40, 40],
                    iconAnchor: [20, 34]
                });
                var m = L.marker(latlng, { icon: icon, draggable: !!draggable }).addTo(map);
                layers.push(m);
                var wrap = {
                    _leaflet: m,
                    setLatLng: function (ll) { m.setLatLng(ll); },
                    getLatLng: function () {
                        var p = m.getLatLng();
                        return [p.lat, p.lng];
                    },
                    remove: function () { map.removeLayer(m); },
                    bindPopup: function (text) {
                        m.bindPopup(text);
                        return { openPopup: function () { m.openPopup(); } };
                    },
                    on: function (evt, cb) {
                        if (evt === 'click') {
                            m.on('click', function () { cb({ latlng: m.getLatLng() }); });
                        } else if (evt === 'dragend') {
                            m.on('dragend', function (e) { cb(e); });
                        } else {
                            m.on(evt, cb);
                        }
                    }
                };
                return wrap;
            },
            addPolyline: function (pts, style) {
                var line = L.polyline(pts, {
                    color: style.color || '#FF6117',
                    weight: style.weight || 3,
                    opacity: style.opacity != null ? style.opacity : 0.8,
                    dashArray: style.dashArray || '7 6'
                }).addTo(map);
                layers.push(line);
                return { setLatLngs: function (np) { line.setLatLngs(np); } };
            },
            addCircle: function (center, radiusM, style) {
                var c = L.circle(center, {
                    radius: radiusM,
                    color: style.color || '#f97316',
                    weight: style.weight || 1.5,
                    opacity: 0.8,
                    dashArray: style.dashArray || '4 6',
                    fillColor: style.fillColor || '#f97316',
                    fillOpacity: style.fillOpacity != null ? style.fillOpacity : 0.05
                }).addTo(map);
                layers.push(c);
                return c;
            },
            addPolygon: function (pts, style) {
                var p = L.polygon(pts, {
                    color: style.color || '#FF6117',
                    weight: style.weight || 1.6,
                    opacity: 0.9,
                    fillColor: style.fillColor || '#FF6117',
                    fillOpacity: style.fillOpacity != null ? style.fillOpacity : 0.06
                }).addTo(map);
                layers.push(p);
                return p;
            }
        };
    }

    function initMap(opts) {
        if (!opts || !opts.el) return null;
        var el = typeof opts.el === 'string' ? document.getElementById(opts.el) : opts.el;
        if (!el) return null;
        if (usingGoogle()) {
            return createGoogleMap(el, opts);
        }
        return createLeafletMap(el, opts);
    }

    /* Leaflet map construction (Free OSM tiles + dark invert filter). */
    function createLeafletMap(el, opts) {
        if (typeof L === 'undefined') return null;
        var map = L.map(el, { attributionControl: false, scrollWheelZoom: true })
            .setView(opts.center || [14.5995, 120.9842], opts.zoom || 15);
        if (opts.minZoom != null) map.setMinZoom(opts.minZoom);
        if (opts.maxZoom != null) map.setMaxZoom(opts.maxZoom);

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: opts.maxZoom || 19,
            minZoom: opts.minZoom || 13,
            subdomains: 'abcd',
            attribution: ''
        }).addTo(map);

        // Dark theme via CSS invert on the tile pane (markers stay true-color).
        var styleEl = document.createElement('style');
        styleEl.textContent =
            '.leaflet-layer,.leaflet-tile{filter:invert(100%) hue-rotate(180deg) brightness(95%) contrast(88%) !important;}';
        el.appendChild(styleEl);

        return macLeaflet(map);
    }

    /* When a Google map becomes ready after the bootstrap loads, any Maps.init()
     * calls made earlier were stashed. Drain the queue now. */
    global.ceGoogleMapsReady = function () {
        while (pending.length) {
            var item = pending.shift();
            var created = createGoogleMap(item.el, item.opts);
            if (item.cb) item.cb(created);
        }
    };

    /* ---------- public API ---------- */
    global.Maps = {
        /** Returns true when the Google Maps engine (keyed) is active. */
        usingGoogle: function () { return usingGoogle(); },
        /** Initialize a map. opts: {el, center, zoom, minZoom, maxZoom}. */
        init: function (opts, cb) {
            if (!opts || !opts.el) return null;
            var el = typeof opts.el === 'string' ? document.getElementById(opts.el) : opts.el;
            if (!el) return null;
            if (engineReady()) {
                var created = initMap({ el: el, center: opts.center, zoom: opts.zoom, minZoom: opts.minZoom, maxZoom: opts.maxZoom });
                if (cb) cb(created);
                return created;
            }
            if (usingGoogle()) {
                pending.push({ el: el, opts: { center: opts.center, zoom: opts.zoom, minZoom: opts.minZoom, maxZoom: opts.maxZoom }, cb: cb });
                return null;
            }
            return null;
        }
    };
})(window);