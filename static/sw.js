/* FamilyHub service worker — keeps the wall UI loading if the server blips.
   Network-first so updates always come through online; falls back to the cached
   shell when offline. API calls are left alone — the app caches those itself
   (localStorage) so a dropped internet still shows the last calendar/weather. */
const CACHE = "familyhub-v2";
const SHELL = ["/", "/index.html", "/theme.js", "/seasonal.js", "/manifest.json"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return; // album photos etc. — never cache cross-origin
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/photos/")) return;   // app owns API caching; photos are big
  e.respondWith(
    fetch(req)
      .then((r) => { const cp = r.clone(); caches.open(CACHE).then((c) => c.put(req, cp)); return r; })
      .catch(() => caches.match(req).then((m) => m || caches.match("/index.html")))
  );
});
