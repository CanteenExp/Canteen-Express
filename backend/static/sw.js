const CACHE_NAME = 'canex-pwa-v4';
const STATIC_ASSETS = [
  '/static/logo.png',
  '/static/official_logo.png',
  '/static/Student.png',
  '/static/Prof.png',
  '/static/Rider.png'
];

self.addEventListener('install', (e) => {
  self.skipWaiting();
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS).catch(() => {});
    })
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);

  if (e.request.method !== 'GET') {
    return;
  }

  // Cross-origin requests (Supabase menu photos, Unsplash fallbacks, map tiles)
  // go straight to the browser. Caching them here used to freeze a 400/402
  // error response forever and made fixed image URLs keep looking broken.
  if (url.origin !== self.location.origin) {
    return;
  }

  // Network-First for HTML pages so data is never stale
  if (e.request.mode === 'navigate' || (e.request.headers.get('accept') || '').includes('text/html')) {
    e.respondWith(
      fetch(e.request)
        .catch(() => caches.match(e.request))
    );
    return;
  }

  // Never cache API/menu JSON: the kiosk polls /kiosk/api/menu/ every 3s and a
  // cache-first reply would pin the first menu snapshot (old prices, old image
  // URLs) for the life of the service worker.
  if (!url.pathname.startsWith('/static/')) {
    return;
  }

  // Cache-First for static assets only, and only cache successful responses.
  e.respondWith(
    caches.match(e.request).then((cachedResponse) => {
      return cachedResponse || fetch(e.request).then((networkResponse) => {
        if (networkResponse.ok) {
          const copy = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(e.request, copy));
        }
        return networkResponse;
      }).catch(() => {});
    })
  );
});
