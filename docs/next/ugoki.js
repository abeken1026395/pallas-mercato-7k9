/* 動きの試作（実験場・2026-10-23）。説明は ugoki.css の頭。
   振動：Android は navigator.vibrate(12)。iPhone は標準の振動が使えないため、
   画面の外に置いた switch 付きのチェックボックスを押して iOS の触覚を出す（iOS 18 以降と推定・設定で切っている人には出ない）。
   振動は押したときだけ。勝手には震えない。 */
(function(){
  var reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var PRESS = ".quick a,.mc,.ni,.cta,.more,.exh,.kn,.guide,.big[role=button],details.race>summary,details.venue>summary,.tab,.dsw-btn,button";

  // 振動。iPhone は標準の振動が使えないので、switch 付きのチェックボックスを押したときの iOS の触覚を借りる。
  // 呼び出し方で効き方が違うため3通り用意し、?shindo=1 で試し分けられるようにする（既定は A）
  //   A：押すたびに label＋switch を作って head に入れ、押して、すぐ消す（ios-haptics の方式）
  //   B：label の中に switch を入れて body に置いたまま、両方を表示しない（web-haptics の方式）
  //   C：B と同じだが、表示しない代わりに画面の隅に1pxで置く
  var test = /[?&]shindo=1/.test(location.search), mode = "A", keepB = null, keepC = null;
  try { mode = sessionStorage.getItem("ugHapticMode") || "A"; } catch (x) {}
  function mk(hidden){
    var l = document.createElement("label"); l.setAttribute("aria-hidden", "true");
    var i = document.createElement("input"); i.type = "checkbox"; i.setAttribute("switch", ""); i.tabIndex = -1;
    if (hidden === "none") { l.style.display = "none"; }
    else if (hidden === "px") { l.style.cssText = "position:fixed;left:0;bottom:0;width:1px;height:1px;overflow:hidden;opacity:.01;pointer-events:none"; }
    l.appendChild(i); return l;
  }
  function hA(){ var l = mk("none"); document.head.appendChild(l); l.click(); document.head.removeChild(l); }
  function hB(){ if (!keepB) { keepB = mk("none"); keepB.firstChild.style.all = "initial"; keepB.firstChild.style.appearance = "auto"; keepB.firstChild.style.display = "none"; document.body.appendChild(keepB); } keepB.click(); }
  function hC(){ if (!keepC) { keepC = mk("px"); document.body.appendChild(keepC); } keepC.click(); }
  function haptic(m){
    try {
      if (typeof navigator.vibrate === "function") { navigator.vibrate(12); return; }
      m = m || mode;
      if (m === "B") hB(); else if (m === "C") hC(); else hA();
    } catch (e) {}
  }
  if (test) {
    var bar = document.createElement("div");
    bar.style.cssText = "position:fixed;left:8px;right:8px;bottom:8px;z-index:9999;display:flex;gap:6px;flex-wrap:wrap;padding:8px;background:#000;color:#fff;font-size:13px;border-radius:4px";
    bar.innerHTML = '<span style="width:100%">振動テスト：ボタンを押して震えたものを教えてください（押すと次からその方式を使う）</span>';
    ["A", "B", "C"].forEach(function(m){
      var b = document.createElement("button"); b.type = "button"; b.textContent = "方式" + m;
      b.style.cssText = "flex:1;min-height:44px;font-size:15px;background:#f2c200;color:#111;border:0;border-radius:4px";
      b.addEventListener("click", function(ev){ ev.stopPropagation(); haptic(m); mode = m; try { sessionStorage.setItem("ugHapticMode", m); } catch (x) {} });
      bar.appendChild(b);
    });
    var add = function(){ document.body.appendChild(bar); };
    if (document.body) add(); else document.addEventListener("DOMContentLoaded", add);
  }

  // ② 手ごたえ：押している間だけ沈む
  document.addEventListener("pointerdown", function(e){
    var el = e.target.closest && e.target.closest(PRESS); if (!el) return;
    el.classList.add("ugP", "ugDown");
    var up = function(){ el.classList.remove("ugDown"); ["pointerup", "pointercancel", "pointerleave"].forEach(function(k){ el.removeEventListener(k, up); }); };
    ["pointerup", "pointercancel", "pointerleave"].forEach(function(k){ el.addEventListener(k, up); });
  }, { passive: true });

  // ② の振動＋③ ページ送り
  document.addEventListener("click", function(e){
    if (e.target.closest && e.target.closest("label[aria-hidden=true]")) return;
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

  // ④ パタパタ：場内の表示板のように、数字の札の上半分が手前に倒れ、新しい下半分が起き上がる。
  // 何度かめくれてから左の桁から順に止まる。押したレースの行の3連単はすぐ、開いた中の払戻は画面に入ったときに1回だけ
  var T = 75; // 半分の札が倒れる時間（ミリ秒）。1回のめくりは 2T
  function half(cls, ch){ var h = document.createElement("span"); h.className = "ugH " + cls; var i = document.createElement("i"); i.textContent = ch; h.appendChild(i); return h; }
  function turn(cell, from, to){
    var st = cell.querySelector(".ugS"); st.textContent = to;
    var ob = half("ugBot", from), ot = half("ugTop ugFall", from), nb = half("ugBot ugRise", to);
    cell.appendChild(ob); cell.appendChild(ot); cell.appendChild(nb);
    setTimeout(function(){ ob.remove(); ot.remove(); nb.remove(); }, T * 2 + 20);
  }
  function flap(el){
    if (!el || el.__ugFl || reduce) return;
    var orig = el.innerHTML, txt = el.textContent;
    if (!/\d/.test(txt)) return;
    el.__ugFl = 1;
    var finals = [];
    el.innerHTML = Array.prototype.map.call(txt, function(c){
      if (/\d/.test(c)) { finals.push(c); return '<span class="ugC"><span class="ugS">' + c + "</span></span>"; }
      return c.replace(/[&<>]/g, function(x){ return { "&": "&amp;", "<": "&lt;", ">": "&gt;" }[x]; });
    }).join("");
    el.classList.add("ugBoard");
    var cs = el.querySelectorAll(".ugC"), cur = finals.slice(), n = 0, START = 4;
    var timer = setInterval(function(){
      n++;
      for (var i = 0; i < cs.length; i++) {
        if (cs[i].__done) continue;
        var to = n >= START + i * 2 ? finals[i] : String((+cur[i] + 1 + Math.floor(Math.random() * 8)) % 10);
        if (n >= START + i * 2) cs[i].__done = 1;
        turn(cs[i], cur[i], to); cur[i] = to;
      }
      if (n >= START + (cs.length - 1) * 2 + 1) {
        clearInterval(timer);
        setTimeout(function(){ el.innerHTML = orig; el.classList.remove("ugBoard"); el.__ugFl = 0; }, T * 2 + 60);
      }
    }, T * 2 + 10);
  }
  var io = ("IntersectionObserver" in window) ? new IntersectionObserver(function(es){
    es.forEach(function(en){ if (en.isIntersecting) { io.unobserve(en.target); flap(en.target); } });
  }, { threshold: 0.6 }) : null;
  document.addEventListener("toggle", function(e){
    var d = e.target;
    if (!d || !d.matches || !d.matches("details.race") || !d.open || reduce) return;
    flap(d.querySelector("summary .rpay"));
    setTimeout(function(){
      var amts = d.querySelectorAll(".pays .amt");
      for (var i = 0; i < amts.length; i++) { if (io) io.observe(amts[i]); else flap(amts[i]); }
    }, 0);
  }, true);
})();
