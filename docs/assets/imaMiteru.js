/* 今見ている人数（再訪設計 段階3・2026-11-13）。どのページでも、画面を見ている間だけ2分に1回、/api/now に合図を送る。
   送るのは中身の無い合図だけ（端末の番号・見ているページ・保存した記録は送らない）。人数は接続元ごとに数え、直近5分の実数。
   トップ（#imaLine がある）だけ「いま○人が見ています」を出す。5人未満のときは出さない（サーバーが0を返す）。
   60分操作が無ければ合図をやめる。合図に失敗しても何もしない。読み込みは assets/raihou.js から。 */
(function () {
  if (window.__dzIma) return; window.__dzIma = 1;
  try { if (window.top !== window) return; } catch (e) { return; }
  if (!window.fetch || !(location.protocol === "https:" || /^(localhost|127\.0\.0\.1)$/.test(location.hostname))) return;
  var EVERY = 120000, IDLE = 3600000, last = 0, act = Date.now(), busy = false;
  var KEY = "dzIma"; // 前回の人数（このタブの間だけ・トップの場所取り用）
  function show(n) {
    var el = document.getElementById("imaLine");
    try { sessionStorage.setItem(KEY, JSON.stringify({ n: n, t: Date.now() })); } catch (e) {}
    if (!el) return;
    if (n >= 5) {
      el.textContent = "";
      el.appendChild(document.createTextNode("いま "));
      var b = document.createElement("b"); b.textContent = n.toLocaleString() + "人"; el.appendChild(b);
      el.appendChild(document.createTextNode("が見ています（直近5分）"));
      el.hidden = false;
    } else {
      el.textContent = ""; el.hidden = true;
    }
    el.style.minHeight = "";
  }
  function beat() {
    if (busy || document.visibilityState !== "visible" || Date.now() - act > IDLE) return;
    busy = true; last = Date.now();
    fetch("/api/now", { method: "POST", headers: { "content-type": "text/plain" }, body: "1", cache: "no-store", credentials: "omit" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) { show(d && typeof d.n === "number" && isFinite(d.n) ? Math.floor(d.n) : 0); })
      .catch(function () { show(0); })
      .then(function () { busy = false; });
  }
  ["pointerdown", "keydown", "scroll", "touchstart"].forEach(function (t) {
    window.addEventListener(t, function () { var was = Date.now() - act > IDLE; act = Date.now(); if (was) beat(); }, { passive: true });
  });
  document.addEventListener("visibilitychange", function () { if (document.visibilityState === "visible" && Date.now() - last > 60000) beat(); });
  setInterval(function () { if (Date.now() - last >= EVERY - 1000) beat(); }, 15000);
  beat();
})();
