/* プッシュ通知（再訪設計 段階3・2026-11-13）。出走表と見どころのレースごとに「10分前に知らせる」「結果を知らせる」を選べる。
   締切がずれたときは、送り役が公式の締切予定時刻で確かめて、新しい時刻の10分前に送る。自分で選んだレースは1日の上限なし（けん裁定）。
   オンにした人だけ、購読の情報と「選んだレースの番号・締切の時刻・知らせる種類」を /api/push に送る。金額・メモ・収支は送らない。
   iPhone はホーム画面に追加したアプリの中だけで使える（Apple の決まり）。
   推し・モーター（2026-11-17 けん）：出走表で付けた推し選手（br_oshi）・推しモーター（dz_oshiMotor）のうち、本人が選んだものだけ、
   出るレースの締切10分前に知らせる。選んだものは dz_tsuchiF（{"p:登録番号":1,"m:場コード_機番":1}）。登録番号と場コード_機番も送る。
   その日のまとめ（2026-11-19 けん）：買い目を保存したレース（dz_bets）の番号と締切だけを送り、その日の結果が出そろったら夜に1通。
   外れの日も送る。買い目・金額は送らない。止めるときは dz_tsuchiS（{off:1}）。
   端末に残すもの：dz_tsuchiR（{レースID:{dl,m,k}}）・dz_tsuchiF・dz_push（{on:1}）・dz_pushSync（最後に送った中身の印と時刻）。
   置き方：ページに <div class="dzt" data-rid="場_日付_R" data-t="締切の時:分"></div> を置けば、ここがボタンを入れる（後から描いた分も拾う）。
   自分の記録の「通知」の欄は dzTsuchi.state() / on() / off() / count() を使う。 */
