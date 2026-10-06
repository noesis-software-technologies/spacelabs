const CACHE = 'carreaux-v1';
const STATIC = [
  '/static/carreaux/manifest.json',
  '/static/carreaux/icon-192.png',
  '/static/carreaux/icon-512.png',
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(STATIC.filter(u => !u.endsWith('.png')))));
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys =>
    Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
  ));
  self.clients.claim();
});

// Network-first pour les pages dynamiques Django
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  const url = new URL(e.request.url);
  if (url.pathname.startsWith('/carreaux/') || url.pathname.startsWith('/static/carreaux/')) {
    e.respondWith(
      fetch(e.request).catch(() => caches.match(e.request))
    );
  }
});
