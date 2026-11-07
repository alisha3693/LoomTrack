// App-shell service worker. Once the app has been opened online, it opens again with no network at all.
// API calls are never cached here: the app keeps its own last-known data and an outbox of updates to send.
const CACHE = "loomtrack-v2";

// Everything the first screen needs is stored at install time: the page, then the scripts and styles it names.
async function precache() {
  const cache = await caches.open(CACHE);
  await cache.addAll(["/", "/icon.svg", "/icon-192.png", "/manifest.webmanifest"]);
  try {
    const html = await (await cache.match("/")).text();
    const assets = [...new Set(html.match(/\/assets\/[^"']+/g) || [])];
    await cache.addAll(assets);
  } catch (e) {
    /* the page still works online, and each file is stored the first time it is used */
  }
}

self.addEventListener("install", (e) => {
  e.waitUntil(precache());
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.pathname.startsWith("/api/")) return;

  // Pages: network first so a new version is picked up, the stored page when there is no network.
  // Every address under the app is the same page (the app draws the screen), so one stored copy serves them all.
  if (e.request.mode === "navigate") {
    e.respondWith(
      fetch(e.request)
        .then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put("/", copy));
          }
          return res;
        })
        .catch(() => caches.match("/")),
    );
    return;
  }

  // Scripts, styles, fonts and icons: stored copy first.
  e.respondWith(
    caches.match(e.request).then(
      (hit) =>
        hit ||
        fetch(e.request).then((res) => {
          if (res.ok && (url.origin === location.origin || url.hostname.endsWith("gstatic.com") || url.hostname.endsWith("googleapis.com"))) {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(e.request, copy));
          }
          return res;
        }),
    ),
  );
});
