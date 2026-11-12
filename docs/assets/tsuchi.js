/* プッシュ通知（再訪設計 段階3・2026-11-13）。出走表と見どころのレースごとに「10分前に知らせる」「結果を知らせる」を選べる。
   締切がずれたときは、送り役が公式の締切予定時刻で確かめて、新しい時刻の10分前に送る。自分で選んだレースは1日の上限なし（けん裁定）。
   オンにした人だけ、購読の情報と「選んだレースの番号・締切の時刻・知らせる種類」を /api/push に送る。金額・メモ・収支は送らない。
   iPhone はホーム画面に追加したアプリの中だけで使える（Apple の決まり）。
   端末に残すもの：dz_tsuchiR（{レースID:{dl,m,k}}）・dz_push（{on:1}）・dz_pushSync（最後に送った中身の印と時刻）。
   置き方：ページに <div class="dzt" data-rid="場_日付_R" data-t="締切の時:分"></div> を置けば、ここがボタンを入れる（後から描いた分も拾う）。
   自分の記録の「通知」の欄は dzTsuchi.state() / on() / off() / count() を使う。 */
(function () {
  if (window.dzTsuchi) return;
  /* 通知の送り主の公開鍵（VAPID）。公開してよい値で、秘密の鍵は Cloudflare の送り役にだけある */
  var KEY = "BNThGrWSzzqv4y2XtgD8AeTKtz_MyncYZxzkMtpTLcSw4xt3TXd1oiJHFXws8RdNKfLQqKHLiaS5rQLXKCwFc9I"; // gitleaks:allow
  var RID = /^(0[1-9]|1\d|2[0-4])_(\d{8})_([1-9]|1[0-2])$/;
  var RKEY = "dz_tsuchiR";
  function get(k) { try { var v = JSON.parse(localStorage.getItem(k) || "{}"); return v && typeof v === "object" && !Array.isArray(v) ? v : {}; } catch (e) { return {}; } }
  function put(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); return true; } catch (e) { return false; } }
  function del(k) { try { localStorage.removeItem(k); } catch (e) {} }
  function u8(s) { var t = s.replace(/-/g, "+").replace(/_/g, "/"), b = atob(t + "===".slice((t.length + 3) % 4)), o = new Uint8Array(b.length); for (var i = 0; i < b.length; i++) o[i] = b.charCodeAt(i); return o; }
  function ios() { return /iP(hone|ad|od)/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1); }
  function standalone() { try { return navigator.standalone === true || matchMedia("(display-mode: standalone)").matches; } catch (e) { return false; } }
  function can() { return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window && (location.protocol === "https:" || /^(localhost|127\.0\.0\.1)$/.test(location.hostname)); }
  // 選んだレースのうち、まだ知らせる意味のあるもの（10分前は締切前・結果は締切から3時間まで）
  function races(now) {
    var R = get(RKEY), out = [];
    Object.keys(R).forEach(function (rid) {
      var e = R[rid], m = RID.exec(rid);
      if (!m || !e || typeof e !== "object") return;
      var dl = +e.dl, mm = e.m ? 1 : 0, kk = e.k ? 1 : 0;
      if (!isFinite(dl)) return;
      if (dl < now - 60000) mm = 0;
      if (dl < now - 3 * 3600000) kk = 0;
      if ((mm || kk) && dl < now + 3 * 86400000) out.push({ rid: rid, dl: dl, m: mm, k: kk });
    });
    out.sort(function (a, b) { return a.dl - b.dl || (a.rid < b.rid ? -1 : 1); });
    return out.slice(0, 60);
  }
  // 古くなった選択と壊れた値は端末からも消す（締切が2日より前・7日より先・形の違うもの）
  function prune() { var R = get(RKEY), now = Date.now(), ch = false; Object.keys(R).forEach(function (k) { var e = R[k], d = e && +e.dl; if (!RID.test(k) || !e || typeof e !== "object" || !(d > now - 2 * 86400000 && d < now + 7 * 86400000)) { delete R[k]; ch = true; } }); if (ch) put(RKEY, R); }
  function reg() { return navigator.serviceWorker.register("/sw.js").then(function () { return navigator.serviceWorker.ready; }); }
  function post(body) {
    return fetch("/api/push", { method: "POST", headers: { "content-type": "text/plain" }, body: JSON.stringify(body), cache: "no-store", credentials: "omit" })
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { if (!r.ok || !j.ok) throw new Error("push " + r.status); return j; }); });
  }
  var T = {
    // no（このブラウザでは使えない）／home（iPhone でホーム画面に追加が要る）／denied（通知を断っている）／off／on
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
          return post({ a: "off", sub: { endpoint: s.toJSON().endpoint } }).catch(function () {}).then(function () { return s.unsubscribe(); });
        });
      }).catch(function () {}).then(function () { T.paint(); });
    },
    // 選んだレースが変わったら送り直す。同じ中身なら6時間に1回だけ（購読がまだ生きているかの知らせを兼ねる）
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
    count: function () { return races(Date.now()).length; },
    // 1レースの選択を切り替える。kind は "m"（10分前）か "k"（結果）
    toggle: function (rid, dl, kind) {
      var R = get(RKEY), e = R[rid] && typeof R[rid] === "object" ? R[rid] : { dl: dl, m: 0, k: 0 };
      var wasOn = T.state() === "on";
      e.dl = dl; e[kind] = wasOn ? (e[kind] ? 0 : 1) : 1; // 通知がオフのときに押したら、選んでからオンにする
      if (!e.m && !e.k) delete R[rid]; else R[rid] = e;
      if (!put(RKEY, R)) return Promise.reject(new Error("save"));
      var turnOn = !wasOn;
      return (turnOn ? T.on() : T.sync(true)).catch(function (err) {
        // 許可が出なかったら選択を戻す
        if (turnOn) { var R2 = get(RKEY), e2 = R2[rid]; if (e2) { e2[kind] = 0; if (!e2.m && !e2.k) delete R2[rid]; put(RKEY, R2); } }
        throw err;
      });
    },
    paint: function () { var ls = document.querySelectorAll(".dzt"); for (var i = 0; i < ls.length; i++) draw(ls[i]); }
  };
  window.dzTsuchi = T;

  /* ---- レースごとのボタン ---- */
  var CSS = ".dzt{margin:8px 0 0}.dzt-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(11.5em,1fr));gap:8px}"
    + ".dzt-b{min-height:48px;padding:0 8px;border:1px solid rgba(232,236,239,.32);border-radius:0;background:none;color:#eef3f8;font-family:inherit;font-size:14px;font-weight:700;line-height:1.3;white-space:nowrap;cursor:pointer;-webkit-tap-highlight-color:transparent}"
    + ".dzt-b[aria-pressed=true]{background:#eef3f8;border-color:#eef3f8;color:#0b1726}"
    + ".dzt-b:disabled{opacity:.6;cursor:default}"
    + ".dzt-m{margin:6px 0 0;font-size:13px;line-height:1.6;color:#cdd7e0}.dzt-m a{color:inherit;text-decoration:underline}";
  function css() { if (document.getElementById("dztCss")) return; var s = document.createElement("style"); s.id = "dztCss"; s.textContent = CSS; document.head.appendChild(s); }
  function note(box, k) {
    var m = box.querySelector(".dzt-m"); if (!m) { m = document.createElement("p"); m.className = "dzt-m"; m.setAttribute("role", "status"); box.appendChild(m); }
    m.textContent = "";
    if (k === "home") {
      m.appendChild(document.createTextNode("iPhone では、ホーム画面に追加したデータ攻めから使えます。"));
      var a = document.createElement("a"); a.href = "/note/#bets"; a.textContent = "追加のしかた"; m.appendChild(a);
    } else m.textContent = k === "denied" ? "この端末で通知が止められています。設定アプリの通知から、データ攻めを許可してください。"
      : k === "dismiss" ? "通知の許可が出ませんでした。もう一度押すと聞き直します。"
      : k === "no" ? "このブラウザは通知に対応していません。"
      : "登録できませんでした。通信の良いところで、もう一度押してください。";
  }
  function draw(box) {
    var rid = box.getAttribute("data-rid"), dl = dlOf(box);
    if (!dl) { box.hidden = true; return; }
    var now = Date.now(), e = get(RKEY)[rid] || {}, on = T.state() === "on";
    var showM = dl > now + 60000, showK = dl > now - 3 * 3600000;
    if (!showM && !showK) { box.hidden = true; return; }
    css(); box.hidden = false;
    var row = box.querySelector(".dzt-row");
    if (!row) { row = document.createElement("div"); row.className = "dzt-row"; box.insertBefore(row, box.firstChild); }
    var want = (showM ? "m" : "") + (showK ? "k" : "");
    if (row.getAttribute("data-w") !== want) {
      row.textContent = ""; row.setAttribute("data-w", want);
      if (showM) row.appendChild(btn("m")); if (showK) row.appendChild(btn("k"));
    }
    var bs = row.querySelectorAll(".dzt-b");
    for (var i = 0; i < bs.length; i++) {
      var k = bs[i].getAttribute("data-k"), p = !!(on && e[k]);
      bs[i].setAttribute("aria-pressed", p ? "true" : "false");
      bs[i].textContent = k === "m" ? (p ? "10分前に知らせます ✓" : "10分前に知らせる") : (p ? "結果を知らせます ✓" : "結果を知らせる");
    }
  }
  function dlOf(box) {
    var m = RID.exec(box.getAttribute("data-rid") || ""), t = /^(\d{1,2}):(\d{2})$/.exec(box.getAttribute("data-t") || "");
    if (!m || !t) return 0;
    var h = m[2];
    return Date.UTC(+h.slice(0, 4), +h.slice(4, 6) - 1, +h.slice(6, 8), +t[1] - 9, +t[2]);
  }
  function btn(k) { var b = document.createElement("button"); b.type = "button"; b.className = "dzt-b"; b.setAttribute("data-k", k); return b; }
  document.addEventListener("click", function (ev) {
    var b = ev.target && ev.target.closest ? ev.target.closest(".dzt-b") : null; if (!b) return;
    var box = b.closest(".dzt"); if (!box) return;
    ev.preventDefault(); ev.stopPropagation();
    var s = T.state();
    if (s === "home" || s === "denied" || s === "no") { note(box, s); return; }
    var rid = box.getAttribute("data-rid"), dl = dlOf(box), k = b.getAttribute("data-k");
    if (!dl) return;
    b.disabled = true;
    var m = box.querySelector(".dzt-m"); if (m) m.remove();
    T.toggle(rid, dl, k).then(function () { b.disabled = false; T.paint(); }, function (err) { b.disabled = false; note(box, err && err.message); T.paint(); });
  }, true);
  function boot() {
    prune(); T.paint();
    try { new MutationObserver(function (ms) { for (var i = 0; i < ms.length; i++) { var a = ms[i].addedNodes; for (var j = 0; j < a.length; j++) { var n = a[j]; if (n.nodeType === 1 && (n.classList.contains("dzt") || n.querySelector(".dzt"))) { T.paint(); return; } } } }).observe(document.body, { childList: true, subtree: true }); } catch (e) {}
    setInterval(T.paint, 60000);
    setTimeout(function () { T.sync(false).catch(function () {}); }, 1500);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
})();
