/* LaTablée service worker — cache-first shell for offline PWA.
   API calls are network-only (data must be fresh); pages/assets cache-first. */
const CACHE = "latablee-v1";
const ASSETS = ["/", "/manifest.json"];

self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(ASSETS)));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))),
    ).then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET") return;
  // never cache API
  if (url.pathname.startsWith("/api/")) return;

  // static assets + pages: cache-first, refresh in background
  event.respondWith(
    caches.match(event.request).then((hit) => {
      const fetched = fetch(event.request)
        .then((res) => {
          if (res.ok && url.origin === location.origin) {
            const copy = res.clone();
            caches.open(CACHE).then((cache) => cache.put(event.request, copy));
          }
          return res;
        })
        .catch(() => hit);
      return hit || fetched;
    }),
  );
});