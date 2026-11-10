/* 下部タブの小さな丸（再訪設計書 izonSekkei 段階1・2026-11-10）
   見どころ：今日（JST）まだ見どころを開いていなければ丸を付ける
   結果　　：この端末で保存した買い目のレースが締切から15分過ぎ、そのあと結果を開いていなければ丸を付ける
   色はアクセントの1色だけ（赤は使わない）。点滅・音はなし。保存先は dz_seen（/hikae/ の対象） */
(function(){
  function jd(t){ return new Date((t||Date.now())+9*3600e3).toISOString().slice(0,10).replace(/-/g,""); }
  function obj(k){ try{ var v=JSON.parse(localStorage.getItem(k)||"{}"); return (v&&typeof v==="object"&&!Array.isArray(v))?v:{}; }catch(e){ return {}; } }
  var S=obj("dz_seen");
  function put(){ try{ localStorage.setItem("dz_seen",JSON.stringify(S)); }catch(e){} }
  var p=location.pathname;
  if(/\/highlights\/(index\.html)?$/.test(p)){ S.hl=jd(); put(); }
  if(/\/results\/(index\.html)?$/.test(p)){ S.rs=Date.now(); put(); }

  var now=Date.now(), rsNew=false, B=obj("dz_bets");
  Object.keys(B).forEach(function(k){
    var m=/^\d{2}_(\d{4})(\d{2})(\d{2})_\d{1,2}$/.exec(k), e=B[k], d=e&&typeof e.d==="string"?/^(\d{1,2}):(\d{2})$/.exec(e.d):null;
    if(!m||!d||!e||!Array.isArray(e.b)||!e.b.length) return;
    var t=Date.UTC(+m[1],+m[2]-1,+m[3],+d[1]-9,+d[2])+15*60e3;
    if(t<=now&&now-t<2*864e5&&(+S.rs||0)<t) rsNew=true;
  });
  var hlNew=S.hl!==jd();

  function mark(){
    var navs=document.querySelectorAll("nav.dzf-tb, nav.tb");
    if(!navs.length) return false;
    Array.prototype.forEach.call(navs,function(nav){
      Array.prototype.forEach.call(nav.querySelectorAll("a[href]"),function(a){
        var h=a.getAttribute("href")||"", on=/highlights\/$/.test(h)?hlNew:/results\/$/.test(h)?rsNew:null;
        if(on===null||a.getAttribute("aria-current")==="page"||a.classList.contains("on")) return;
        if(on&&!a.querySelector(".dz-dot")){
          var s=document.createElement("span"); s.className="dz-dot"; s.setAttribute("aria-hidden","true"); a.appendChild(s);
          a.setAttribute("aria-label",a.textContent.trim()+"（新しい内容あり）");
        }
      });
    });
    return true;
  }
  var st=document.createElement("style");
  st.textContent="nav.dzf-tb a,nav.tb a{position:relative}.dz-dot{position:absolute;top:8px;left:calc(50% + 8px);width:8px;height:8px;border-radius:50%;background:#7fb4ff;box-shadow:0 0 0 2px #0e1d30;pointer-events:none}";
  document.head.appendChild(st);
  if(!mark()) document.addEventListener("DOMContentLoaded",mark);
})();
