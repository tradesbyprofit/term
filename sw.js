// J.A.R.V.I.S. High-Frequency PWA Service Worker
const CACHE_NAME = 'jarvis-pinnacle-v1';
const STATIC_ASSETS = ['/'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    })
  );
  self.clients.claim();
});

// Network-first strategy for live Pinnacle market telemetry; fallback to cache for shell
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // If requesting real-time telemetry API, always go straight to network
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(fetch(event.request));
    return;
  }

  // App shell caching
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});
