/* 旧URL（github.io）の Service Worker を片づける版。
   以前の sw.js はトップと出走表をキャッシュしていたため、ホーム画面から開く人が
   古いページを掴んだままになる。この版は入った瞬間に全キャッシュを消し、自分を外す。 */
self.addEventListener("install", function () { self.skipWaiting(); });
self.addEventListener("activate", function (e) {
  e.waitUntil(
    caches.keys()
      .then(function (keys) { return Promise.all(keys.map(function (k) { return caches.delete(k); })); })
      .then(function () { return self.registration.unregister(); })
      .then(function () { return self.clients.matchAll({ type: "window" }); })
      .then(function (cs) { cs.forEach(function (c) { c.navigate(c.url); }); })
  );
});
