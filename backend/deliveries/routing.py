"""Road-following routes for live delivery tracking.

The tracking maps used to draw a straight line between the rider and the
customer, so the "route" cut straight through buildings and fences. Real
navigation apps route along the road network, so we ask a routing engine for
the actual drivable polyline and hand that to the map instead.

Providers are tried in order and every failure is non-fatal. Both defaults are
free, key-less public servers that may be slow, rate limited or simply down, so
when none of them answers we return None and the caller keeps drawing the
straight line. Results are cached because the tracking endpoint is polled every
few seconds by every open tab.
"""
import json
import sys
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.cache import cache

from .utils import haversine_km

# Sentinel so a cached "no route available" is not mistaken for a cache miss
# (otherwise every poll would re-hit a provider that is already failing).
_MISS = object()

# Coordinates are rounded before they become part of the cache key. 4 decimals
# is roughly 11 m, so a rider who is standing still keeps reusing the cached
# route instead of hammering a free public server on every single poll.
_CACHE_PRECISION = 4

# A failed lookup is cached briefly so a dead provider is not retried on every
# poll; a successful route is cached for much longer.
_FAIL_TTL = 60

# Guard rail in case a misconfigured base URL returns something huge.
_MAX_POINTS = 600

def _routing_enabled():
    if not getattr(settings, 'ROUTING_ENABLED', True):
        return False
    # The test suite must never depend on a third-party service being reachable.
    return 'test' not in sys.argv


def _coord_pair(lat, lng):
    return f'{round(float(lat), _CACHE_PRECISION)},{round(float(lng), _CACHE_PRECISION)}'


def _get_json(url, timeout):
    req = urllib.request.Request(url, headers={'User-Agent': 'CanteenExpress/1.0'})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode('utf-8'))


def decode_polyline(encoded, precision=6):
    """Decode Google's encoded-polyline format (also used by Valhalla).

    Returns a list of (lat, lng) tuples. `precision` is 5 for Google, 6 for
    Valhalla.
    """
    coordinates = []
    index = 0
    lat = 0
    lng = 0
    factor = 10 ** precision
    while index < len(encoded):
        for axis in ('lat', 'lng'):
            shift = 0
            result = 0
            while True:
                if index >= len(encoded):
                    raise ValueError('Truncated polyline payload')
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            # Odd values are negative: the sign is carried in the LSB.
            delta = ~(result >> 1) if result & 1 else (result >> 1)
            if axis == 'lat':
                lat += delta
            else:
                lng += delta
        coordinates.append((lat / factor, lng / factor))
    return coordinates


def _osrm_route(origin_lat, origin_lng, dest_lat, dest_lng):
    """Ask OSRM for a driving route. Returns (path, distance_km, minutes)."""
    base = (getattr(settings, 'OSRM_BASE_URL', '') or 'https://router.project-osrm.org').rstrip('/')
    coordinates = f'{origin_lng:.6f},{origin_lat:.6f};{dest_lng:.6f},{dest_lat:.6f}'
    url = f'{base}/route/v1/driving/{coordinates}?overview=full&geometries=geojson'
    data = _get_json(url, getattr(settings, 'ROUTING_TIMEOUT', 4))

    if data.get('code') != 'Ok' or not data.get('routes'):
        return None
    route = data['routes'][0]
    # GeoJSON orders coordinates as [lng, lat]; the maps want [lat, lng].
    path = [(point[1], point[0]) for point in route.get('geometry', {}).get('coordinates', [])]
    if len(path) < 2:
        return None
    return path, float(route['distance']) / 1000.0, float(route['duration']) / 60.0


def _valhalla_route(origin_lat, origin_lng, dest_lat, dest_lng):
    """Ask Valhalla for a walking route (covers campus footpaths a car profile
    cannot reach). Returns (path, distance_km, minutes)."""
    base = (getattr(settings, 'VALHALLA_BASE_URL', '') or 'https://valhalla1.openstreetmap.de').rstrip('/')
    payload = {
        'locations': [
            {'lat': origin_lat, 'lon': origin_lng},
            {'lat': dest_lat, 'lon': dest_lng},
        ],
        'costing': 'pedestrian',
        'directions_options': {'units': 'kilometers'},
    }
    url = f'{base}/route?json={urllib.parse.quote(json.dumps(payload))}'
    data = _get_json(url, getattr(settings, 'ROUTING_TIMEOUT', 4))

    trip = data.get('trip') or {}
    legs = trip.get('legs') or []
    if not legs or not legs[0].get('shape'):
        return None
    path = decode_polyline(legs[0]['shape'])
    if len(path) < 2:
        return None

    summary = trip.get('summary') or {}
    return path, float(summary.get('length', 0.0)), float(summary.get('time', 0.0)) / 60.0


# Ordered by preference: a rider on a motorbike follows the road network first,
# and only if that fails do we try the pedestrian graph for campus footpaths.
_PROVIDERS = (_osrm_route, _valhalla_route)


def get_road_route(origin_lat, origin_lng, dest_lat, dest_lng):
    """Return a road-following route between two points.

    Returns ``{'path': [(lat, lng), ...], 'distance_km': float,
    'duration_min': float, 'provider': str}`` or ``None`` when routing is
    disabled or every provider failed. Callers must treat None as "draw the
    straight line instead".
    """
    if not _routing_enabled():
        return None
    if None in (origin_lat, origin_lng, dest_lat, dest_lng):
        return None

    key = 'roadroute:{}|{}'.format(
        _coord_pair(origin_lat, origin_lng), _coord_pair(dest_lat, dest_lng))
    cached = cache.get(key, _MISS)
    if cached is not _MISS:
        return cached

    found = None
    for provider in _PROVIDERS:
        name = provider.__name__.lstrip('_').split('_')[0]
        try:
            result = provider(origin_lat, origin_lng, dest_lat, dest_lng)
        except Exception:
            # A provider that is down, slow or rate limiting must never break
            # tracking -- try the next one, then fall back to a straight line.
            result = None
        if not result:
            continue

        path, distance_km, duration_min = result
        path = path[:_MAX_POINTS]

        # Engines snap the endpoints to the nearest road (often 20-30 m away),
        # so pin the true rider position and destination onto the ends or the
        # line would visibly miss the markers on screen.
        origin = (origin_lat, origin_lng)
        dest = (dest_lat, dest_lng)
        lead = haversine_km(origin[0], origin[1], path[0][0], path[0][1])
        tail = haversine_km(path[-1][0], path[-1][1], dest[0], dest[1])
        if lead > 0.002:  # ~0.2 m: already on the road
            path.insert(0, origin)
        if tail > 0.002:
            path.append(dest)
        found = {
            'path': [[round(lat, 6), round(lng, 6)] for lat, lng in path],
            'distance_km': distance_km + lead + tail,
            'duration_min': duration_min,
            'provider': name,
        }
        break

    cache.set(
        key, found,
        getattr(settings, 'ROUTING_CACHE_SECONDS', 600) if found else _FAIL_TTL,
    )
    return found
