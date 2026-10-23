/* サイト共通の型 第3版（実験場・2026-10-23）。第2版 kata2.js に 20)〜22) を足したもの（けん「統一してみたらとにかくAIくさいし見にくい。角も丸い」）。説明は kata.css の頭。
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
  /* 第2版：紫に加えてピンク（赤紫）も黄へ */ function isPurple(c){ if (!c || c[3] === 0) return false; var x = hue(c); return x[0] >= 240 && x[0] <= 345 && x[1] >= 0.3 && x[2] >= 0.3; }

  function styleEl(el){
    if (done.has(el)) return; done.add(el);
    var tag = el.tagName;
    if (el.closest("[data-kata-skip]")) return; // ページ側で形を決めている部品はさわらない
    if (tag === "IMG") { if (parseFloat(getComputedStyle(el).borderTopLeftRadius) > 0) el.style.setProperty("border-radius", "0", "important"); return; }
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
    // 20) 角はすべて四角に。丸のままにするのは 14px 以下の小さな点だけ
    if (rad > 0) {
      var small = Math.min(w, h);
      if (!(small > 0 && small <= 14 && rad >= small / 2)) el.style.setProperty("border-radius", "0", "important");
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
    // ---- 第2版で足した決まり ----
    cs = getComputedStyle(el);
    // 12) 斜体 → 立てる
    if (cs.fontStyle === "italic" && tag !== "I" && tag !== "EM") el.style.setProperty("font-style", "normal", "important");
    else if (cs.fontStyle === "italic") el.style.setProperty("font-style", "normal", "important");
    // 13) 字間を広げた小さな文字 → 詰める（飾りの小見出しの癖）
    if (fs <= 13 && ls >= 1) el.style.setProperty("letter-spacing", "0", "important");
    // 14) 文字の色を絞る：ピンク・紫寄りの赤紫・水色・青の地の文字 → 白か淡い灰。
    //     札（地や枠のある部品）の中の色は意味があるのでそのまま。赤・緑・黄・橙もそのまま
    var fc2 = parseC(cs.color), own = (function(){
      for (var p = el, k = 0; p && k < 3; p = p.parentElement, k++) {
        var s = getComputedStyle(p), b = parseC(s.backgroundColor);
        if (p !== el && k > 0 && (px(p.getBoundingClientRect().height) > 40)) break;
        if ((b && b[3] > 0.15 && px(p.getBoundingClientRect().height) <= 40) || (px(s.borderTopWidth) > 0 && s.borderTopStyle !== "none" && p.getBoundingClientRect().height <= 40)) return true;
      }
      return false; })();
    if (fc2 && !own && !el.closest(".kataTitle")) {
      var hh = hue(fc2);
      // 暗い色の文字（白い札の上の文字など）は対象外。後ろの地が明るいときも対象外
      var lightBack = (function(){ for (var p = el; p && p !== document.body; p = p.parentElement) { var b = parseC(getComputedStyle(p).backgroundColor); if (b && b[3] > 0.5) return hue(b)[2] > 0.55; } return false; })();
      if (!lightBack && hh[2] >= 0.45 && hh[1] >= 0.35 && ((hh[0] >= 170 && hh[0] < 240) || (hh[0] > 300 && hh[0] < 345))) {
        var big = fs >= 15 || cs.fontWeight >= 600 || tag === "A";
        el.style.setProperty("color", big ? "#f2f2f0" : "#c9d3dd", "important");
        if (!el.children.length) el.style.setProperty("-webkit-text-fill-color", big ? "#f2f2f0" : "#c9d3dd", "important");
      }
    }
    // 15) 地と枠の両方を持つ大きな箱 → 枠を外す（地だけで区切る）
    var bg3 = parseC(cs.backgroundColor);
    if (bg3 && bg3[3] > 0.3 && h > 40 && w > 120 && px(cs.borderTopWidth) > 0 && px(cs.borderTopWidth) <= 1.5) el.style.setProperty("border", "0", "important");
    // 19) 絵文字を外して空になった四角い飾り枠 → 消す
    if (w >= 20 && w <= 64 && h >= 20 && h <= 64 && Math.abs(w - h) <= 8 && !(el.textContent || "").trim() && !el.querySelector("img,svg,canvas,input,select,video") && tag !== "BUTTON" && tag !== "A" && tag !== "INPUT" && !el.closest("button,a,label") && ((bg3 && bg3[3] > 0.3) || px(cs.borderTopWidth) > 0)) { el.style.setProperty("display", "none", "important"); return; }
    // 16) 箱の角丸をさらに小さく（6 → 3px）
    // 21) 読みやすさ：色の付いていない文字（灰色）を、紺の地の上で十分に明るくする。12px 未満の文字は 12px に
    var fcx = parseC(getComputedStyle(el).color);
    if (fcx && Array.prototype.some.call(el.childNodes, function(n){ return n.nodeType === 3 && n.nodeValue.trim(); })) {
      var hx = hue(fcx);
      if (hx[1] < 0.3 && hx[2] < 0.82 && hx[2] > 0.25) el.style.setProperty("color", fs <= 12 ? "#c8d3dd" : "#e3e9ee", "important"); // 文字の塗り（text-fill）は子に引き継がれて色付きの●まで灰色にするので触らない
      if (fs > 0 && fs < 12 && !el.closest(".kataNote")) el.style.setProperty("font-size", "12px", "important");
    }
    // 22) 紺の上にさらに紺の箱を浮かせない：大きな箱の地を外し、上下の罫線だけで区切る（札・ボタン・入力欄は対象外）
    var bgx = parseC(getComputedStyle(el).backgroundColor);
    var fixedLike = /sticky|fixed/.test(getComputedStyle(el).position);
    if (fixedLike && bgx && bgx[3] > 0.3) { /* 上に重なる帯は地を残す（下の文字が透けて重ならないように） */ }
    else if (bgx && bgx[3] > 0.3 && h > 60 && w > 200 && tag !== "BUTTON" && tag !== "INPUT" && tag !== "SELECT" && tag !== "TEXTAREA" && !el.closest("button,[role=tab]")) {
      var hb = hue(bgx);
      if (hb[1] < 0.8 && hb[2] < 0.22) {
        el.style.setProperty("background-color", "transparent", "important");
        el.style.setProperty("border-top", "1px solid #2b4568", "important");
        el.style.setProperty("border-bottom", "1px solid #2b4568", "important");
      }
    }
  }

  // ---- 第3版の見直しで足した決まり（けん「全て見直せ」・自動の点検で見つかった所） ----
  function gradAt(y){ var st = [[0, [27, 58, 94]], [360, [19, 43, 70]], [900, [13, 28, 47]], [1500, [10, 20, 34]]]; if (y >= 1500) return [10, 20, 34];
    for (var i = 0; i < 3; i++) { var a = st[i], b = st[i + 1]; if (y <= b[0]) { var t = (y - a[0]) / (b[0] - a[0]); return a[1].map(function(v, k){ return v + (b[1][k] - v) * t; }); } } }
  function backOf(e, yDoc){
    for (var p = e; p && p !== document.documentElement; p = p.parentElement) {
      var s = getComputedStyle(p), b = parseC(s.backgroundColor);
      if (b && b[3] > 0.5) return b.slice(0, 3);
      if (p !== document.body && s.backgroundImage && s.backgroundImage !== "none" && s.backgroundImage.indexOf("gradient") < 0) return null;
    }
    return gradAt(yDoc);
  }
  function lum(c){ return c.slice(0, 3).reduce(function(acc, v, i){ v /= 255; v = v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); return acc + [0.2126, 0.7152, 0.0722][i] * v; }, 0); }
  function ratio(a, b){ var x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); }
  function fixPass(root){
    var els = root.querySelectorAll ? root.querySelectorAll("*") : [];
    for (var i = 0; i < els.length; i++) {
      var e = els[i];
      if (e.closest(".kataNote,svg,canvas,.ugSwCover,script,style,.kataTitle,[data-kata-skip]")) continue;
      var r = e.getBoundingClientRect(); if (!r.width || !r.height) continue;
      var s = getComputedStyle(e), y = r.top + window.scrollY, b = parseC(s.backgroundColor);
      // 23) 左の細い色の棒（中身の無い細い要素・::before/::after の細い帯）→ 消す
      if (r.width <= 6 && r.height >= 16 && b && b[3] > 0.3 && !e.textContent.trim() && !e.children.length) { e.style.setProperty("display", "none", "important"); continue; }
      ["before", "after"].forEach(function(ps){
        var q = getComputedStyle(e, "::" + ps), qb = parseC(q.backgroundColor), qw = parseFloat(q.width), qh = parseFloat(q.height);
        if (q.content !== "none" && q.content !== "normal" && qw > 0 && qw <= 6 && qh >= 14 && qb && qb[3] > 0.3) e.classList.add(ps === "before" ? "kataNoBefore" : "kataNoAfter");
      });
      // 内側の影で描いた左の色帯（inset 4px 0 0 など）→ 消す
      var sh = s.boxShadow.match(/(-?\d+(?:\.\d+)?)px (-?\d+(?:\.\d+)?)px 0px 0px inset/);
      if (sh && Math.abs(parseFloat(sh[1])) >= 2 && parseFloat(sh[2]) === 0) e.style.setProperty("box-shadow", "none", "important");
      // 角の残り（遅れて大きさが決まった部品）
      var rad = parseFloat(s.borderTopLeftRadius) || 0, sm = Math.min(r.width, r.height);
      if (rad > 0 && !(sm <= 14 && rad >= sm / 2 - 1)) e.style.setProperty("border-radius", "0", "important");
      // 24) 背景と同じ色に溶けている部品（地の色が後ろとほぼ同じ）→ 小さな部品は 1px の枠、大きな箱は地を外して上下の罫線
      if (b && b[3] > 0.5 && r.width > 30 && r.height > 16 && e.tagName !== "INPUT" && e.tagName !== "SELECT" && e.tagName !== "TEXTAREA") {
        var pb = backOf(e.parentElement, y);
        if (pb && ratio(b, pb) < 1.15) {
          var wide = r.width > Math.min(window.innerWidth, document.documentElement.clientWidth) * 0.6;
          if (/sticky|fixed/.test(s.position) || (!wide && r.height <= 60)) { if (!(parseFloat(s.borderTopWidth) > 0)) e.style.setProperty("box-shadow", "inset 0 0 0 1px #3d5a80", "important"); }
          else { e.style.setProperty("background-color", "transparent", "important"); e.style.setProperty("border-top", "1px solid #2b4568", "important"); e.style.setProperty("border-bottom", "1px solid #2b4568", "important"); }
        }
      }
      // 25) 読みにくい文字（後ろとの差が 4.5 未満）→ 明るく。色で意味を出す札（地が色付き）の中はそのまま
      var own = Array.prototype.some.call(e.childNodes, function(n){ return n.nodeType === 3 && n.nodeValue.trim(); });
      if (own) {
        var fc = parseC(s.color), bk = backOf(e, y);
        if (fc && fc[3] > 0.5 && bk && ratio(fc, bk) < 4.5) {
          var bh = hue(bk.concat(1)), fh = hue(fc);
          var chip = bh[1] > 0.45 && bh[2] > 0.25; // 枠番などの色付きの札
          if (!chip) {
            var light = lum(bk) < 0.2, to = light ? (fh[1] > 0.45 ? null : "#e3e9ee") : "#111111";
            if (to) { e.style.setProperty("color", to, "important"); if (!e.children.length) e.style.setProperty("-webkit-text-fill-color", to, "important"); }
            else if (fh[1] > 0.45) { e.style.setProperty("filter", "brightness(1.6)", "important"); }
          }
        }
      }
    }
  }

  // 17) 縦に積んだ同じ形の箱（カードの山）→ 罫線で区切る一覧に。並び・中身はそのまま
  function stackPass(root){
    var els = root.querySelectorAll ? root.querySelectorAll("*") : [];
    var seen = new Set();
    for (var i = 0; i < els.length; i++) {
      var p = els[i]; if (seen.has(p) || p.children.length < 3 || p.closest(".kataNote")) continue;
      seen.add(p);
      var kids = Array.prototype.filter.call(p.children, function(c){
        var s = getComputedStyle(c), b = parseC(s.backgroundColor), r = c.getBoundingClientRect();
        return b && b[3] > 0.3 && r.height > 36 && s.display !== "none" && s.position !== "absolute" && s.position !== "fixed";
      });
      if (kids.length < 3) continue;
      var x0 = Math.round(kids[0].getBoundingClientRect().left), same = kids.every(function(c){ return Math.abs(Math.round(c.getBoundingClientRect().left) - x0) <= 2 && c.tagName === kids[0].tagName; });
      if (!same) continue; // 横に並ぶ格子は対象外
      var pw = p.getBoundingClientRect().width;
      if (kids.some(function(c){ return c.getBoundingClientRect().width < pw * 0.85; })) continue;
      var ps = getComputedStyle(p);
      if (ps.display.indexOf("flex") >= 0 || ps.display.indexOf("grid") >= 0) p.style.setProperty("row-gap", "0", "important");
      kids.forEach(function(c, j){
        c.style.setProperty("margin-top", "0", "important");
        c.style.setProperty("margin-bottom", "0", "important");
        c.style.setProperty("border-radius", "0", "important");
        c.style.setProperty("border", "0", "important");
        c.style.setProperty("border-top", "1px solid #263f61", "important");
        if (j === kids.length - 1) c.style.setProperty("border-bottom", "1px solid #263f61", "important");
      });
    }
  }

  // 9) 絵文字・飾りの矢印
  function textPass(root){
    var tw = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null), n, list = [];
    while ((n = tw.nextNode())) list.push(n);
    list.forEach(function(t){
      var p = t.parentElement; if (!p || p.closest("script,style,textarea,svg,code,pre")) return;
      var v = t.nodeValue, nv = v.replace(EMO, function(s){ return KEEP.indexOf(s.charAt(0)) >= 0 ? s.charAt(0) : ""; });
      if (p.closest("a,button")) nv = nv.replace(/\s*(?:→|›|»)\s*$/, "").replace(/^\s*(?:→|›)\s*/, "");
      // 18) 文章の癖：「——」で文をつなぐ → 句点で切る。題字の頭の英字「BOATRACE」→ 外す
      nv = nv.replace(/[—―─]{2}\s*(?=[」』）)]|$)/g, "").replace(/([。、！？」』])\s*[—―─]{2}\s*/g, "$1").replace(/\s*[—―─]{2}\s*/g, "。");
      if (p.closest("h1,.kataTitle")) nv = nv.replace(/^\s*BOATRACE\s+/, "");
      if (nv === v) return;
      var host = p.closest("a,button,[role=button],[role=tab],label");
      if (!nv.trim() && host && host.textContent.replace(v, "").trim() === "" && !host.getAttribute("aria-label")) return; // 中身が絵文字だけのボタンは残す
      t.nodeValue = nv.replace(/^\s+(?=\S)/, "");
    });
  }

  // 11) 試作どうしの行き来
  var root = location.pathname.replace(/\/next\/.*$/, "/");
  var MAP = { "": "next/topF.html", "index.html": "next/topF.html", "players/": "next/playersE.html", "players/index.html": "next/playersE.html" };
  var PAGES = { "highlights/": "highlights", "racers/": "racers", "results/": "results", "motor/": "motor", "motor-maintenance/": "motorMaintenance",
    "players/card.html": "playersCard", "payouts/": "payouts", "stadium/": "stadium", "kensho/": "kensho", "kensho/flow/": "kenshoFlow",
    "kensho/fmochi/": "kenshoFmochi", "kensho/jimoto/": "kenshoJimoto", "kensho/kado/": "kenshoKado", "kensho/kisetsu/": "kenshoKisetsu",
    "kensho/ninki/": "kenshoNinki", "kensho/shobugake/": "kenshoShobugake", "kensho/taiju/": "kenshoTaiju", "kensho/tilt/": "kenshoTilt",
    "glossary/": "glossary", "fan/": "fan", "announcers/": "announcers", "uranai/": "uranai", "updates/": "updates", "torisetsu/": "torisetsu" };
  Object.keys(PAGES).forEach(function(k){ MAP[k] = "next/kansei3/" + PAGES[k] + ".html"; if (/\/$/.test(k)) MAP[k + "index.html"] = MAP[k]; });
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
    stackPass(node);
    fixPass(node);
    relink(node);
  }
  // 遅れて大きさや中身が決まる部品があるので、読み込み後・1.5秒後・4秒後に全体をもう一度かける
  function again(){ done = new WeakSet(); pass(document.body); title(); }
  var q = [], busy = false;
  function flush(){ busy = false; var a = q; q = []; a.forEach(function(n){ if (n.isConnected) pass(n); }); title(); }
  function start(){
    if (window.KATA_LINK_ONLY) { relink(document.body); new MutationObserver(function(ms){ ms.forEach(function(m){ m.addedNodes.forEach(function(a){ if (a.nodeType === 1) relink(a); }); }); }).observe(document.body, { childList: true, subtree: true }); return; }
    title(); pass(document.body);
    window.addEventListener("load", function(){ setTimeout(again, 50); }); setTimeout(again, 1500); setTimeout(again, 4000);
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
