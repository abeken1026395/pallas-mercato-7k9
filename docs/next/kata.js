/* サイト共通の型（実験場・2026-10-23）。説明は kata.css の頭。
   描画後のページに、トップと選手図鑑で了承された決まりだけをかける：
   1) 題字（最初の h1）を Dela Gothic One の白に
   2) 黒に近い箱の地（#0b1219 などの暗い無彩色）→ トップの箱と同じ紺 #12233a
   3) 箱の斜めのグラデーション → 平らな色、文字のグラデーション → 1色
   4) 大きな角丸 → 6px、丸い札 → 4px（小さな点は丸のまま）
   5) 左の太い色帯 → なし（色の意味は札や文字で分かる）
   6) ぼかしの影・文字の影 → なし
   7) 紫 → 大時計の黄色（トップの見どころと同じ）
   8) Helvetica・Arial などの書体 → 端末の標準
   9) 絵文字 → 外す（★ ♥ ▶ など意味のある記号は残す）。末尾の飾りの矢印 → 外す
   10) 英字の大文字で字間を広げた小見出し → 外す
   11) 試作どうしの行き来：本番のページへのリンクを、同じページの試作へ付け替える
   色で意味を出している札（荒れ・堅め・級別・枠番など）の色はそのまま。 */
(function(){
  var EMO = /(?:\p{Extended_Pictographic}|[\u{1F1E6}-\u{1F1FF}])️?|️|‍/gu;
  var KEEP = "©®★☆♥♡▶◀▲▼△▽◆◇■□●○◎✓✔✕✖♪™";
  var FONT = /Helvetica|Arial|Inter|Roboto|Segoe/i;
  var SYS = '-apple-system,"Hiragino Sans","Noto Sans JP",sans-serif';
  var done = new WeakSet();
  function px(v){ return parseFloat(v) || 0; }
  function parseC(s){ var m = s && s.match(/rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\)/); return m ? [+m[1], +m[2], +m[3], m[4] == null ? 1 : +m[4]] : null; }
  function firstColor(s){ var m = s.match(/rgba?\([^)]*\)/); return m ? m[0] : null; }
  function hue(c){ var r = c[0] / 255, g = c[1] / 255, b = c[2] / 255, mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn, h = 0;
    if (d) h = mx === r ? ((g - b) / d) % 6 : mx === g ? (b - r) / d + 2 : (r - g) / d + 4; h *= 60; if (h < 0) h += 360;
    return [h, mx ? d / mx : 0, (mx + mn) / 2]; }
  function isPurple(c){ if (!c || c[3] === 0) return false; var x = hue(c); return x[0] >= 240 && x[0] <= 300 && x[1] >= 0.3 && x[2] >= 0.3; }

  function styleEl(el){
    if (done.has(el)) return; done.add(el);
    var tag = el.tagName;
    if (tag === "HTML" || tag === "BODY" || tag === "SCRIPT" || tag === "STYLE" || tag === "IMG" || tag === "CANVAS" || el.closest("svg") || el.classList.contains("ugSwCover")) return;
    var cs = getComputedStyle(el), r = el.getBoundingClientRect(), w = r.width, h = r.height;
    // 3) グラデーション
    var bi = cs.backgroundImage;
    if (bi && bi.indexOf("gradient") >= 0 && bi.indexOf("url(") < 0) {
      var c = firstColor(bi), clip = cs.webkitBackgroundClip === "text" || cs.backgroundClip === "text";
      if (clip) {
        el.style.setProperty("background-image", "none", "important");
        el.style.setProperty("-webkit-background-clip", "border-box", "important");
        el.style.setProperty("color", c || "#e8ecef", "important");
        el.style.setProperty("-webkit-text-fill-color", c || "#e8ecef", "important");
      } else if (h > 14) {
        el.style.setProperty("background-image", "none", "important");
        var bc0 = parseC(cs.backgroundColor);
        if (c && (!bc0 || bc0[3] === 0)) el.style.setProperty("background-color", c, "important");
      }
      cs = getComputedStyle(el);
    }
    // 2) 黒に近い箱の地 → 紺
    var bg = parseC(cs.backgroundColor);
    if (bg && bg[3] >= 0.6 && Math.max(bg[0], bg[1], bg[2]) <= 40 && Math.max(bg[0], bg[1], bg[2]) - Math.min(bg[0], bg[1], bg[2]) <= 22 && h >= 24 && w >= 60) {
      el.style.setProperty("background-color", "#12233a", "important");
    }
    // 4) 角丸
    var rad = px(cs.borderTopLeftRadius);
    if (rad > 6) {
      var small = Math.min(w, h);
      if (small > 0 && small <= 14 && rad >= small / 2) { /* 小さな点は丸のまま */ }
      else if (h > 0 && h <= 36 && rad >= h / 2 - 1) el.style.setProperty("border-radius", "4px", "important");
      else el.style.setProperty("border-radius", "6px", "important");
    }
    // 5) 左の太い色帯
    var bl = px(cs.borderLeftWidth), bt = px(cs.borderTopWidth);
    if (bl >= 3 && bt <= 1 && cs.borderLeftStyle !== "none") {
      if (bt === 0) el.style.setProperty("border-left", "0", "important");
      else { el.style.setProperty("border-left-width", bt + "px", "important"); el.style.setProperty("border-left-color", cs.borderTopColor, "important"); }
    }
    // 6) 影
    if (cs.boxShadow && cs.boxShadow !== "none" && cs.boxShadow.indexOf("inset") < 0) el.style.setProperty("box-shadow", "none", "important");
    if (cs.textShadow && cs.textShadow !== "none") el.style.setProperty("text-shadow", "none", "important");
    // 7) 紫 → 黄
    var fc = parseC(cs.color);
    if (isPurple(fc)) { el.style.setProperty("color", "#f5d55c", "important"); el.style.setProperty("-webkit-text-fill-color", "#f5d55c", "important"); }
    var bgc = parseC(getComputedStyle(el).backgroundColor);
    if (isPurple(bgc)) {
      el.style.setProperty("background-color", bgc[3] >= 0.6 ? "#f2c200" : "rgba(242,194,0," + Math.min(bgc[3], .25) + ")", "important");
      if (bgc[3] >= 0.6) { el.style.setProperty("color", "#111111", "important"); el.style.setProperty("-webkit-text-fill-color", "#111111", "important"); }
    }
    var brc = parseC(cs.borderTopColor);
    if (px(cs.borderTopWidth) > 0 && isPurple(brc)) el.style.setProperty("border-color", "rgba(242,194,0," + brc[3] + ")", "important");
    // 10) 英字大文字の小見出し
    var tx = el.children.length === 0 ? (el.textContent || "").trim() : "";
    var fs = px(cs.fontSize), ls = cs.letterSpacing === "normal" ? 0 : px(cs.letterSpacing);
    if (tx.length >= 4 && /^[A-Z0-9'’&\s.\-\/|]+$/.test(tx) && /[A-Z]{3}/.test(tx) && fs <= 13 && ls >= 1) { el.style.setProperty("display", "none", "important"); return; }
    // 8) 書体
    if (FONT.test(cs.fontFamily)) el.style.setProperty("font-family", SYS, "important");
  }

  // 9) 絵文字・飾りの矢印
  function textPass(root){
    var tw = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null), n, list = [];
    while ((n = tw.nextNode())) list.push(n);
    list.forEach(function(t){
      var p = t.parentElement; if (!p || p.closest("script,style,textarea,svg,code,pre")) return;
      var v = t.nodeValue, nv = v.replace(EMO, function(s){ return KEEP.indexOf(s.charAt(0)) >= 0 ? s.charAt(0) : ""; });
      if (p.closest("a,button")) nv = nv.replace(/\s*(?:→|›|»)\s*$/, "").replace(/^\s*(?:→|›)\s*/, "");
      if (nv === v) return;
      var host = p.closest("a,button,[role=button],[role=tab],label");
      if (!nv.trim() && host && host.textContent.replace(v, "").trim() === "" && !host.getAttribute("aria-label")) return; // 中身が絵文字だけのボタンは残す
      t.nodeValue = nv.replace(/^\s+(?=\S)/, "");
    });
  }

  // 11) 試作どうしの行き来
  var root = location.pathname.replace(/\/next\/.*$/, "/");
  var MAP = { "": "next/topD.html", "index.html": "next/topD.html", "players/": "next/playersC.html", "players/index.html": "next/playersC.html" };
  var PAGES = { "highlights/": "highlights", "racers/": "racers", "results/": "results", "motor/": "motor", "motor-maintenance/": "motorMaintenance",
    "players/card.html": "playersCard", "payouts/": "payouts", "stadium/": "stadium", "kensho/": "kensho", "kensho/flow/": "kenshoFlow",
    "kensho/fmochi/": "kenshoFmochi", "kensho/jimoto/": "kenshoJimoto", "kensho/kado/": "kenshoKado", "kensho/kisetsu/": "kenshoKisetsu",
    "kensho/ninki/": "kenshoNinki", "kensho/shobugake/": "kenshoShobugake", "kensho/taiju/": "kenshoTaiju", "kensho/tilt/": "kenshoTilt",
    "glossary/": "glossary", "fan/": "fan", "announcers/": "announcers", "uranai/": "uranai", "updates/": "updates", "torisetsu/": "torisetsu" };
  Object.keys(PAGES).forEach(function(k){ MAP[k] = "next/kansei/" + PAGES[k] + ".html"; if (/\/$/.test(k)) MAP[k + "index.html"] = MAP[k]; });
  function relink(scope){
    var as = scope.querySelectorAll ? scope.querySelectorAll("a[href]") : [];
    for (var i = 0; i < as.length; i++) {
      var a = as[i]; if (a.__kata) continue; a.__kata = 1;
      if (a.closest(".kataNote")) continue;
      var u; try { u = new URL(a.getAttribute("href"), document.baseURI); } catch (x) { continue; }
      if (u.origin !== location.origin || u.pathname.indexOf(root) !== 0) continue;
      var rel = u.pathname.slice(root.length);
      if (MAP[rel] && !u.search) a.setAttribute("href", root + MAP[rel] + u.hash);
    }
  }

  function title(){
    if (document.querySelector(".kataTitle")) return;
    var h = document.querySelector("h1");
    if (h && !h.closest(".kataNote")) { h.classList.add("kataTitle"); return; }
    // h1 が無いページ（モーター・24場・場の文化など）は、上の方で一番大きな短い見出しを題字とみなす
    var best = null, bs = 0, els = document.body.querySelectorAll("div,span,p,h2");
    for (var i = 0; i < els.length && i < 400; i++) {
      var e = els[i]; if (e.closest(".kataNote,a,button,label,select")) continue;
      if (e.children.length > 2) continue;
      var tx = (e.textContent || "").trim(); if (tx.length < 2 || tx.length > 40) continue;
      var rc = e.getBoundingClientRect(); if (rc.top > 400 || rc.height === 0) continue;
      var fs = parseFloat(getComputedStyle(e).fontSize) || 0;
      if (fs >= 18 && fs > bs) { bs = fs; best = e; }
    }
    if (best) best.classList.add("kataTitle");
  }
  function pass(node){
    if (node.nodeType !== 1) return;
    textPass(node);
    styleEl(node);
    var els = node.querySelectorAll("*");
    for (var i = 0; i < els.length; i++) styleEl(els[i]);
    relink(node);
  }
  var q = [], busy = false;
  function flush(){ busy = false; var a = q; q = []; a.forEach(function(n){ if (n.isConnected) pass(n); }); title(); }
  function start(){
    if (window.KATA_LINK_ONLY) { relink(document.body); new MutationObserver(function(ms){ ms.forEach(function(m){ m.addedNodes.forEach(function(a){ if (a.nodeType === 1) relink(a); }); }); }).observe(document.body, { childList: true, subtree: true }); return; }
    title(); pass(document.body);
    new MutationObserver(function(ms){
      ms.forEach(function(m){
        if (m.type === "attributes") { done.delete(m.target); q.push(m.target); return; }
        if (m.type === "characterData") { if (m.target.parentElement) q.push(m.target.parentElement); }
        else m.addedNodes.forEach(function(a){ if (a.nodeType === 1 && !a.classList.contains("ugSwCover")) q.push(a); else if (a.nodeType === 3 && a.parentElement) q.push(a.parentElement); });
      });
      if (!busy && q.length) { busy = true; setTimeout(flush, 50); }
    }).observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ["class", "aria-selected", "aria-pressed"] });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
