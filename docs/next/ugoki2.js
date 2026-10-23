/* 動き 第2版（実験場・2026-10-23）。第1版 ugoki.js に、開閉・タブ・★・保存・リンク・一覧・バーの細かい動きを足したもの。説明は ugoki2.css の頭。 */
/* 動きの試作（実験場・2026-10-23）。説明は ugoki.css の頭。
   振動：タップしたときだけ震える。スライドやスクロールでは震えない・画面送りも止めない。
   Android は navigator.vibrate(12)。iPhone は下の「iPhone の振動」の仕組み（設定で触覚を切っている人には出ない）。 */
(function(){
  var reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  // 押せる部品：トップと結果の部品に加え、どのページでも使えるようにリンク・ボタン・開閉・タブ全般
  var PRESS = ".quick a,.mc,.ni,.cta,.more,.exh,.kn,.guide,.big[role=button],details.race>summary,details.venue>summary,.tab,.dsw-btn,button,a[href],summary,[role=button],[role=tab],[onclick]";

  // iPhone の振動（2026-10-23 確定版）。
  // Safari には振動の命令が無いので、switch 付きのチェックボックスが切り替わるときの iOS の触覚を借りる。
  // iOS 26.5 から、プログラムで押した切り替えでは震えない。本物の指のタップが要る。
  // ただしスイッチを指の下に置くと、WebKit がそのタッチを処理済みにして画面のスクロールを止めてしまう（けん「スライドできない」）。
  // そこで ios-haptics（2026-09-22 の修正）と同じ形にする：
  //   押せる部品の上に透明な <label> を重ね、その中のスイッチは 1px・visibility:hidden で指の下に置かない。
  //   タップ → label が本物のクリックをスイッチへ渡す → スイッチが切り替わって震える。
  //   スライド → 指はスイッチに触れないので、そのまま画面が送れる。
  // label の中のクリックは下の部品に el.click() で渡す（リンク・開閉・ボタンは本来の動きになる）。
  // 押せる部品が入れ子のときは、内側にだけ重ねる（外側の label が内側を覆わないように）。
  var IOS_OVERLAY = typeof navigator.vibrate !== "function" && "switch" in HTMLInputElement.prototype;
  function cover(el){
    if (el.__ugSw || !el.isConnected) return;
    if (el.closest("label,select,textarea,[contenteditable]") || el.querySelector("input,select,textarea")) return; // 入力欄を含む部品には重ねない
    if (el.querySelector(PRESS)) return; // 内側に押せる部品があれば、内側に任せる
    el.__ugSw = 1;
    // 先に外側へ重ねていたら外す（後から中身が読み込まれたとき）
    for (var a = el.parentElement; a && a !== document.body; a = a.parentElement) {
      if (a.__ugLab) { a.__ugLab.remove(); a.__ugLab = null; }
    }
    if (getComputedStyle(el).position === "static") el.style.position = "relative";
    var lab = document.createElement("label");
    lab.className = "ugSwCover"; lab.setAttribute("aria-hidden", "true");
    var sw = document.createElement("input");
    sw.type = "checkbox"; sw.setAttribute("switch", ""); sw.tabIndex = -1;
    // label からスイッチへ渡る2回目のクリックは、下の部品に届けない
    sw.addEventListener("click", function(ev){ ev.stopPropagation(); });
    lab.addEventListener("click", function(ev){
      if (ev.target !== lab) return;
      ev.stopPropagation(); // label のクリックそのものは止め、下の部品を押し直す（preventDefault はしない：スイッチが切り替わらず震えなくなる）
      el.click();
    });
    lab.appendChild(sw); el.appendChild(lab); el.__ugLab = lab;
  }
  // 重ねる作業は、閉じた開閉の中を飛ばし（開いたときに重ねる）、150個ずつ区切って読み込みを止めないようにする（けん「動きが遅い」）
  function closedIn(el){ var d = el.closest("details:not([open])"); if (!d) return false; var sm = d.querySelector(":scope > summary"); return !(sm && sm.contains(el)); }
  function coverAll(root){
    if (!IOS_OVERLAY || !root.querySelectorAll) return;
    var els = Array.prototype.slice.call(root.querySelectorAll(PRESS));
    if (root.matches && root.matches(PRESS)) els.unshift(root);
    var i = 0;
    (function chunk(){
      var end = Math.min(i + 150, els.length);
      for (; i < end; i++) { var e = els[i]; if (!e.__ugSw && !closedIn(e)) cover(e); }
      if (i < els.length) setTimeout(chunk, 0);
    })();
  }
  document.addEventListener("toggle", function(e){ if (IOS_OVERLAY && e.target && e.target.tagName === "DETAILS" && e.target.open) coverAll(e.target); }, true);
  if (IOS_OVERLAY) {
    var startCover = function(){
      coverAll(document.body);
      new MutationObserver(function(ms){ ms.forEach(function(m){ m.addedNodes.forEach(function(n){ if (n.nodeType === 1 && !n.classList.contains("ugSwCover")) coverAll(n); }); }); })
        .observe(document.body, { childList: true, subtree: true });
    };
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", startCover); else startCover();
  }
  // Android の振動（クリック＝指を離したタップのときだけ呼ばれる）。iPhone は label の仕組みで震えるので何もしない
  function haptic(){
    try { if (typeof navigator.vibrate === "function") navigator.vibrate(12); } catch (e) {}
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
    if (e.target.closest && e.target.closest(".ugSwCover")) return; // label のクリックは label 側で処理済み
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
  // 何度かめくれてから左の桁から順に止まる。画面の外の数字は、画面に入ったときに1回だけ
  var T = 75; // 半分の札が倒れる時間（ミリ秒）。1回のめくりは 2T
  function half(cls, ch){ var h = document.createElement("span"); h.className = "ugH " + cls; var i = document.createElement("i"); i.textContent = ch; h.appendChild(i); return h; }
  function turn(cell, from, to){
    var st = cell.querySelector(".ugS"); st.textContent = to;
    var ob = half("ugBot", from), ot = half("ugTop ugFall", from), nb = half("ugBot ugRise", to);
    cell.appendChild(ob); cell.appendChild(ot); cell.appendChild(nb);
    setTimeout(function(){ ob.remove(); ot.remove(); nb.remove(); }, T * 2 + 20);
  }
  // 元の文字には手を触れず（React などで作られた数字も壊さない）、同じ書体の札を真上に重ねてめくり、止まったら外す
  function flap(el){
    if (!el || el.__ugFl || reduce || !el.isConnected) return;
    var txt = el.textContent.trim();
    if (!/\d/.test(txt)) return;
    var rg = document.createRange(); rg.selectNodeContents(el);
    var rr = rg.getBoundingClientRect(); if (!rr.width || !rr.height) return;
    el.__ugFl = 1;
    var cs = getComputedStyle(el);
    var bgc = "transparent", p = el;
    while (p && p !== document.documentElement) { var b = getComputedStyle(p).backgroundColor; if (b && b !== "transparent" && !/rgba\([^)]*,\s*0\)$/.test(b)) { bgc = b; break; } p = p.parentElement; }
    if (bgc === "transparent") bgc = getComputedStyle(document.body).backgroundColor;
    var ov = document.createElement("span"), finals = [];
    ov.className = "ugBoard"; ov.setAttribute("aria-hidden", "true");
    ov.style.cssText = "position:absolute;z-index:60;pointer-events:none;margin:0;padding:0;white-space:nowrap;display:block";
    ["fontFamily", "fontSize", "fontWeight", "fontStyle", "letterSpacing", "fontVariantNumeric", "fontFeatureSettings"].forEach(function(k){ ov.style[k] = cs[k]; });
    ov.style.color = cs.webkitTextFillColor && cs.webkitTextFillColor !== cs.color && !/rgba\([^)]*,\s*0\)$/.test(cs.webkitTextFillColor) ? cs.webkitTextFillColor : cs.color;
    ov.style.left = (rr.left + window.scrollX) + "px"; ov.style.top = (rr.top + window.scrollY) + "px";
    ov.style.height = rr.height + "px"; ov.style.lineHeight = rr.height + "px";
    ov.style.setProperty("--ugBg", bgc);
    ov.innerHTML = Array.prototype.map.call(txt, function(c){
      if (/\d/.test(c)) { finals.push(c); return '<span class="ugC"><span class="ugS">' + c + "</span></span>"; }
      return c.replace(/[&<>]/g, function(x){ return { "&": "&amp;", "<": "&lt;", ">": "&gt;" }[x]; });
    }).join("");
    document.body.appendChild(ov);
    var prevC = el.style.getPropertyValue("color"), prevCP = el.style.getPropertyPriority("color");
    var prevF = el.style.getPropertyValue("-webkit-text-fill-color"), prevFP = el.style.getPropertyPriority("-webkit-text-fill-color");
    el.style.setProperty("color", "transparent", "important"); el.style.setProperty("-webkit-text-fill-color", "transparent", "important");
    var cells = ov.querySelectorAll(".ugC"), cur = finals.slice(), n = 0, START = 4;
    for (var k = 0; k < cells.length; k++) cells[k].style.width = cells[k].getBoundingClientRect().width + "px";
    function done(){
      ov.remove();
      if (prevC) el.style.setProperty("color", prevC, prevCP); else el.style.removeProperty("color");
      if (prevF) el.style.setProperty("-webkit-text-fill-color", prevF, prevFP); else el.style.removeProperty("-webkit-text-fill-color");
      el.__ugFl = 0;
    }
    var timer = setInterval(function(){
      if (!el.isConnected) { clearInterval(timer); done(); return; }
      n++;
      for (var i = 0; i < cells.length; i++) {
        if (cells[i].__done) continue;
        var to = n >= START + i * 2 ? finals[i] : String((+cur[i] + 1 + Math.floor(Math.random() * 8)) % 10);
        if (n >= START + i * 2) cells[i].__done = 1;
        turn(cells[i], cur[i], to); cur[i] = to;
      }
      if (n >= START + (cells.length - 1) * 2 + 1) { clearInterval(timer); setTimeout(done, T * 2 + 60); }
    }, T * 2 + 10);
  }
  var io = ("IntersectionObserver" in window) ? new IntersectionObserver(function(es){
    es.forEach(function(en){ if (en.isIntersecting) { io.unobserve(en.target); flap(en.target); } });
  }, { threshold: 0.6 }) : null;
  // ④ をどのページでも：タップで開いた・切り替わったときに新しく見えた数字だけがパタパタする（2026-10-23 けん「他ページにも動きを」）。
  // 結果ページは場のタブを開いた時点で、並んだレースの払戻がめくれる（けん「場タブ開いた時点の数字から」）。
  // ページを開いただけ・スクロールしただけでは動かさない。読み込み後に遅れて出た数字も動かさない。
  var NUM = /^[¥￥]?\d[\d,]*(?:\.\d+)?\s*(?:%|％|円|倍|回|位|本|件|走|勝|機|人|R)?$/;
  var MAXF = 30, seen = new WeakSet();
  // 数字の葉は一度だけ全体を数え、あとは足された部分だけ数え足す（タップのたびに全要素を走査しない）
  var leaves = null, addQ = [], gone = false;
  var LSKIP = "a,button,select,option,textarea,script,style,.kataTitle,.kataNote,.ugBoard,svg";
  var LTAG = { A: 1, BUTTON: 1, SELECT: 1, OPTION: 1, TEXTAREA: 1, SCRIPT: 1, STYLE: 1, svg: 1, SVG: 1 };
  function skipEl(n){ var c = n.classList; return LTAG[n.tagName] || c.contains("kataTitle") || c.contains("kataNote") || c.contains("ugBoard"); }
  function isLeaf(e){ // 親の判定（LSKIP）は集めるときに枝ごと済ませてある
    if (e.firstElementChild || e.__ugFl) return false;
    var f = e.firstChild; if (!f) return false;
    var t = f === e.lastChild && f.nodeType === 3 ? f.nodeValue : e.textContent; if (!t || t.length > 14) return false;
    t = t.trim(); return NUM.test(t) && (t.match(/\d/g) || []).length >= 2;
  }
  function scanInto(root, out){
    if (root.nodeType !== 1 || root.closest(LSKIP)) return;
    if (isLeaf(root)) { out.push(root); return; }
    var w = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT, { acceptNode: function(n){
      if (skipEl(n)) return NodeFilter.FILTER_REJECT;
      return n.firstElementChild ? NodeFilter.FILTER_SKIP : NodeFilter.FILTER_ACCEPT; } });
    var n; while ((n = w.nextNode())) if (isLeaf(n)) out.push(n);
  }
  function numLeaves(){
    if (!leaves) { leaves = []; addQ = []; gone = false; scanInto(document.body, leaves); return leaves; }
    if (addQ.length) {
      var q = addQ; addQ = [];
      var roots = q.filter(function(n){ return n.isConnected && !q.some(function(o){ return o !== n && o.contains(n); }); });
      var got = new Set(leaves);
      roots.forEach(function(r){ var tmp = []; scanInto(r, tmp); tmp.forEach(function(e){ if (!got.has(e)) { got.add(e); leaves.push(e); } }); });
    }
    if (gone) { gone = false; leaves = leaves.filter(function(e){ return e.isConnected; }); }
    return leaves;
  }
  new MutationObserver(function(ms){
    if (!leaves) return;
    ms.forEach(function(m){
      if (m.type === "characterData") { var pe = m.target.parentElement; if (pe) addQ.push(pe); return; }
      if (m.removedNodes.length) gone = true;
      m.addedNodes.forEach(function(n){ if (n.nodeType === 1) { if (!n.classList.contains("ugBoard") && !n.classList.contains("ugSwCover")) addQ.push(n); } else if (n.parentElement) addQ.push(n.parentElement); });
    });
  }).observe(document.documentElement, { childList: true, subtree: true, characterData: true });
  // 最初の数え上げは、読み込みが落ち着いて手が空いたときに済ませておく
  if (!reduce) window.addEventListener("load", function(){ (window.requestIdleCallback || function(f){ setTimeout(f, 1500); })(function(){ numLeaves(); }, { timeout: 4000 }); });
  // 閉じた開閉の中は、大きさが取れても見えていない扱い（Chromium は閉じた details の中身にも大きさを返す）
  function shown(e){
    if (e.checkVisibility && !e.checkVisibility({ visibilityProperty: true })) return false;
    for (var d = e.closest("details"); d; d = d.parentElement && d.parentElement.closest("details")) {
      if (!d.open) { var sm = d.querySelector(":scope > summary"); if (!sm || !sm.contains(e)) return false; }
    }
    var r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0;
  }
  function strong(e){ var cs = getComputedStyle(e); return (parseInt(cs.fontWeight, 10) >= 600 || parseFloat(cs.fontSize) >= 15) && cs.visibility !== "hidden"; }
  function markSeen(){ var l = numLeaves(); for (var i = 0; i < l.length; i++) if (shown(l[i])) seen.add(l[i]); }
  function flapNew(){
    var l = numLeaves(), n = 0;
    for (var i = 0; i < l.length && n < MAXF; i++) {
      var e = l[i]; if (seen.has(e) || !isLeaf(e) || !shown(e)) continue;
      seen.add(e);
      if (!strong(e)) continue;
      n++;
      var r = e.getBoundingClientRect();
      if (r.bottom > 0 && r.top < innerHeight) flap(e); else if (io) io.observe(e);
    }
  }
  if (!reduce) {
    // 指を置いた時点で見えている数字を「既に見た」に入れ、タップのあとに新しく見えた数字だけを動かす
    document.addEventListener("pointerdown", function(){ markSeen(); }, { capture: true, passive: true });
    document.addEventListener("click", function(e){
      if (!e.target.closest || !e.target.closest(PRESS)) return;
      setTimeout(flapNew, 200); setTimeout(flapNew, 450); // 開いた中身の降りる動き（160ms）が終わってから札を重ねる
    }, true);
    document.addEventListener("keydown", function(e){ if (e.key === "Enter" || e.key === " ") markSeen(); }, true);
  }

  // ===== 第2版で足した細かい動き（押した・開いた・切り替わった瞬間だけ） =====
  if (!reduce) (function(){
    var lastTap = 0;
    document.addEventListener("click", function(e){ if (e.isTrusted) lastTap = Date.now(); }, true);
    document.addEventListener("keydown", function(e){ if (e.key === "Enter" || e.key === " ") lastTap = Date.now(); }, true);
    function anim(el, cls, ms){ el.classList.remove(cls); void el.offsetWidth; el.classList.add(cls); setTimeout(function(){ el.classList.remove(cls); }, ms + 60); }
    function visible(el){ var r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; }
    // ⑦ 新しく出たバーの塗り（中身なし・高さ8px以下・幅を % で持つ・色付き）
    function growBars(root){
      var els = Array.prototype.slice.call(root.querySelectorAll('[style*="width"]')); // 幅を style で持つ部品だけを見る
      if (root.matches && root.matches('[style*="width"]')) els.unshift(root);
      for (var i = 0; i < els.length; i++) {
        var e = els[i]; if (e.children.length || (e.textContent || "").trim()) continue;
        var st = e.getAttribute("style") || "";
        if (!/width:\s*[\d.]+%/.test(st)) continue;
        var r = e.getBoundingClientRect(); if (!r.width || r.height > 8 || r.height < 2) continue;
        var bg = getComputedStyle(e).backgroundColor; if (!bg || /rgba\([^)]*,\s*0\)$/.test(bg) || bg === "transparent") continue;
        anim(e, "ugGrow", 250);
      }
    }
    // ① 開閉：details が開いたら中身が降りてくる
    document.addEventListener("toggle", function(e){
      var d = e.target; if (!d || d.tagName !== "DETAILS" || !d.open || Date.now() - lastTap > 800) return;
      for (var i = 0; i < d.children.length; i++) { var c = d.children[i]; if (c.tagName !== "SUMMARY") { anim(c, "ugDrop", 160); growBars(c); } }
    }, true);
    // ①⑥⑦ 押したあとに足された中身：少なければ降りてくる、多ければ（一覧の入れ替え）薄い状態から濃く
    var pend = [], t = null;
    new MutationObserver(function(ms){
      if (Date.now() - lastTap > 700) return;
      ms.forEach(function(m){ m.addedNodes.forEach(function(n){ if (n.nodeType === 1 && !n.classList.contains("ugSwCover") && !n.classList.contains("ugBoard") && !n.classList.contains("ugTabBar") && !n.closest(".ugBoard,.kataNote")) pend.push(n); }); });
      if (!t) t = setTimeout(function(){
        t = null; var list = pend.filter(function(n){ return n.isConnected && visible(n) && !pend.some(function(o){ return o !== n && o.contains(n); }); }); pend = [];
        if (!list.length) return;
        var many = list.length > 8;
        list.slice(0, 60).forEach(function(n){ anim(n, many ? "ugFade" : "ugDrop", many ? 120 : 160); growBars(n); });
      }, 0);
    }).observe(document.body, { childList: true, subtree: true });
    // ② タブ：選ばれていた見た目の兄弟から、押した部品へ金の線が滑る
    function looksSelected(el){
      if (el.getAttribute("aria-selected") === "true" || el.getAttribute("aria-pressed") === "true") return true;
      if (/(^|\s)(on|active|sel|selected|cur|current|is-active)(\s|$)/.test(el.className || "")) return true;
      var b = getComputedStyle(el).backgroundColor.match(/\d+(\.\d+)?/g);
      if (b && +(b[3] == null ? 1 : b[3]) > 0.5) { var r = +b[0], g = +b[1], bl = +b[2]; if (r > 150 && g > 120 && bl < 120) return true; } // 金・黄の地
      return false;
    }
    function tabGroup(el){
      var p = el.parentElement; if (!p) return null;
      var sib = Array.prototype.filter.call(p.children, function(c){ return c.tagName === el.tagName && visible(c); });
      if (sib.length < 2 || sib.length > 12) return null;
      var r = el.getBoundingClientRect(), pr = p.getBoundingClientRect();
      if (r.height > 60 || r.width > pr.width * 0.6) return null;
      return sib;
    }
    var before = null;
    document.addEventListener("pointerdown", function(e){
      before = null;
      var el = e.target.closest && e.target.closest("button,[role=tab],.tab,.dsw-btn,a,[role=button]"); if (!el) return;
      var sib = tabGroup(el); if (!sib) return;
      var old = sib.filter(function(c){ return c !== el && looksSelected(c); })[0];
      if (old) before = { el: el, old: old, r: old.getBoundingClientRect() };
    }, { capture: true, passive: true });
    document.addEventListener("click", function(e){
      var b = before; before = null; if (!b) return;
      var el = e.target.closest && e.target.closest("button,[role=tab],.tab,.dsw-btn,a,[role=button]"); if (el !== b.el) return;
      setTimeout(function(){
        if (!b.el.isConnected) return;
        var nr = b.el.getBoundingClientRect(); if (!nr.width) return;
        var bar = document.createElement("div"); bar.className = "ugTabBar";
        bar.style.left = (b.r.left + scrollX) + "px"; bar.style.top = (b.r.bottom + scrollY - 2) + "px"; bar.style.width = b.r.width + "px";
        document.body.appendChild(bar); void bar.offsetWidth;
        bar.style.left = (nr.left + scrollX) + "px"; bar.style.top = (nr.bottom + scrollY - 2) + "px"; bar.style.width = nr.width + "px";
        setTimeout(function(){ bar.style.opacity = "0"; }, 260);
        setTimeout(function(){ bar.remove(); }, 450);
      }, 20);
    }, true);
    // ③ ★・♥・フォロー：一瞬ふくらむ
    document.addEventListener("click", function(e){
      var el = e.target.closest && e.target.closest("button,[role=button],a,span,div"); if (!el) return;
      var tx = (el.textContent || "").trim(), lab = (el.getAttribute("aria-label") || "") + (el.title || "");
      if (/^[★☆♥♡]/.test(tx) && tx.length <= 6 || /推し|フォロー/.test(lab) || (/フォロー/.test(tx) && tx.length <= 8)) {
        var g = el.querySelector && el.children.length ? (Array.prototype.find.call(el.querySelectorAll("*"), function(c){ return /^[★☆♥♡]$/.test((c.textContent || "").trim()); }) || el) : el;
        anim(g, "ugPop", 180);
      }
    }, true);
    // ④ 保存のボタン：入れない。選手カードの「画像を保存」は、ページ自身が下に結果の文を出すため（二重になる）
    // ⑤ 文章中のリンク（ボタン・札・タイルでないもの）に印を付ける
    function markLinks(root){
      var as = root.querySelectorAll ? root.querySelectorAll("a[href]") : [];
      for (var i = 0; i < as.length; i++) {
        var a = as[i]; if (a.__ugL) continue; a.__ugL = 1;
        var s = getComputedStyle(a);
        if (s.display.indexOf("inline") === 0 && !a.querySelector("img,svg,div") && (a.textContent || "").trim().length > 0 && !(parseFloat(s.paddingTop) > 4)) a.classList.add("ugTxtLink");
      }
    }
    var startL = function(){ markLinks(document.body); new MutationObserver(function(ms){ ms.forEach(function(m){ m.addedNodes.forEach(function(n){ if (n.nodeType === 1) markLinks(n); }); }); }).observe(document.body, { childList: true, subtree: true }); };
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", startL); else startL();
  })();
})();
