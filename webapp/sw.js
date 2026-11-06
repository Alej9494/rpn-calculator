// Service worker: keeps the app on the phone so it opens instantly and works
// offline. Files are served from the cache first. The Pages workflow replaces
// VERSION with the commit id on every publish; the browser sees sw.js has
// changed, fetches the new files, and the next time the app opens it runs the
// new version. Nothing needs bumping by hand.
const VERSION = "dev";
const CACHE = "rpn-" + VERSION;
const FILES = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./fonts/IBMPlexMono-SemiBold.woff2",
  "./fonts/IBMPlexSansCondensed-SemiBold.woff2",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./icons/icon-maskable-512.png",
  "./icons/apple-touch-icon.png"
];

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE)
      .then(cache => cache.addAll(FILES.map(f => new Request(f, { cache: "reload" }))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k.startsWith("rpn-") && k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", event => {
  if (event.request.method !== "GET") return;
  event.respondWith(
    caches.match(event.request, { ignoreSearch: true })
      .then(hit => hit || fetch(event.request))
  );
});
