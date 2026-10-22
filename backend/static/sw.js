const CACHE_NAME = 'canex-pwa-v3';
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

  // Network-First for HTML pages so data is never stale.
  //
  // The offline fallback deliberately does NOT serve a cached HTML page.
  // Cached HTML is a *previous* build of the UI and, worse, a previous canteen
  // state -- a dashboard cached while "closed" would keep showing the closed
  // notice after staff reopened, and a stale sheet could show the old thin
  // header banner long after the layout changed. A failed navigation now just
  // fails, so the browser shows its own offline error instead of an
  // authoritative-looking but wrong page.
  if (e.request.mode === 'navigate' || (e.request.headers.get('accept') && e.request.headers.get('accept').includes('text/html'))) {
    e.respondWith(fetch(e.request));
    return;
  }

  // Cache-First for static assets (CSS/JS/images are safe: they are addressed
  // by path and refreshed whenever CACHE_NAME changes, unlike HTML).
  e.respondWith(
    caches.match(e.request).then((cachedResponse) => {
      return cachedResponse || fetch(e.request).then((networkResponse) => {
        return caches.open(CACHE_NAME).then((cache) => {
          cache.put(e.request, networkResponse.clone());
          return networkResponse;
        });
      }).catch(() => {});
    })
  );
});
