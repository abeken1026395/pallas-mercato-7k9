/* 選手図鑑 最小変更案（実験場・2026-10-23）：絵文字だけを文字に置き換える。
   ⭐（推しフォロー中）→ ★（色はそのまま黄色）、📝（選手の札のメモあり）→「メモ」・それ以外の📝は外す、📘（トリセツ）→ 外す。
   本番では scripts/players/app.jsx と players/index.html の文字を直す。 */
(function(){
  var MAP = [["⭐", "★"], ["📝", "メモ"], ["📘️", ""], ["📘", ""]];
  function fix(root){
    var tw = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null), n, list = [];
    while ((n = tw.nextNode())) list.push(n);
    list.forEach(function(t){
      var v = t.nodeValue, nv = v;
      var memoMark = t.parentNode && t.parentNode.getAttribute && t.parentNode.getAttribute("aria-label") === "メモあり";
      MAP.forEach(function(m){ nv = nv.split(m[0]).join(m[0] === "\uD83D\uDCDD" && !memoMark ? "" : m[1]); });
      if (nv !== v) t.nodeValue = nv.replace(/^\s+/, function(s){ return v.charAt(0) === "\uD83D" ? "" : s; });
    });
  }
  function start(){
    fix(document.body);
    new MutationObserver(function(ms){
      ms.forEach(function(m){
        if (m.type === "characterData") { if (m.target.parentNode) fix(m.target.parentNode); }
        else m.addedNodes.forEach(function(a){ if (a.nodeType === 1) fix(a); else if (a.nodeType === 3 && a.parentNode) fix(a.parentNode); });
      });
    }).observe(document.body, { childList: true, subtree: true, characterData: true });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
