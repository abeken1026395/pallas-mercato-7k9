/* データ攻め ポータル Service Worker
   方針: ネットワーク優先（オンライン時は常に最新の出走表/データ）＋オフライン時はキャッシュ。
   出走表・払戻などは日々更新されるため、stale を掴ませない network-first にする。 */
var CACHE = "pallas-mercato-7k9-v1";
var SHELL = [
  "./", "./racers/", "./manifest.json?v=2",
  "./icon180.png", "./icon192.png", "./icon512.png"
];

self.addEventListener("install", function (e) {
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(SHELL).catch(function () {}); }));
});

self.addEventListener("activate", function (e) {
  e.waitUntil(
    caches.keys().then(function (ks) {
      return Promise.all(ks.map(function (k) { if (k !== CACHE) return caches.delete(k); }));
    })
  );
  self.clients.claim();
});

/* ページを開く要求を、HTTP キャッシュを通さずに取り直す。古いブラウザが navigate の要求に
   オプションを付けるのを拒んだときは、同じ URL を同じ条件で取り直す */
function fresh(req) {
  try {
    return fetch(req, { cache: "no-cache" });
  } catch (err) {
    return fetch(req.url, { cache: "no-cache", credentials: "same-origin", redirect: "manual" });
  }
}

self.addEventListener("fetch", function (e) {
  var req = e.request;
  if (req.method !== "GET") return;
  /* ページを開くときだけ、ブラウザの HTTP キャッシュ（GitHub Pages は最大10分）を使わず、必ず配信元に新しい版があるか確かめる。
     変わっていなければ 304 で軽く済む。データ・画像・アイコンはこれまでどおり */
  var net = req.mode === "navigate" ? fresh(req) : fetch(req);
  e.respondWith(
    net.then(function (res) {
      var cp = res.clone();
      caches.open(CACHE).then(function (c) { c.put(req, cp); }).catch(function () {});
      return res;
    }).catch(function () {
      return caches.match(req).then(function (m) { return m || caches.match("./racers/"); });
    })
  );
});

/* プッシュ通知（再訪設計 段階3・2026-11-13）。送り役が送る中身は {t:題, b:本文, u:開くページ, g:まとめる印}。
   押したら、そのページを開いているタブがあれば前に出し、無ければ開く */
self.addEventListener("push", function (e) {
  var d = {};
  try { d = e.data ? e.data.json() : {}; } catch (err) { d = {}; }
  var t = typeof d.t === "string" && d.t ? d.t.slice(0, 80) : "データ攻め";
  var u = typeof d.u === "string" && d.u.charAt(0) === "/" && d.u.charAt(1) !== "/" ? d.u : "/";
  e.waitUntil(self.registration.showNotification(t, {
    body: typeof d.b === "string" ? d.b.slice(0, 200) : "",
    tag: typeof d.g === "string" ? d.g.slice(0, 60) : "dz",
    icon: "/icon192.png",
    badge: "/icon192.png",
    data: { u: u }
  }));
});

self.addEventListener("notificationclick", function (e) {
  e.notification.close();
  var u = new URL((e.notification.data && e.notification.data.u) || "/", self.location.origin).href;
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(function (cs) {
    for (var i = 0; i < cs.length; i++) {
      if (cs[i].url.split("#")[0] === u.split("#")[0] && "focus" in cs[i]) { if ("navigate" in cs[i]) cs[i].navigate(u); return cs[i].focus(); }
    }
    return self.clients.openWindow ? self.clients.openWindow(u) : null;
  }));
});
