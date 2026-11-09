/* 来訪の計測（第2版・2026-11-10）。端末の中に残すのは「来た日（日本時間の日付）」最大8件と、入口から移ってきた印（1回で消す）だけ。外へは送らない。
   数え方：区分ごとの空ページ /in/kaisu/<区分>/ ・ /in/c/<入口>/ を見えない枠で開き、Cloudflare Web Analytics の表示数として数える。
   1) 入口から来た：入口ページ（/in/line/ など）は開いた瞬間に移り、印（sessionStorage の dzIn）だけを残す。移った先のこのファイルが /in/c/<入口>/ を1回開く
   2) 来訪の間隔と頻度：その日の最初の1ページ目だけ、/in/kaisu/ の2区分を開く（第1版と同じ）
   3) 外の LINE へ出る入口（/in/top/… ・ /in/yosou/）を押したとき：押した側のページで /in/c/<入口>/ を開く
   保存できない環境では何もしない。 */
(function () {
  var opens = [];
  function frame(p) {
    var f = document.createElement("iframe");
    f.src = p;
    f.title = "";
    f.setAttribute("aria-hidden", "true");
    f.tabIndex = -1;
    f.style.cssText = "position:absolute;width:1px;height:1px;border:0;left:-9999px;top:0;visibility:hidden";
    document.body.appendChild(f);
    setTimeout(function () { if (f.parentNode) f.parentNode.removeChild(f); }, 15000);
  }
  var NAME = /^[a-z0-9-]+(\/[a-z0-9-]+)?$/;
  try {
    if (window.top !== window) return;
    try {
      var src = sessionStorage.getItem("dzIn");
      if (src !== null) {
        sessionStorage.removeItem("dzIn");
        if (NAME.test(src)) opens.push("/in/c/" + src + "/");
      }
    } catch (e) { /* 印が読めない環境では入口を数えない */ }
    (function () {
      var KEY = "dzRaihou";
      var DAY = 86400000;
      var today = new Date(Date.now() + 9 * 3600000).toISOString().slice(0, 10);
      var raw = localStorage.getItem(KEY);
      var list = [];
      if (raw) {
        try { list = JSON.parse(raw).d || []; } catch (e) { list = []; }
      }
      list = list.filter(function (s) { return /^\d{4}-\d{2}-\d{2}$/.test(s); });
      if (list.indexOf(today) >= 0) return;
      list.sort();
      var t0 = Date.parse(today + "T00:00:00Z");
      var kankaku;
      if (!list.length) {
        kankaku = "hajime";
      } else {
        var gap = Math.round((t0 - Date.parse(list[list.length - 1] + "T00:00:00Z")) / DAY);
        kankaku = gap <= 1 ? "zenjitsu" : (gap <= 6 ? "2to6" : "7ijo");
      }
      list.push(today);
      list = list.slice(-8);
      localStorage.setItem(KEY, JSON.stringify({ d: list }));
      if (localStorage.getItem(KEY) === null) return;
      var n = list.filter(function (s) { return t0 - Date.parse(s + "T00:00:00Z") < 7 * DAY; }).length;
      var hindo = n >= 7 ? "hindo7" : (n >= 4 ? "hindo4to6" : (n >= 2 ? "hindo2to3" : "hindo1"));
      opens.push("/in/kaisu/" + kankaku + "/", "/in/kaisu/" + hindo + "/");
    })();
  } catch (e) { /* 保存できない・ブロックされた環境では何もしない */ }
  try {
    document.addEventListener("click", function (ev) {
      var a = ev.target && ev.target.closest && ev.target.closest("a[href]");
      if (!a || a.host !== location.host) return;
      var m = /^\/in\/((?:top\/[a-z0-9-]+)|yosou)\/?$/.exec(a.pathname || "");
      if (m) frame("/in/c/" + m[1] + "/");
    }, true);
  } catch (e) { /* 何もしない */ }
  if (!opens.length) return;
  var go = function () { opens.forEach(frame); };
  if (document.readyState === "complete") go();
  else window.addEventListener("load", go);
})();
