/* サイト共通の型 第6版（実験場・2026-10-23）。けん「動きが遅い」「効率化を図れ」。
   第5版は、表示のたびに数万の部品を1つずつ読んで塗り直していたので、タップのたびに重かった。
   第6版は、第5版が塗った結果を作るときに（ブラウザで開いて）写し取り、ページごとの CSS（kata6/ページ名.css）にした。
   読み込み・タップのときに色や形を計算しない。ここに残すのは軽い処理だけ：
   9) 絵文字・飾りの矢印・「——」を外す　11) 試作どうしの行き来　1) 題字の印　数字だけの部品の印 kataN（文字だけ見る） */
(function(){
  var EMO = /(?:\p{Extended_Pictographic}|[\u{1F1E6}-\u{1F1FF}])️?|️|‍/gu;
  var FIXCH = /[\u{1F1E6}-\u{1F1FF}\u200D\uFE0F→›»—―─]|\p{Extended_Pictographic}|BOATRACE/u;
  var KEEP = "©®★☆♥♡▶◀▲▼△▽◆◇■□●○◎✓✔✕✖♪™";
  function textPass(root){
    var tw = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null), n, list = [];
    while ((n = tw.nextNode())) list.push(n);
    list.forEach(function(t){
      var v = t.nodeValue; if (!FIXCH.test(v)) return; // 直す文字（絵文字・矢印・ダッシュ・BOATRACE）が無い文は親をたどらない
      var p = t.parentElement; if (!p || p.closest("script,style,textarea,svg,code,pre,footer")) return; // フッター（制作・運営の表記）は書き換えない。ページ側が表記の改変を検知して、2つ目の表記を足してしまう（けん 10-24「フッターが被ってる」）
      var nv = v.replace(EMO, function(s){ return KEEP.indexOf(s.charAt(0)) >= 0 ? s.charAt(0) : ""; });
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
  var MAP = { "": "next/topI.html", "index.html": "next/topI.html", "players/": "next/playersH.html", "players/index.html": "next/playersH.html" };
  var PAGES = { "highlights/": "highlights", "racers/": "racers", "results/": "results", "motor/": "motor", "motor-maintenance/": "motorMaintenance",
    "players/card.html": "playersCard", "payouts/": "payouts", "stadium/": "stadium", "kensho/": "kensho", "kensho/flow/": "kenshoFlow",
    "kensho/fmochi/": "kenshoFmochi", "kensho/jimoto/": "kenshoJimoto", "kensho/kado/": "kenshoKado", "kensho/kisetsu/": "kenshoKisetsu",
    "kensho/ninki/": "kenshoNinki", "kensho/shobugake/": "kenshoShobugake", "kensho/taiju/": "kenshoTaiju", "kensho/tilt/": "kenshoTilt",
    "glossary/": "glossary", "fan/": "fan", "announcers/": "announcers", "uranai/": "uranai", "updates/": "updates", "torisetsu/": "torisetsu" };
  Object.keys(PAGES).forEach(function(k){ MAP[k] = "next/kansei6/" + PAGES[k] + ".html"; if (/\/$/.test(k)) MAP[k + "index.html"] = MAP[k]; });
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
  // 数字だけの短い部品に印 kataN を付ける（第5版が数字の書体・大きさを変えていた部品。中身で決まるので、文字だけ見て付ける。色や大きさは読まない）
  var PNUM = /^[¥￥+\-−]?\d[\d,]*(?:\.\d+)?\s*(?:%|％|円|倍|回|位|本|件|走|勝|機|人|R|秒|号機|日|節|pt)?$/;
  function numMark(p){
    if (!p || p.nodeType !== 1) return;
    var own = false; for (var c = p.firstChild; c; c = c.nextSibling) if (c.nodeType === 3 && c.nodeValue.trim()) { own = true; break; }
    var t = own ? (p.textContent || "").trim() : "";
    var on = own && t.length <= 14 && PNUM.test(t) && /\d/.test(t);
    if (on !== p.classList.contains("kataN")) p.classList.toggle("kataN", on);
  }
  function numPass(root){
    var tw = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null), n, seen = new Set();
    while ((n = tw.nextNode())) {
      var p = n.parentElement; if (!p || seen.has(p)) continue;
      var v = n.nodeValue; if ((v.length > 40 || !/\d/.test(v)) && !p.classList.contains("kataN")) continue; // 数字の無い文は、親を調べない（印が付いていた部品だけ外しに行く）
      seen.add(p); numMark(p);
    }
    if (root.nodeType === 1) numMark(root);
  }
  function start(){
    if (!window.KATA_LINK_ONLY) { textPass(document.body); numPass(document.body); title(); }
    relink(document.body);
    new MutationObserver(function(ms){
      ms.forEach(function(m){ m.addedNodes.forEach(function(a){
        if (a.nodeType === 1) { if (!window.KATA_LINK_ONLY) { textPass(a); numPass(a); } relink(a); }
        else if (a.nodeType === 3 && a.parentElement && !window.KATA_LINK_ONLY) { textPass(a.parentElement); numMark(a.parentElement); }
      });
      if (m.type === "characterData" && m.target.parentElement && !window.KATA_LINK_ONLY) numMark(m.target.parentElement);
      if (m.type === "childList" && m.removedNodes.length && m.target.nodeType === 1 && !window.KATA_LINK_ONLY) numMark(m.target); });
    }).observe(document.body, { childList: true, subtree: true, characterData: true });
    if (!window.KATA_LINK_ONLY) window.addEventListener("load", function(){ title(); });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
