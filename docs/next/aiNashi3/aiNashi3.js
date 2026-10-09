/* AI臭さを消す型 第3案（実験場の試作・2026-10-09）
   第2案に加えて：黒に近い面を全部トップと同じ紺に持ち上げる（暗さの解消）、
   色で塗った小さい札は枠線だけにする（F1の表のように色を絞る）、大きい数字は極太書体（F1の数字の効かせ方）、
   薄すぎる灰色の文字を明るく、ページの頭に1から6号艇の枠色の帯（サイトだけの持ち物・The Pudding の考え方）
   第1案に加えて：箱をやめて線で区切る（日経ビジュアルデータの紙面型）、見出しを極太書体に（F1の書体の効かせ方）、
   選択中は大時計の針の黄色、背景はトップと同じく上から下へ暗くなる形を全ページに
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
        el.style.setProperty("background-color", "#f2c200", "important");
        el.style.setProperty("color", "#111111", "important");
        el.style.setProperty("border-color", "#f2c200", "important");
      }
    }
    // 大きい箱は背景と枠をやめ、下の線1本で区切る（中身の札・ボタン・表の行は対象外）
    if (!el.matches("input,select,textarea,td,th,tr,thead,tbody,table,img,canvas,[role=tab]") && (el.children.length >= 2 || el.matches("a,button,details,summary")) && h >= 48) {
      var pw = el.parentElement ? el.parentElement.getBoundingClientRect().width : w;
      var bgc = cs.backgroundColor.match(/rgba?\(([^)]*)\)/);
      var al = bgc ? (bgc[1].split(",")[3] == null ? 1 : +bgc[1].split(",")[3]) : 0;
      if (al > 0.3 && pw > 0 && w >= pw * 0.85 && w >= 240) {
        el.style.setProperty("background-color", "transparent", "important");
        el.style.setProperty("border", "0", "important");
        el.style.setProperty("border-bottom", "1px solid rgba(232,236,239,.16)", "important");
        el.style.setProperty("border-radius", "0", "important");
        el.style.setProperty("box-shadow", "none", "important");
        el.style.setProperty("padding-left", "0", "important");
        el.style.setProperty("padding-right", "0", "important");
      }
    }
    var bgm = cs.backgroundColor.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/);
    if (bgm) {
      var r8 = +bgm[1], g8 = +bgm[2], b8 = +bgm[3], a8 = bgm[4] == null ? 1 : +bgm[4];
      var mx8 = Math.max(r8, g8, b8), mn8 = Math.min(r8, g8, b8), sat8 = mx8 ? (mx8 - mn8) / mx8 : 0;
      var txt = (el.textContent || "").trim();
      var waku = /^[1-6]$/.test(txt) && w <= 40;
      // 黒に近い面（中身のある箱・帯）→ 紺の薄い面へ。トップの紺と同じ系統で明るくする
      if (a8 >= 0.5 && mx8 <= 48 && !waku && h >= 20) {
        el.style.setProperty("background-color", "rgba(120,165,215,.10)", "important");
      }
      // 色で塗った小さい札 → 枠線だけ（文字色を札の色に）
      else if (a8 >= 0.5 && sat8 >= 0.3 && mx8 >= 110 && h > 0 && h <= 28 && w <= 160 && !waku && txt && !el.matches("[aria-selected=true],[aria-pressed=true],.active,.on,.sel,.is-active,.cur,.current")) {
        var cc = "rgb(" + r8 + "," + g8 + "," + b8 + ")";
        el.style.setProperty("background-color", "transparent", "important");
        el.style.setProperty("border", "1px solid " + cc, "important");
        el.style.setProperty("color", cc, "important");
        el.style.setProperty("-webkit-text-fill-color", cc, "important");
      }
    }
    // 薄すぎる灰色の文字を明るく
    var fc = cs.color.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
    if (fc) {
      var r9 = +fc[1], g9 = +fc[2], b9 = +fc[3], mx9 = Math.max(r9, g9, b9), mn9 = Math.min(r9, g9, b9);
      if (mx9 - mn9 <= 40 && mx9 >= 90 && mx9 <= 165) el.style.setProperty("color", "#aebccb", "important");
    }
    // 大きい数字は極太書体
    if (el.children.length === 0 && px(cs.fontSize) >= 22) {
      var nt = (el.textContent || "").trim();
      if (nt && /^[0-9.,:%\/\-+円位R]+$/.test(nt)) {
        el.style.setProperty("font-family", '"Dela Gothic One",' + SYS, "important");
        el.style.setProperty("font-weight", "400", "important");
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
    if (root.nodeType === 1 && root !== document.body) styleEl(root);
    var els = root.querySelectorAll ? root.querySelectorAll("*") : [];
    for (var i = 0; i < els.length; i++) styleEl(els[i]);
  }
  var busy = false, q = [];
  function run(){ busy = false; var nodes = q; q = []; nodes.forEach(function(n){ if (n.isConnected) pass(n); }); }
  function strip(){
    var d = document.createElement("div");
    d.setAttribute("aria-hidden", "true");
    d.className = "aiNashiWaku";
    d.innerHTML = "<i></i><i></i><i></i><i></i><i></i><i></i>";
    document.body.insertBefore(d, document.body.firstChild);
  }
  function start(){
    strip();
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
