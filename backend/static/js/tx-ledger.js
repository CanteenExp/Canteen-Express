/* In-place filtering for the staff "Transaction Logs" tab.

   Clicking a customer-group tab (Delivery personnel, Faculty & staff, ...),
   paging, or applying the filter form used to reload the whole dashboard.
   That reload made the page flash back to the Overview tab before Alpine
   restored `?tab=transactions`, and it re-ran every dashboard query.

   This module swaps only the `#tx-ledger` fragment, fetched from
   `canteen_menu.views.transaction_log_ledger`, so:

     * nothing navigates -> no flash of the dashboard overview;
     * only the ledger query runs -> the swap lands in a few milliseconds;
     * the four group tabs are prefetched (on hover/focus and when the tab
       opens), so the first click is usually served from memory;
     * the address bar still updates, so a filtered ledger stays shareable.

   Everything degrades to plain links if this script never runs. */
(function () {
    'use strict';

    var panel = document.getElementById('tx-panel');
    var endpoint = panel && panel.getAttribute('data-tx-ledger-url');
    if (!panel || !endpoint) { return; }

    var KEYS = ['tx_group', 'tx_days', 'tx_q', 'tx_page'];
    var TTL = 60000;
    var LIMIT = 30;
    var cache = new Map();
    var inflight = new Set();
    var pending = 0;

    function ledger() {
        return document.getElementById('tx-ledger');
    }

    function endpointFor(url) {
        var params = new URLSearchParams();
        KEYS.forEach(function (key) {
            var value = url.searchParams.get(key);
            if (value) { params.set(key, value); }
        });
        var query = params.toString();
        return query ? endpoint + '?' + query : endpoint;
    }

    function readCache(key) {
        var hit = cache.get(key);
        if (!hit) { return null; }
        if (Date.now() - hit.at > TTL) {
            cache.delete(key);
            return null;
        }
        return hit.html;
    }

    function writeCache(key, html) {
        if (cache.size >= LIMIT) {
            cache.delete(cache.keys().next().value);
        }
        cache.set(key, { html: html, at: Date.now() });
    }

    function request(key) {
        return fetch(key, {
            credentials: 'same-origin',
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        }).then(function (response) {
            if (!response.ok) { throw new Error('HTTP ' + response.status); }
            return response.text();
        });
    }

    function prefetch(key) {
        if (readCache(key) !== null || inflight.has(key)) { return; }
        inflight.add(key);
        request(key).then(function (html) {
            writeCache(key, html);
        }).catch(function () {
            /* Offline: the real link still works. */
        }).then(function () {
            inflight.delete(key);
        });
    }

    function paint(html) {
        var current = ledger();
        if (!current) { return; }
        current.outerHTML = html;
        var fresh = ledger();
        if (fresh) {
            fresh.removeAttribute('aria-busy');
            warmGroupLinks();
        }
    }

    function load(key, fallbackUrl) {
        var seq = ++pending;
        var cached = readCache(key);
        if (cached !== null) {
            paint(cached);
            return;
        }

        var current = ledger();
        var timer = window.setTimeout(function () {
            if (current) { current.setAttribute('aria-busy', 'true'); }
        }, 120);

        request(key).then(function (html) {
            window.clearTimeout(timer);
            if (seq !== pending) { return; }
            writeCache(key, html);
            paint(html);
        }).catch(function () {
            window.clearTimeout(timer);
            if (seq !== pending) { return; }
            if (current) { current.removeAttribute('aria-busy'); }
            window.location.href = fallbackUrl;
        });
    }

    function go(link) {
        var url = new URL(link.href, window.location.origin);
        try {
            window.history.replaceState(null, '', url.pathname + url.search);
        } catch (error) {
            /* history is unavailable in some embedded webviews */
        }
        load(endpointFor(url), url.pathname + url.search);
    }

    function warmGroupLinks() {
        var links = document.querySelectorAll('#tx-ledger a[data-tx-prefetch]');
        Array.prototype.forEach.call(links, function (link) {
            prefetch(endpointFor(new URL(link.href, window.location.origin)));
        });
    }

    // Delegated listeners keep working after the fragment is replaced.
    document.addEventListener('click', function (event) {
        var target = event.target;
        var link = target && target.closest ? target.closest('#tx-ledger a[data-tx-nav]') : null;
        if (!link || event.defaultPrevented) { return; }
        if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) { return; }
        event.preventDefault();
        go(link);
    });

    document.addEventListener('submit', function (event) {
        var target = event.target;
        var form = target && target.closest ? target.closest('#tx-ledger form') : null;
        if (!form || event.defaultPrevented) { return; }
        event.preventDefault();
        var url = new URL(window.location.pathname, window.location.origin);
        url.search = new URLSearchParams(new FormData(form)).toString();
        try {
            window.history.replaceState(null, '', url.pathname + url.search);
        } catch (error) {
            /* ignore */
        }
        load(endpointFor(url), url.pathname + url.search);
    });

    document.addEventListener('change', function (event) {
        var target = event.target;
        // Picking a date range applies it straight away, without a reload.
        var select = target && target.closest ? target.closest('#tx-ledger select[name="tx_days"]') : null;
        if (select && select.form && select.form.requestSubmit) {
            select.form.requestSubmit();
        }
    });

    function warmFromEvent(event) {
        var target = event.target;
        var link = target && target.closest ? target.closest('#tx-ledger a[data-tx-nav]') : null;
        if (link) {
            prefetch(endpointFor(new URL(link.href, window.location.origin)));
        }
    }

    document.addEventListener('pointerover', warmFromEvent, { passive: true });
    document.addEventListener('focusin', warmFromEvent);

    // Warm the group tabs as soon as the ledger is on screen (Alpine raises
    // this when the tab is opened), and once at boot if it already is.
    window.addEventListener('tx-warm', warmGroupLinks);
    if (panel.style.display !== 'none') {
        warmGroupLinks();
    }
})();
