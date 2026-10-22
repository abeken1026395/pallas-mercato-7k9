/* 動きの試作（実験場・2026-10-23）。説明は ugoki.css の頭。
   振動：Android は navigator.vibrate(12)。iPhone は標準の振動が使えないため、
   画面の外に置いた switch 付きのチェックボックスを押して iOS の触覚を出す（iOS 18 以降と推定・設定で切っている人には出ない）。
   振動は押したときだけ。勝手には震えない。 */
(function(){
  var reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var PRESS = ".quick a,.mc,.ni,.cta,.more,.exh,.kn,.guide,.big[role=button],details.race>summary,details.venue>summary,.tab,.dsw-btn,button";

  // 振動（web-haptics と同じ組み方：label の中に switch 付きの input を入れ、両方とも表示しない。label を押すと iOS の触覚が出る）
  // ?shindo=1 を付けて開くと、本物のスイッチを画面の左下に出す。それを指で押して震えなければ、端末の設定で触覚が切れている
  var lab = null, test = /[?&]shindo=1/.test(location.search);
  function iosSwitch(){
    if (lab) return lab;
    lab = document.createElement("label");
    lab.setAttribute("for", "ugSw");
    lab.setAttribute("aria-hidden", "true");
    var sw = document.createElement("input");
    sw.type = "checkbox"; sw.setAttribute("switch", ""); sw.id = "ugSw"; sw.tabIndex = -1;
    sw.style.all = "initial"; sw.style.appearance = "auto";
    if (test) {
      lab.textContent = "振動テスト ";
      lab.style.cssText = "position:fixed;left:10px;bottom:10px;z-index:9999;padding:8px 12px;background:#000;color:#fff;font-size:14px;border-radius:4px";
    } else {
      lab.style.display = "none"; sw.style.display = "none";
    }
    lab.appendChild(sw); document.body.appendChild(lab);
    return lab;
  }
  function haptic(){
    try {
      if (typeof navigator.vibrate === "function") { navigator.vibrate(12); return; }
      iosSwitch().click();
    } catch (e) {}
  }
  if (test) { if (document.body) iosSwitch(); else document.addEventListener("DOMContentLoaded", iosSwitch); }

  // ② 手ごたえ：押している間だけ沈む
  document.addEventListener("pointerdown", function(e){
    var el = e.target.closest && e.target.closest(PRESS); if (!el) return;
    el.classList.add("ugP", "ugDown");
    var up = function(){ el.classList.remove("ugDown"); ["pointerup", "pointercancel", "pointerleave"].forEach(function(k){ el.removeEventListener(k, up); }); };
    ["pointerup", "pointercancel", "pointerleave"].forEach(function(k){ el.addEventListener(k, up); });
  }, { passive: true });

  // ② の振動＋③ ページ送り
  document.addEventListener("click", function(e){
    if (e.target.closest && e.target.closest("#ugSw,label[for=ugSw]")) return;
    var el = e.target.closest && e.target.closest(PRESS);
    if (el) haptic();
    var a = e.target.closest && e.target.closest("a[href]");
    if (!a || reduce || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    if (a.target && a.target !== "_self") return;
    var url; try { url = new URL(a.href, location.href); } catch (x) { return; }
    if (url.origin !== location.origin) return;
    if (url.pathname === location.pathname && url.search === location.search) return; // 同じページ内
    e.preventDefault();
    try { sessionStorage.setItem("ugEnter", "1"); } catch (x) {}
    document.documentElement.classList.add("ugLeave");
    setTimeout(function(){ location.href = url.href; }, 170);
  });
  // 戻るで帰ってきたときに消えたままにしない
  window.addEventListener("pageshow", function(){ document.documentElement.classList.remove("ugLeave"); });
  // 試作どうしの移動で来たときだけ、右から入る
  try {
    if (sessionStorage.getItem("ugEnter") === "1") {
      sessionStorage.removeItem("ugEnter");
      document.documentElement.classList.add("ugEnter");
      setTimeout(function(){ document.documentElement.classList.remove("ugEnter"); }, 400);
    }
  } catch (x) {}

  // ④ 裏返し：結果のレースを開いたとき、払戻の升を順に裏返す
  document.addEventListener("toggle", function(e){
    var d = e.target;
    if (!d || !d.matches || !d.matches("details.race") || !d.open || reduce) return;
    setTimeout(function(){
      var cells = d.querySelectorAll(".pays .pcell");
      for (var i = 0; i < cells.length; i++) {
        var c = cells[i];
        if (c.parentNode) c.parentNode.classList.add("ugFlipHost");
        c.classList.remove("ugFlip"); void c.offsetWidth;
        c.style.animationDelay = (i * 45) + "ms";
        c.classList.add("ugFlip");
      }
    }, 0);
  }, true);
})();
