// 90 Meclis service worker: sayfalar ağdan (çevrimdışıysa son kopya), /assets/* değişmez dosyalar önbellekten.
// Veri (Supabase) hiçbir zaman önbelleğe alınmaz: rakam her zaman canlıdır.
const V = "90m-v1";
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(
  caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== V).map((k) => caches.delete(k)))).then(() => self.clients.claim()),
));
self.addEventListener("fetch", (e) => {
  const r = e.request;
  if (r.method !== "GET") return;
  const u = new URL(r.url);
  if (u.origin !== self.location.origin) return;
  if (u.pathname.includes("/assets/")) {
    e.respondWith(caches.open(V).then(async (c) => (await c.match(r)) || fetch(r).then((res) => { if (res.ok) c.put(r, res.clone()); return res; })));
  } else if (r.mode === "navigate") {
    e.respondWith(fetch(r).then((res) => { const cp = res.clone(); caches.open(V).then((c) => c.put(r, cp)); return res; })
      .catch(() => caches.match(r).then((m) => m || caches.match(self.registration.scope))));
  }
});
