/* プッシュ通知（再訪設計 段階3・2026-11-13）。保存した買い目のあるレースの締切10分前に知らせる。1日3通まで。
   オンにした人だけ、購読の情報と「レースの番号・締切の時刻」を /api/push に送る。金額・メモ・収支は送らない。
   iPhone はホーム画面に追加したアプリの中だけで使える（Apple の決まり）。
   端末に残すもの：dz_push（{on:1}）・dz_pushSync（最後に送った中身の印と時刻）。
   使う側：自分の記録（ボタン）・出走表（保存と削除のあとに dzTsuchi.sync()）。 */
(function () {
  if (window.dzTsuchi) return;
  /* 通知の送り主の公開鍵（VAPID）。公開してよい値で、秘密の鍵は Cloudflare の送り役にだけある */
  var KEY = "BNThGrWSzzqv4y2XtgD8AeTKtz_MyncYZxzkMtpTLcSw4xt3TXd1oiJHFXws8RdNKfLQqKHLiaS5rQLXKCwFc9I"; // gitleaks:allow
  var RID = /^(0[1-9]|1\d|2[0-4])_(\d{8})_([1-9]|1[0-2])$/;
  function get(k) { try { var v = JSON.parse(localStorage.getItem(k) || "{}"); return v && typeof v === "object" && !Array.isArray(v) ? v : {}; } catch (e) { return {}; } }
  function put(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); return true; } catch (e) { return false; } }
  function del(k) { try { localStorage.removeItem(k); } catch (e) {} }
  function u8(s) { var t = s.replace(/-/g, "+").replace(/_/g, "/"), b = atob(t + "===".slice((t.length + 3) % 4)), o = new Uint8Array(b.length); for (var i = 0; i < b.length; i++) o[i] = b.charCodeAt(i); return o; }
  function ios() { return /iP(hone|ad|od)/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1); }
  function standalone() { try { return navigator.standalone === true || matchMedia("(display-mode: standalone)").matches; } catch (e) { return false; } }
  function can() { return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window && (location.protocol === "https:" || /^(localhost|127\.0\.0\.1)$/.test(location.hostname)); }
  // 保存した買い目から、これから締切のレースだけ（締切は日付と「時:分」から日本時間で計算）
  function races(now) {
    var B = get("dz_bets"), out = [];
    Object.keys(B).forEach(function (rid) {
      var e = B[rid], m = RID.exec(rid);
      if (!m || !e || typeof e !== "object" || !Array.isArray(e.b) || !e.b.length) return;
      var d = /^(\d{1,2}):(\d{2})$/.exec(String(e.d || "")); if (!d) return;
      var h = m[2], dl = Date.UTC(+h.slice(0, 4), +h.slice(4, 6) - 1, +h.slice(6, 8), +d[1] - 9, +d[2]);
      if (dl > now - 60000 && dl < now + 3 * 86400000) out.push({ rid: rid, dl: dl });
    });
    out.sort(function (a, b) { return a.dl - b.dl || (a.rid < b.rid ? -1 : 1); });
    return out.slice(0, 60);
  }
  function reg() { return navigator.serviceWorker.register("/sw.js").then(function () { return navigator.serviceWorker.ready; }); }
  function post(body) {
    return fetch("/api/push", { method: "POST", headers: { "content-type": "text/plain" }, body: JSON.stringify(body), cache: "no-store", credentials: "omit" })
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { if (!r.ok || !j.ok) throw new Error("push " + r.status); return j; }); });
  }
  var T = {
    // 画面に出す状態：no（この端末では使えない）／home（iPhone でホーム画面に追加が要る）／denied（通知を断っている）／off／on
    state: function () {
      if (ios() && !standalone()) return "home";
      if (!can()) return "no";
      if (Notification.permission === "denied") return "denied";
      return get("dz_push").on ? "on" : "off";
    },
    on: function () {
      if (!can()) return Promise.reject(new Error("no"));
      return Promise.resolve(Notification.requestPermission()).then(function (p) {
        if (p !== "granted") throw new Error(p === "denied" ? "denied" : "dismiss");
        return reg();
      }).then(function (r) {
        return r.pushManager.getSubscription().then(function (s) { return s || r.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: u8(KEY) }); });
      }).then(function (s) {
        put("dz_push", { on: 1 });
        return T.sync(true, s);
      });
    },
    off: function () {
      del("dz_push"); del("dz_pushSync");
      if (!can()) return Promise.resolve();
      return navigator.serviceWorker.getRegistration("/").then(function (r) {
        if (!r) return;
        return r.pushManager.getSubscription().then(function (s) {
          if (!s) return;
          var j = s.toJSON();
          return post({ a: "off", sub: { endpoint: j.endpoint } }).catch(function () {}).then(function () { return s.unsubscribe(); });
        });
      }).catch(function () {});
    },
    // 保存した買い目が変わったら送り直す。同じ中身なら6時間に1回だけ（購読がまだ生きているかの知らせを兼ねる）
    sync: function (force, sub) {
      if (!get("dz_push").on || !can() || Notification.permission !== "granted") return Promise.resolve(null);
      var now = Date.now(), rs = races(now), sig = JSON.stringify(rs), S = get("dz_pushSync");
      if (!force && S.s === sig && now - (+S.t || 0) < 6 * 3600000) return Promise.resolve(null);
      var p = sub ? Promise.resolve(sub) : navigator.serviceWorker.getRegistration("/").then(function (r) { return r ? r.pushManager.getSubscription() : null; });
      return p.then(function (s) {
        if (!s) { del("dz_push"); del("dz_pushSync"); return null; } // 別の端末から引き継いだ印だけが残っている
        var j = s.toJSON();
        return post({ a: "sync", sub: { endpoint: j.endpoint, keys: j.keys }, races: rs }).then(function (r) { put("dz_pushSync", { s: sig, t: now }); return r; });
      });
    },
    count: function () { return races(Date.now()).length; }
  };
  window.dzTsuchi = T;
  // 読み込んだページで、オンの人は黙って送り直す（失敗しても何もしない）
  setTimeout(function () { T.sync(false).catch(function () {}); }, 1500);
})();
