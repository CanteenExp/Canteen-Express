self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open('canex-pwa-v1').then((cache) => {
      return cache.addAll([
        '/',
        '/kiosk/',
        '/accounts/login/',
        '/canteen/staff/',
        '/deliveries/dashboard/'
      ]).catch(() => {});
    })
  );
});

self.addEventListener('fetch', (e) => {
  e.respondWith(
    caches.match(e.request).then((response) => {
      return response || fetch(e.request);
    })
  );
});
