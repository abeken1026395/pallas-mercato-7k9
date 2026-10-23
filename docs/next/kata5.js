/* サイト共通の型 第5版（実験場・2026-10-23）。第4版の背景をトップ以外は平らな紺にしたもの（window.KATA_GRAD=1 のページだけグラデーション）。
   もとの説明：サイト共通の型 第4版（実験場・2026-10-23）。第3版に高級感の決まり 26)〜28) を足したもの（けん「無料なのに有料サイトの様な高級感」）。
   もとの説明：サイト共通の型 第3版（実験場・2026-10-23）。第2版 kata2.js に 20)〜22) を足したもの（けん「統一してみたらとにかくAIくさいし見にくい。角も丸い」）。説明は kata.css の頭。
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
  // 型が付けた style を部品ごとに覚えておく（元の値も）。タブの切り替えなどで class が変わったら、
  // 覚えた分を元に戻してから型をかけ直す。戻さないと、前の状態の色（選ばれていたタブの金の地など）が残る（けん「見どころ内のタブの動きがおかしい」）
  var KP = new WeakMap(), recording = 0, _sp = CSSStyleDeclaration.prototype.setProperty;
  CSSStyleDeclaration.prototype.setProperty = function(n, v, pr){
    var m = null;
    if (recording) { m = KP.get(this); if (!m) { m = new Map(); KP.set(this, m); } if (!m.has(n)) m.set(n, [this.getPropertyValue(n), this.getPropertyPriority(n), ""]); }
    var r = _sp.call(this, n, v, pr);
    if (m) m.get(n)[2] = this.getPropertyValue(n); // 型が入れた値（読み直した形）
    return r;
  };
  // ページ（React など）が style を書き換えたとき：書き換えられた項目は、その新しい値を「元の値」に置き直す
  function adoptExternal(el){
    var m = KP.get(el.style); if (!m) return;
    m.forEach(function(o, n){ var cur = el.style.getPropertyValue(n); if (cur !== o[2]) { o[0] = cur; o[1] = el.style.getPropertyPriority(n); } });
  }
  function markOwn(root){
    var list = [root].concat(Array.prototype.slice.call(root.querySelectorAll ? root.querySelectorAll("*") : []));
    for (var i = 0; i < list.length; i++) list[i].__kStyle = list[i].getAttribute ? list[i].getAttribute("style") : null;
  }
  function restore(el){
    var m = KP.get(el.style); if (!m) return;
    m.forEach(function(o, n){ if (o[0]) _sp.call(el.style, n, o[0], o[1]); else el.style.removeProperty(n); });
    KP.delete(el.style);
  }
  function resetTree(root){
    var list = [root].concat(Array.prototype.slice.call(root.querySelectorAll("*")));
    for (var i = 0; i < list.length; i++) { var e = list[i]; adoptExternal(e); restore(e); done.delete(e); e.__kNum = 0; e.classList.remove("kataNum", "kataNoBefore", "kataNoAfter"); }
  }
  function meaningful(oldCls, el){
    var f = function(c){ return String(c || "").split(/\s+/).filter(function(x){ return x && !/^(ug|kata)/.test(x); }).sort().join(" "); };
    return f(oldCls) !== f(el.getAttribute("class"));
  }
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
    if (el.closest("[data-kata-skip],[data-kskip]")) return; // ページ側で形を決めている部品・状態が変わる部品はさわらない
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
    if (bg && bg[3] >= 0.6 && Math.max(bg[0], bg[1], bg[2]) <= 40 && Math.max(bg[0], bg[1], bg[2]) - Math.min(bg[0], bg[1], bg[2]) <= 22 && h >= 16 && w >= 24) { // 第5版：小さな札も同じ紺に（読み込みの途中で大きさが変わると、札ごとに色がばらついたため）
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
    if (fixedLike && bgx && bgx[3] > 0.3) { /* 上に重なる帯は地を残す。第5版：一段明るい紺にそろえる（色付きの帯はそのまま） */ if (hue(bgx)[1] < 0.75 && hue(bgx)[2] < 0.3) el.style.setProperty("background-color", "#132b46", "important"); }
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
  function gradAt(y){ if (!window.KATA_GRAD) return [13, 28, 47]; var st = [[0, [27, 58, 94]], [360, [19, 43, 70]], [900, [13, 28, 47]], [1500, [10, 20, 34]]]; if (y >= 1500) return [10, 20, 34];
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
    var els = root.querySelectorAll ? [root].concat(Array.prototype.slice.call(root.querySelectorAll("*"))) : []; // かけ直すときは、その部品自身も含める
    for (var i = 0; i < els.length; i++) {
      var e = els[i];
      if (e.closest(".kataNote,svg,canvas,.ugSwCover,script,style,.kataTitle,[data-kata-skip],[data-kskip]")) continue;
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

  // ---- 第4版：高級感 ----
  // 26) 数字を細身の数字書体に（数字だけの部品・数字＋単位の部品）。書体が細い分、少し大きく
  var PNUM = /^[¥￥+\-−]?\d[\d,]*(?:\.\d+)?\s*(?:%|％|円|倍|回|位|本|件|走|勝|機|人|R|秒|号機|日|節|pt)?$/;
  // 27) 黄の差し色 → 金（シャンパンゴールド）。枠番の5号艇の黄（地が黄の小さな札で数字1つ）はそのまま
  var GOLD_T = "#dcbd78", GOLD_B = "#c8a45e";
  function isYellow(c){ if (!c || c[3] === 0) return false; var x = hue(c); return x[0] >= 38 && x[0] <= 58 && x[1] >= 0.55 && x[2] >= 0.45; }
  function premiumPass(root){
    var els = root.querySelectorAll ? [root].concat(Array.prototype.slice.call(root.querySelectorAll("*"))) : []; // かけ直すときは、その部品自身も含める
    for (var i = 0; i < els.length; i++) {
      var e = els[i];
      if (e.closest(".kataNote,svg,canvas,.ugSwCover,script,style,[data-kata-skip],[data-kskip],input,select,textarea,option")) continue;
      var s = getComputedStyle(e);
      var own = Array.prototype.some.call(e.childNodes, function(n){ return n.nodeType === 3 && n.nodeValue.trim(); });
      var tx = (e.textContent || "").trim();
      if (!e.__kNum && own && !e.closest(".kataTitle") && tx.length <= 14 && PNUM.test(tx) && (tx.match(/\d/g) || []).length >= 1) {
        var fs = parseFloat(s.fontSize) || 0;
        if (fs >= 12) {
          e.__kNum = 1; e.classList.add("kataNum");
          // style 属性に大きさや太さを書いている部品（React で作るページ）は書き換えない。属性で選んで色を付けている上書き（選手図鑑）が外れるため
          var inl = e.getAttribute("style") || "";
          if (fs >= 15 && inl.indexOf("font-size") < 0) e.style.setProperty("font-size", Math.round(fs * 1.14) + "px", "important");
          if ((parseInt(s.fontWeight, 10) || 400) >= 600 && inl.indexOf("font-weight") < 0) e.style.setProperty("font-weight", "600", "important");
        }
      }
      var fc = parseC(s.color), bg = parseC(s.backgroundColor), r = e.getBoundingClientRect();
      var wakuChip = bg && bg[3] > 0.5 && r.width <= 30 && r.height <= 30 && /^[1-6]$/.test(tx);
      if (wakuChip) continue;
      if (isYellow(fc)) { e.style.setProperty("color", GOLD_T, "important"); if (!e.children.length) e.style.setProperty("-webkit-text-fill-color", GOLD_T, "important"); }
      if (isYellow(bg)) {
        if (bg[3] >= 0.6) { e.style.setProperty("background-color", GOLD_B, "important"); e.style.setProperty("color", "#10141a", "important"); e.style.setProperty("-webkit-text-fill-color", "#10141a", "important"); }
        else e.style.setProperty("background-color", "rgba(200,164,94," + Math.min(bg[3], 0.22) + ")", "important");
      }
      var bc = parseC(s.borderTopColor);
      if (parseFloat(s.borderTopWidth) > 0 && isYellow(bc)) e.style.setProperty("border-color", "rgba(200,164,94," + bc[3] + ")", "important");
      // 28) 太い白の見出し線（2px 以上の明るい下線）→ 細い金の線
      var bb = parseC(s.borderBottomColor);
      if (parseFloat(s.borderBottomWidth) >= 2 && bb && hue(bb)[2] > 0.85) e.style.setProperty("border-bottom", "1px solid rgba(212,176,106,.6)", "important");
      // バーの塗り（中身の無い細長い部品）の黄 → 金
      if (bg && isYellow(bg) && !own && r.height <= 8) e.style.setProperty("background-color", GOLD_B, "important");
    }
  }

  // 17) 縦に積んだ同じ形の箱（カードの山）→ 罫線で区切る一覧に。並び・中身はそのまま
  function stackPass(root){
    var els = root.querySelectorAll ? [root].concat(Array.prototype.slice.call(root.querySelectorAll("*"))) : []; // かけ直すときは、その部品自身も含める
    var seen = new Set();
    for (var i = 0; i < els.length; i++) {
      var p = els[i]; if (seen.has(p) || p.children.length < 3 || p.closest(".kataNote,[data-kskip]")) continue;
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
  var MAP = { "": "next/topH.html", "index.html": "next/topH.html", "players/": "next/playersG.html", "players/index.html": "next/playersG.html" };
  var PAGES = { "highlights/": "highlights", "racers/": "racers", "results/": "results", "motor/": "motor", "motor-maintenance/": "motorMaintenance",
    "players/card.html": "playersCard", "payouts/": "payouts", "stadium/": "stadium", "kensho/": "kensho", "kensho/flow/": "kenshoFlow",
    "kensho/fmochi/": "kenshoFmochi", "kensho/jimoto/": "kenshoJimoto", "kensho/kado/": "kenshoKado", "kensho/kisetsu/": "kenshoKisetsu",
    "kensho/ninki/": "kenshoNinki", "kensho/shobugake/": "kenshoShobugake", "kensho/taiju/": "kenshoTaiju", "kensho/tilt/": "kenshoTilt",
    "glossary/": "glossary", "fan/": "fan", "announcers/": "announcers", "uranai/": "uranai", "updates/": "updates", "torisetsu/": "torisetsu" };
  Object.keys(PAGES).forEach(function(k){ MAP[k] = "next/kansei5/" + PAGES[k] + ".html"; if (/\/$/.test(k)) MAP[k + "index.html"] = MAP[k]; });
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
    recording++;
    try { passInner(node); } finally { recording--; }
    markOwn(node);
  }
  // 選んだ状態を持つ部品（タブ・札・日付の切り替えなど）は、最初から型をかけない（ページの色のまま）。
  // 見分け方：class に on／active などがある・aria-selected／aria-pressed がある・class が tab／chip など、
  // または同じ形の兄弟が並び、1つだけ地の色が違う（選ばれている）組
  var CTL = ".rbtn,.cd,.tab,.tabs > *,.chip,.chipbtn,.dsw-btn,[role=tab],[aria-selected],[aria-pressed],.on,.active,.is-active,.sel,.selected,.cur,.current";
  function markControls(root){
    if (!root.querySelectorAll) return;
    var c = [root].concat(Array.prototype.slice.call(root.querySelectorAll(CTL))).filter(function(e){ return e.matches && e.matches(CTL); });
    c.forEach(function(e){ e.setAttribute("data-kskip", ""); var p = e.parentElement; if (p) Array.prototype.forEach.call(p.children, function(sib){ if (sib.tagName === e.tagName) sib.setAttribute("data-kskip", ""); }); });
    var ps = new Set(); Array.prototype.forEach.call(root.querySelectorAll("button,[role=button],a,span,div"), function(e){ if (e.parentElement) ps.add(e.parentElement); });
    ps.forEach(function(p){
      var kids = Array.prototype.filter.call(p.children, function(k){ return k.tagName === "BUTTON" || k.getAttribute("role") === "button"; });
      if (kids.length < 2 || kids.length > 14) return;
      var bgs = kids.map(function(k){ return getComputedStyle(k).backgroundColor + getComputedStyle(k).color; });
      var cnt = {}; bgs.forEach(function(b){ cnt[b] = (cnt[b] || 0) + 1; });
      var keys = Object.keys(cnt);
      if (keys.length === 2 && keys.some(function(k){ return cnt[k] === 1; })) kids.forEach(function(k){ k.setAttribute("data-kskip", ""); });
    });
  }
  function passInner(node){
    markControls(node);
    textPass(node);
    styleEl(node);
    var els = node.querySelectorAll("*");
    for (var i = 0; i < els.length; i++) styleEl(els[i]);
    stackPass(node);
    fixPass(node);
    premiumPass(node);
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
    // 状態が変わる部品（タブ・札・時刻で class や style が変わる行など）には、型の色を塗らない。
    // 塗った上からページが状態を切り替えると、古い色が残ったり（けん「出走表はタブに古い色」）、
    // 塗り直しとページの切り替えが追いかけ合って色がブレ続けたりする（けん「見どころの場別で場所を選ぶと永遠にぶれ続ける」）。
    // そこで、class・aria・style がページ側で一度でも変わった部品は、その部品と中身から型の塗りを外して元に戻し、以後は塗らない。
    // 新しく足された中身には、その場で（画面に描かれる前に）型をかける
    new MutationObserver(function(ms){
      var now = [];
      ms.forEach(function(m){
        if (m.type === "attributes") {
          var tg = m.target;
          if (tg.closest("[data-kskip],.ugBoard,.ugSwCover,.ugTabBar,.kataNote")) return;
          if (m.attributeName === "class" && !meaningful(m.oldValue, tg)) return; // 動き（ug…）や型（kata…）の印だけの変化は見ない
          if (m.attributeName === "style") { if (tg.getAttribute("style") === tg.__kStyle) return; adoptExternal(tg); } // 型自身が書いた style は見ない
          // 大きな入れ物（場の札・カードの並び・開閉の箱など）の切り替えは、中の色を変えないことが多いので見送る（塗りはそのまま）。
          // 状態で色が変わるのは、タブ・札・行のような小さな部品
          var tr = tg.getBoundingClientRect(); if (tr.height > 80 || tr.width > window.innerWidth * 0.95 && tr.height > 48) return;
          tg.setAttribute("data-kskip", "");
          var list = [tg].concat(Array.prototype.slice.call(tg.querySelectorAll("*")));
          list.forEach(function(e){ adoptExternal(e); restore(e); e.classList.remove("kataNum"); });
          return;
        }
        if (m.type === "characterData") { if (m.target.parentElement) now.push(m.target.parentElement); }
        else m.addedNodes.forEach(function(a){ if (a.nodeType === 1 && !a.classList.contains("ugSwCover") && !a.classList.contains("ugBoard") && !a.classList.contains("ugTabBar")) now.push(a); else if (a.nodeType === 3 && a.parentElement) now.push(a.parentElement); });
      });
      now = now.filter(function(n, k){ return n.isConnected && !n.closest("[data-kskip]") && now.indexOf(n) === k && !now.some(function(o){ return o !== n && o.contains(n); }); });
      if (now.length) { now.forEach(pass); title(); }
    }).observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeOldValue: true, attributeFilter: ["class", "aria-selected", "aria-pressed", "style"] });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