(function () {
  if (window.dzTsuchi) return;
  /* 通知の送り主の公開鍵（VAPID）。公開してよい値で、秘密の鍵は Cloudflare の送り役にだけある */
  var KEY = "BNThGrWSzzqv4y2XtgD8AeTKtz_MyncYZxzkMtpTLcSw4xt3TXd1oiJHFXws8RdNKfLQqKHLiaS5rQLXKCwFc9I"; // gitleaks:allow
  var RID = /^(0[1-9]|1\d|2[0-4])_(\d{8})_([1-9]|1[0-2])$/;
  var RKEY = "dz_tsuchiR", FKEY = "dz_tsuchiF", SKEY = "dz_tsuchiS";
  var JO = { "01": "桐生", "02": "戸田", "03": "江戸川", "04": "平和島", "05": "多摩川", "06": "浜名湖", "07": "蒲郡", "08": "常滑", "09": "津", "10": "三国", "11": "びわこ", "12": "住之江", "13": "尼崎", "14": "鳴門", "15": "丸亀", "16": "児島", "17": "宮島", "18": "徳山", "19": "下関", "20": "若松", "21": "芦屋", "22": "福岡", "23": "唐津", "24": "大村" };
  var FOL = /^(p:\d{4}|m:(0[1-9]|1\d|2[0-4])_[1-9]\d{0,2})$/;
  function get(k) { try { var v = JSON.parse(localStorage.getItem(k) || "{}"); return v && typeof v === "object" && !Array.isArray(v) ? v : {}; } catch (e) { return {}; } }
  function put(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); return true; } catch (e) { return false; } }
  function del(k) { try { localStorage.removeItem(k); } catch (e) {} }
  function u8(s) { var t = s.replace(/-/g, "+").replace(/_/g, "/"), b = atob(t + "===".slice((t.length + 3) % 4)), o = new Uint8Array(b.length); for (var i = 0; i < b.length; i++) o[i] = b.charCodeAt(i); return o; }
  function ios() { return /iP(hone|ad|od)/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1); }
  function standalone() { try { return navigator.standalone === true || matchMedia("(display-mode: standalone)").matches; } catch (e) { return false; } }
  function can() { return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window && (location.protocol === "https:" || /^(localhost|127\.0\.0\.1)$/.test(location.hostname)); }
  // 選んだレースのうち、まだ知らせる意味のあるもの（10分前は締切前・結果は締切から3時間まで）
  function jday(ms) { return new Date(ms + 9 * 3600000).toISOString().slice(0, 10).replace(/-/g, ""); }
  function dlOfBet(rid, e) {
    var m = RID.exec(rid), t = e && /^(\d{1,2}):(\d{2})$/.exec(String(e.d || ""));
    if (!m || !t) return 0;
    return Date.UTC(+m[2].slice(0, 4), +m[2].slice(4, 6) - 1, +m[2].slice(6, 8), +t[1] - 9, +t[2]);
  }
  // その日のまとめに数えるレース（買い目を保存した、今日と先の日のレース）。{rid: 締切}
  function sumRaces(now) {
    var out = {}; if (get(SKEY).off) return out;
    var B = get("dz_bets"), today = jday(now);
    Object.keys(B).forEach(function (rid) {
      var e = B[rid], m = RID.exec(rid);
      if (!m || !e || typeof e !== "object" || !Array.isArray(e.b) || !e.b.length || m[2] < today) return;
      var dl = dlOfBet(rid, e);
      if (dl && jday(dl) === m[2] && dl < now + 3 * 86400000) out[rid] = dl;
    });
    return out;
  }
  function races(now) {
    var R = get(RKEY), S = sumRaces(now), all = {}, out = [];
    Object.keys(R).forEach(function (rid) {
      var e = R[rid], m = RID.exec(rid);
      if (!m || !e || typeof e !== "object") return;
      var dl = +e.dl, mm = e.m ? 1 : 0, kk = e.k ? 1 : 0;
      if (!isFinite(dl)) return;
      if (dl < now - 60000) mm = 0;
      if (dl < now - 3 * 3600000) kk = 0;
      if ((mm || kk) && dl < now + 3 * 86400000) all[rid] = { rid: rid, dl: dl, m: mm, k: kk };
    });
    Object.keys(S).forEach(function (rid) { if (all[rid]) all[rid].s = 1; else all[rid] = { rid: rid, dl: S[rid], m: 0, k: 0, s: 1 }; });
    Object.keys(all).forEach(function (rid) { out.push(all[rid]); });
    out.sort(function (a, b) { return a.dl - b.dl || (a.rid < b.rid ? -1 : 1); });
    return out.slice(0, 60);
  }
  // 付けている推し選手と推しモーター（出走表・モーターのページで付けたもの）。{k, label, on}
  function follows() {
    var F = get(FKEY), out = { p: [], m: [] }, seen = {};
    var O; try { O = JSON.parse(localStorage.getItem("br_oshi") || "[]"); } catch (e) { O = []; }
    (Array.isArray(O) ? O : []).forEach(function (o) {
      var t = o && String(o.toban || ""), k = "p:" + t;
      if (!/^\d{4}$/.test(t) || seen[k]) return; seen[k] = 1;
      out.p.push({ k: k, label: String((o && o.name) || t).replace(/[\s\u3000]+/g, "").slice(0, 12) || t, on: !!F[k] });
    });
    var M; try { M = JSON.parse(localStorage.getItem("dz_oshiMotor") || "{}"); } catch (e) { M = {}; }
    if (M && typeof M === "object" && !Array.isArray(M)) Object.keys(M).sort(function (a, b) { return (+M[b] || 0) - (+M[a] || 0); }).forEach(function (x) {
      var k = "m:" + x, mm = /^(\d{2})_(\d{1,3})$/.exec(x);
      if (!FOL.test(k) || !mm || seen[k]) return; seen[k] = 1;
      out.m.push({ k: k, label: JO[mm[1]] + " " + (+mm[2]) + "号機", on: !!F[k] });
    });
    return out;
  }
  // 送るのは、いまも付けていて、知らせると選んだものだけ
  function fols() { var f = follows(), o = []; f.p.concat(f.m).forEach(function (x) { if (x.on) o.push(x.k); }); return o.sort().slice(0, 40); }
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
      var now = Date.now(), rs = races(now), fs = fols(), sig = JSON.stringify(rs) + (fs.length ? "|" + fs.join(",") : ""), S = get("dz_pushSync");
      if (!force && S.s === sig && now - (+S.t || 0) < 6 * 3600000) return Promise.resolve(null);
      var p = sub ? Promise.resolve(sub) : navigator.serviceWorker.getRegistration("/").then(function (r) { return r ? r.pushManager.getSubscription() : null; });
      return p.then(function (s) {
        if (!s) { del("dz_push"); del("dz_pushSync"); return null; } // 別の端末から引き継いだ印だけが残っている
        var j = s.toJSON();
        return post({ a: "sync", sub: { endpoint: j.endpoint, keys: j.keys }, races: rs, f: fs }).then(function (r) { put("dz_pushSync", { s: sig, t: now }); return r; });
      });
    },
    // いま知らせる予定のレース（10分前・結果を選んだもの。まとめだけのレースは数えない）
    count: function () { return races(Date.now()).filter(function (r) { return r.m || r.k; }).length; },
    // その日のまとめ：受け取るか（既定は受け取る）と、今日数えるレースの数
    sum: function () { return { on: !get(SKEY).off, n: Object.keys(sumRaces(Date.now())).filter(function (r) { return RID.exec(r)[2] === jday(Date.now()); }).length }; },
    toggleS: function () {
      var wasOn = T.state() === "on", off = !!get(SKEY).off;
      if (wasOn && !off) put(SKEY, { off: 1 }); else del(SKEY);
      var turnOn = !wasOn;
      return (turnOn ? T.on() : T.sync(true)).catch(function (err) { if (turnOn && off) put(SKEY, { off: 1 }); throw err; });
    },
    follows: follows,
    // 推し・モーター1つの「出走を知らせる」を切り替える。通知がオフなら、選んでからオンにする
    toggleF: function (k) {
      if (!FOL.test(String(k))) return Promise.reject(new Error("bad"));
      var F = get(FKEY), wasOn = T.state() === "on";
      if (wasOn && F[k]) delete F[k]; else F[k] = 1;
      Object.keys(F).forEach(function (x) { if (!FOL.test(x) || F[x] !== 1) delete F[x]; });
      if (!put(FKEY, F)) return Promise.reject(new Error("save"));
      var turnOn = !wasOn;
      return (turnOn ? T.on() : T.sync(true)).catch(function (err) {
        if (turnOn) { var F2 = get(FKEY); delete F2[k]; put(FKEY, F2); }
        throw err;
      });
    },
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
    // 出走表で買い目を保存したら、1分以内に送り直す（中身が同じなら送らない）
    setInterval(function () { T.paint(); T.sync(false).catch(function () {}); }, 60000);
    setTimeout(function () { T.sync(false).catch(function () {}); }, 1500);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
})();
