/* AI臭さを消す共通の型（実験場の試作・2026-10-09）
   描画後のページに、決まりを機械的にかける。本番ではこのスクリプトを使わず、元ファイルを直す。
   1) 箱のグラデーション → 最初の色の単色（文字のグラデーションは最初の色の文字に）
   2) 角丸 → 4px（小さい札は3px、小さい点はそのまま）
   3) 左の太い色帯 → 上端の細い線
   4) ぼかしの影 → なし
   5) 絵文字・飾りの矢印（末尾の → ›）→ 外す（ボタンの中身が絵文字だけのときは残す）
   6) Helvetica・Arial・等幅などの書体 → 端末の標準書体 */
(function(){
  var EMO = /(?:\p{Extended_Pictographic}|[\u{1F1E6}-\u{1F1FF}])️?|️|‍/gu;
  // 記号として意味を持つもの（評価の星・お気に入りの印・再生・著作権・並べ替えの三角など）は残す
  var KEEP = "\u00A9\u00AE\u2605\u2606\u2665\u2661\u25B6\u25C0\u25B2\u25BC\u25B3\u25BD\u25C6\u25C7\u25A0\u25A1\u25CF\u25CB\u25CE\u2713\u2714\u2715\u2716\u266A\u2122";
  var TAIL = /\s*(?:→|›|»|&rarr;)\s*$/;
  var LEAD = /^\s*(?:→|›)\s*/;
  var FONT = /Helvetica|Arial|Inter|Roboto|Segoe|monospace|Menlo|Consolas|SF Mono|Courier/i;
  var SYS = '-apple-system,"Hiragino Sans","Noto Sans JP",sans-serif';
  var seen = new WeakSet();
  function firstColor(s){ var m = s.match(/rgba?\([^)]*\)/); return m ? m[0] : null; }
  function px(v){ return parseFloat(v) || 0; }
  function styleEl(el){
    if (seen.has(el)) return; seen.add(el);
    var tag = el.tagName;
    if (tag === "HTML" || tag === "BODY" || tag === "SCRIPT" || tag === "STYLE" || el.closest("svg")) return;
    var cs = getComputedStyle(el), r = el.getBoundingClientRect(), w = r.width, h = r.height;
    var bi = cs.backgroundImage;
    if (bi && bi.indexOf("gradient") >= 0 && bi.indexOf("url(") < 0) {
      var c = firstColor(bi);
      var clipText = cs.webkitBackgroundClip === "text" || cs.backgroundClip === "text";
      if (clipText) {
        el.style.setProperty("background-image", "none", "important");
        el.style.setProperty("-webkit-background-clip", "border-box", "important");
        el.style.setProperty("background-clip", "border-box", "important");
        el.style.setProperty("color", c || "#e8ecef", "important");
        el.style.setProperty("-webkit-text-fill-color", c || "#e8ecef", "important");
      } else if (h > 14) {
        el.style.setProperty("background-image", "none", "important");
        var bc = cs.backgroundColor;
        if (c && (bc === "transparent" || /rgba\([^)]*,\s*0\)$/.test(bc))) el.style.setProperty("background-color", c, "important");
      }
    }
    var rad = px(cs.borderTopLeftRadius);
    if (rad > 4) {
      var small = Math.min(w, h);
      if (small > 0 && small <= 14 && rad >= small / 2) { /* 小さい点は丸のまま */ }
      else if (h > 0 && h <= 34 && rad >= h / 2 - 1) el.style.setProperty("border-radius", "3px", "important");
      else el.style.setProperty("border-radius", "4px", "important");
    }
    var bl = px(cs.borderLeftWidth), bt = px(cs.borderTopWidth);
    if (bl >= 3 && bt <= 1 && cs.borderLeftStyle !== "none") {
      var lc = cs.borderLeftColor;
      el.style.setProperty("border-left-width", bt + "px", "important");
      if (bt === 0) el.style.setProperty("border-left-style", "none", "important");
      else el.style.setProperty("border-left-color", cs.borderTopColor, "important");
      el.style.setProperty("box-shadow", "inset 0 3px 0 " + lc, "important");
    } else if (cs.boxShadow && cs.boxShadow !== "none" && cs.boxShadow.indexOf("inset") < 0) {
      el.style.setProperty("box-shadow", "none", "important");
    }
    if (cs.textShadow && cs.textShadow !== "none") el.style.setProperty("text-shadow", "none", "important");
    // 英字の大文字で字間を広げた小見出し（TODAY'S FOCUS など）は外す
    var tx = el.children.length === 0 ? (el.textContent || "").trim() : "";
    var fs = px(cs.fontSize), ls = cs.letterSpacing === "normal" ? 0 : px(cs.letterSpacing);
    if (tx.length >= 4 && /^[A-Z0-9'\u2019&\s.\-\/|]+$/.test(tx) && /[A-Z]{3}/.test(tx) && fs <= 13 && ls >= 1) {
      el.style.setProperty("display", "none", "important"); return;
    }
    // 小さい文字の広すぎる字間を詰める
    if (fs <= 14 && ls > fs * 0.15) el.style.setProperty("letter-spacing", "0.04em", "important");
    // 選択中のボタン・タブの青紫の塗りを、白地に濃い文字へ
    var bg = cs.backgroundColor.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/);
    if (bg && el.matches("button,a,label,[role=tab],[aria-selected=true],[aria-pressed=true],.active,.on,.sel,.is-active,.cur,.current")) {
      var R = +bg[1] / 255, G = +bg[2] / 255, B = +bg[3] / 255, A = bg[4] == null ? 1 : +bg[4];
      var mx = Math.max(R, G, B), mn = Math.min(R, G, B), hue = 0, sat = mx ? (mx - mn) / mx : 0;
      if (mx !== mn) { hue = mx === R ? 60 * (((G - B) / (mx - mn)) % 6) : mx === G ? 60 * ((B - R) / (mx - mn) + 2) : 60 * ((R - G) / (mx - mn) + 4); }
      if (hue < 0) hue += 360;
      var state = el.matches("[aria-selected=true],[aria-pressed=true],.active,.on,.sel,.is-active,.cur,.current");
      var violet = hue >= 240 && hue <= 290;
      if (A >= 0.7 && sat >= 0.35 && mx >= 0.45 && h <= 64 && ((state && hue >= 205 && hue <= 290) || violet)) {
        el.style.setProperty("background-color", "#e8ecef", "important");
        el.style.setProperty("color", "#0a1422", "important");
        el.style.setProperty("border-color", "#e8ecef", "important");
      }
    }
    if (tag !== "H1" && FONT.test(cs.fontFamily)) {
      el.style.setProperty("font-family", SYS, "important");
      el.style.setProperty("font-variant-numeric", "tabular-nums", "important");
    }
  }
  function textPass(root){
    var tw = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null), n, list = [];
    while ((n = tw.nextNode())) list.push(n);
    list.forEach(function(t){
      var p = t.parentElement; if (!p || p.closest("script,style,textarea,svg,code,pre")) return;
      var v = t.nodeValue, nv = v.replace(EMO, function(s){ return KEEP.indexOf(s.charAt(0)) >= 0 ? s.charAt(0) : ""; });
      if (p.matches("a,button") || p.closest("a,button")) nv = nv.replace(TAIL, "").replace(LEAD, "");
      else nv = nv.replace(/\s*→\s*$/, "");
      if (nv === v) return;
      var host = p.closest("a,button,[role=button],[role=tab],label");
      if (!nv.trim() && host && host.textContent.replace(v, "").trim() === "" && !host.getAttribute("aria-label")) return;
      t.nodeValue = nv.replace(/^\s+(?=\S)/, function(s){ return s.indexOf("\n") >= 0 ? s : ""; });
      if (!p.textContent.trim() && !p.children.length && !p.matches("a,button")) p.style.setProperty("display", "none", "important");
    });
  }
  function pass(root){
    textPass(root);
    var els = root.querySelectorAll ? root.querySelectorAll("*") : [];
    for (var i = 0; i < els.length; i++) styleEl(els[i]);
  }
  var busy = false, q = [];
  function run(){ busy = false; var nodes = q; q = []; nodes.forEach(function(n){ if (n.isConnected) pass(n); }); }
  function start(){
    pass(document.body);
    new MutationObserver(function(ms){
      ms.forEach(function(m){
        if (m.type === "characterData") { if (m.target.parentElement) q.push(m.target.parentElement); }
        else m.addedNodes.forEach(function(a){ if (a.nodeType === 1) q.push(a); else if (a.nodeType === 3 && a.parentElement) q.push(a.parentElement); });
      });
      if (!busy && q.length) { busy = true; setTimeout(run, 60); }
    }).observe(document.body, { childList: true, subtree: true, characterData: true });
    window.addEventListener("load", function(){ seen = new WeakSet(); pass(document.body); });
  }
  // <base> を使っているので、ページ内の #見出し へのリンクはここで受けてスクロールする
  document.addEventListener("click", function(e){
    var a = e.target.closest && e.target.closest('a[href^="#"]');
    if (!a) return;
    var id = a.getAttribute("href").slice(1);
    var t = id ? document.getElementById(id) || document.querySelector('[name="' + id + '"]') : null;
    e.preventDefault();
    if (t) t.scrollIntoView({ block: "start" }); else if (!id) window.scrollTo(0, 0);
  }, true);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
