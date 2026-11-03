/* 来訪の間隔と頻度を数える（2026-11-03）。
   端末の中だけに「来た日（日本時間の日付）」を最大8件残す。日付以外は保存しない・外へ送らない。
   その日の最初の1ページ目だけ、区分ごとの空ページ /in/kaisu/<区分>/ を見えない枠で開き、
   Cloudflare Web Analytics の表示数として数える。保存できない環境では何もしない。 */
(function () {
  try {
    if (window.top !== window) return;
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
    var open = function () {
      [kankaku, hindo].forEach(function (k) {
        var f = document.createElement("iframe");
        f.src = "/in/kaisu/" + k + "/";
        f.title = "";
        f.setAttribute("aria-hidden", "true");
        f.tabIndex = -1;
        f.style.cssText = "position:absolute;width:1px;height:1px;border:0;left:-9999px;top:0;visibility:hidden";
        document.body.appendChild(f);
        setTimeout(function () { if (f.parentNode) f.parentNode.removeChild(f); }, 15000);
      });
    };
    if (document.readyState === "complete") open();
    else window.addEventListener("load", open);
  } catch (e) { /* 保存できない・ブロックされた環境では何もしない */ }
})();
