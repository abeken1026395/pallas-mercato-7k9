/* 推しモーター（2026-11-10 けん裁定 A〜F）
   出走表・モーター・モーター整備・見どころ・トップで共有する。
   保存先：端末内 dz_oshiMotor（/hikae/ の引き継ぎ対象）。形式 {"12_45": 付けた時刻(ms)} ＝ 場コード2桁_機番
   上限20機。付けた日より後にその場のモーターが新替になったら自動で外し、1回だけ知らせる（docs/data/motorReplace.json）
   壊れた値は読むたびに捨てる。外から来た文字列は画面に入れない（場名は下の固定表、機番は数字だけ）
   使い方：DZOM.btn(場コード,機番,"text"|"icon") でボタンのHTML、DZOM.mark(場コード,機番) で印のHTML。
   押したときの処理と、画面の中のボタン・印の切り替えはこのファイルがまとめて行う（document の capture で受ける） */
(function(){
  if(window.DZOM) return;
  var KEY="dz_oshiMotor", GONE="dzomGone", MAX=20;
  var VN={"01":"桐生","02":"戸田","03":"江戸川","04":"平和島","05":"多摩川","06":"浜名湖","07":"蒲郡","08":"常滑","09":"津","10":"三国","11":"びわこ","12":"住之江","13":"尼崎","14":"鳴門","15":"丸亀","16":"児島","17":"宮島","18":"徳山","19":"下関","20":"若松","21":"芦屋","22":"福岡","23":"唐津","24":"大村"};
  var src=(document.currentScript&&document.currentScript.src)||"";

  function jd(t){ return new Date((t||Date.now())+9*3600e3).toISOString().slice(0,10).replace(/-/g,""); }
  function key(j,m){
    var js=String(j==null?"":j).trim(), ms=String(m==null?"":m).trim();
    if(/^\d$/.test(js)) js="0"+js;
    if(!VN[js] || !/^\d{1,3}$/.test(ms)) return null;
    var n=parseInt(ms,10); if(!(n>=1&&n<=999)) return null;
    return js+"_"+n;
  }
  function read(){
    var o={}, raw;
    try{ raw=JSON.parse(localStorage.getItem(KEY)||"{}"); }catch(e){ raw={}; }
    if(!raw||typeof raw!=="object"||Array.isArray(raw)) raw={};
    var lim=Date.now()+864e5;
    Object.keys(raw).forEach(function(k){
      var p=/^(\d{2})_(\d{1,3})$/.exec(k), t=raw[k];
      if(!p) return;
      var kk=key(p[1],p[2]);
      if(kk!==k) return;
      if(typeof t!=="number"||!isFinite(t)||t<=0||t>lim) return;
      o[k]=t;
    });
    var ks=Object.keys(o);
    if(ks.length>MAX){ ks.sort(function(a,b){ return o[b]-o[a]; }).slice(MAX).forEach(function(k){ delete o[k]; }); }
    return o;
  }
  function write(o){ try{ localStorage.setItem(KEY,JSON.stringify(o)); }catch(e){} }
  var S=read();

  function has(j,m){ var k=key(j,m); return !!(k&&S[k]); }
  function name(j,m){ var k=key(j,m); if(!k) return ""; var p=k.split("_"); return VN[p[0]]+" "+p[1]+"号機"; }
  function list(){
    return Object.keys(S).sort(function(a,b){ return S[b]-S[a]; }).map(function(k){
      var p=k.split("_"); return {k:k, j:p[0], m:+p[1], t:S[k], name:VN[p[0]]+" "+p[1]+"号機"};
    });
  }

  /* 図柄：船外機（カバー・脚・板・ギアケース・プロペラ）。推し選手の星と形で見分ける。色は文字色を継ぐ。
     ボタンは付けていないとき線だけ・付けたとき塗り（色だけで状態を伝えない） */
  function icon(line){
    var a=line?' fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"':' fill="currentColor"';
    return '<svg class="dzom-ic"'+(line?' data-line="1"':'')+' viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" focusable="false">'
      +'<rect x="2.7" y="1" width="8.6" height="5" rx="2.5"'+a+'/>'
      +'<rect x="6" y="6" width="2.6" height="5.6"'+a+'/>'
      +'<rect x="3.3" y="8.2" width="8" height="1.3" rx=".65"'+a+'/>'
      +'<ellipse cx="7.3" cy="12.8" rx="2.7" ry="1.5"'+a+'/>'
      +'<rect x="10.6" y="10.9" width="1.6" height="3.8" rx=".8"'+a+'/></svg>';
  }
  function btn(j,m,mode){
    var k=key(j,m); if(!k) return "";
    var on=!!S[k], nm=name(j,m);
    return '<button type="button" class="dzom-btn'+(mode==="icon"?" dzom-i":"")+(on?" on":"")+'" data-om="'+k+'" aria-pressed="'+(on?"true":"false")+'"'
      +' aria-label="'+nm+(on?"のフォローを解除":"をフォロー")+'">'+icon(!on)
      +(mode==="icon"?"":'<span class="dzom-t">'+(on?"推しフォロー中":"推しフォローする")+'</span>')+'</button>';
  }
  function mark(j,m){
    var k=key(j,m); if(!k) return "";
    return '<span class="dzom-mk" data-om="'+k+'" role="img" aria-label="推しモーター"'+(S[k]?"":" hidden")+'>'+icon()+'</span>';
  }
  /* 機番の並びの中に推しがあるか（レース単位の印に使う） */
  function anyIn(j,ms){ return (ms||[]).some(function(m){ return has(j,m); }); }

  function refresh(){
    Array.prototype.forEach.call(document.querySelectorAll(".dzom-btn[data-om]"),function(b){
      var k=b.getAttribute("data-om"), on=!!S[k], p=k.split("_"), nm=(VN[p[0]]||"")+" "+p[1]+"号機";
      b.classList.toggle("on",on);
      b.setAttribute("aria-pressed",on?"true":"false");
      b.setAttribute("aria-label",nm+(on?"のフォローを解除":"をフォロー"));
      var t=b.querySelector(".dzom-t"); if(t) t.textContent=on?"推しフォロー中":"推しフォローする";
      var ic=b.querySelector(".dzom-ic"); if(ic&&(ic.getAttribute("data-line")==="1")===on) ic.outerHTML=icon(!on);
    });
    Array.prototype.forEach.call(document.querySelectorAll(".dzom-mk[data-om]"),function(s){ s.hidden=!S[s.getAttribute("data-om")]; });
  }
  function fire(){ refresh(); try{ document.dispatchEvent(new CustomEvent("dzom:change")); }catch(e){} }

  function toggle(j,m){
    var k=key(j,m); if(!k) return null;
    S=read();
    if(S[k]){ delete S[k]; write(S); fire(); return "off"; }
    if(Object.keys(S).length>=MAX){ toast("推しモーターは"+MAX+"機までです。どれかを外すと付けられます。"); return "limit"; }
    S[k]=Date.now(); write(S); fire(); return "on";
  }

  /* 知らせ（role=status）。動きは不透明度だけ・動きを減らす設定では動かさない。点滅・音・振動なし */
  var tEl=null, tTimer=0;
  function toast(msg,keep){
    if(!document.body) return;
    if(!tEl){
      tEl=document.createElement("div"); tEl.className="dzom-toast"; tEl.setAttribute("role","status"); tEl.setAttribute("aria-live","polite");
      document.body.appendChild(tEl);
    }
    tEl.innerHTML='<span class="dzom-tm"></span>'+(keep?'<button type="button" class="dzom-tx">閉じる</button>':"");
    tEl.firstChild.textContent=msg;
    var c=tEl.querySelector(".dzom-tx"); if(c) c.onclick=function(){ tEl.classList.remove("show"); };
    tEl.classList.add("show");
    clearTimeout(tTimer);
    if(!keep) tTimer=setTimeout(function(){ tEl.classList.remove("show"); },3500);
  }

  /* 新替で外す。付けた日（JST）より後で、今日までに来た新替だけを見る */
  function prune(){
    if(!Object.keys(S).length) return;
    var u; try{ u=new URL("../data/motorReplace.json",src||location.href).href; }catch(e){ return; }
    fetch(u,{cache:"no-store"}).then(function(r){ return r.ok?r.json():null; }).catch(function(){ return null; }).then(function(R){
      if(!R||typeof R!=="object") return;
      S=read();
      var today=jd(), gone=[];
      Object.keys(S).forEach(function(k){
        var rep=R[k.split("_")[0]], d=rep&&typeof rep==="object"?String(rep["新替日"]||""):"";
        if(/^\d{8}$/.test(d) && d>jd(S[k]) && d<=today){ gone.push(k); delete S[k]; }
      });
      if(!gone.length) return;
      write(S); fire();
      var g; try{ g=JSON.parse(localStorage.getItem(GONE)||"[]"); }catch(e){ g=[]; }
      if(!Array.isArray(g)) g=[];
      gone.forEach(function(k){ if(g.indexOf(k)<0) g.push(k); });
      try{ localStorage.setItem(GONE,JSON.stringify(g.slice(-MAX))); }catch(e){}
      notice();
    });
  }
  /* 外したことを1回だけ知らせる（見せたら消す） */
  function notice(){
    var g; try{ g=JSON.parse(localStorage.getItem(GONE)||"[]"); }catch(e){ g=[]; }
    if(!Array.isArray(g)) g=[];
    var ns=g.map(function(k){ var p=/^(\d{2})_(\d{1,3})$/.exec(String(k)); return p&&VN[p[1]]?VN[p[1]]+" "+(+p[2])+"号機":""; }).filter(Boolean);
    try{ localStorage.removeItem(GONE); }catch(e){}
    if(!ns.length) return;
    toast("新替で別のモーターになったため、推しフォローを外しました："+(ns.length<=3?ns.join("・"):ns.slice(0,3).join("・")+" ほか"+(ns.length-3)+"機"),true);
  }

  document.addEventListener("click",function(e){
    var b=e.target&&e.target.closest?e.target.closest(".dzom-btn[data-om]"):null;
    if(!b) return;
    e.preventDefault(); e.stopPropagation();
    var p=b.getAttribute("data-om").split("_");
    toggle(p[0],p[1]);
  },true);
  window.addEventListener("storage",function(e){ if(e.key===KEY){ S=read(); fire(); } });
  window.addEventListener("pageshow",function(e){ if(e.persisted){ S=read(); fire(); } });

  var st=document.createElement("style");
  st.textContent=".dzom-ic{display:block;flex:none}"
    +".dzom-btn{display:inline-flex;align-items:center;justify-content:center;gap:6px;min-height:44px;min-width:44px;padding:0 12px;margin:0;border:1px solid #3a4a5c;border-radius:999px;background:none;color:#9fb0c3;font-family:inherit;font-weight:700;font-size:13px;line-height:1;cursor:pointer;touch-action:manipulation;white-space:nowrap;flex:none}"
    +".dzom-btn .dzom-ic{width:20px;height:20px}"
    +".dzom-btn.dzom-i{padding:0;border-color:transparent}"
    +".dzom-btn.on{color:#7fb4ff;border-color:#7fb4ff}"
    +".dzom-btn.dzom-i.on{border-color:transparent}"
    +".dzom-btn:active{opacity:.6}"
    +".dzom-btn:focus-visible{outline:2px solid #7fb4ff;outline-offset:2px}"
    +".dzom-mk{display:inline-flex;align-items:center;vertical-align:-2px;color:#7fb4ff;margin-left:4px}"
    +".dzom-mk[hidden]{display:none}"
    +".dzom-toast{position:fixed;left:12px;right:12px;bottom:calc(70px + env(safe-area-inset-bottom));z-index:80;max-width:560px;margin:0 auto;display:flex;align-items:center;gap:10px;padding:10px 14px;background:#1c2a3a;border:1px solid #3a4a5c;border-radius:8px;color:#e0e6ed;font-size:14px;line-height:1.6;opacity:0;pointer-events:none;transition:opacity .15s ease-out}"
    +".dzom-toast.show{opacity:1;pointer-events:auto}"
    +".dzom-tm{flex:1;min-width:0}"
    +".dzom-tx{flex:none;min-height:44px;padding:0 12px;border:1px solid #3a4a5c;border-radius:999px;background:none;color:#e0e6ed;font-family:inherit;font-weight:700;font-size:13px;line-height:1;cursor:pointer}"
    +"@media (prefers-reduced-motion:reduce){.dzom-toast{transition:none}}";
  (document.head||document.documentElement).appendChild(st);

  window.DZOM={has:has,name:name,list:list,btn:btn,mark:mark,anyIn:anyIn,toggle:toggle,refresh:refresh,icon:icon,max:MAX};
  if(document.readyState==="loading") document.addEventListener("DOMContentLoaded",function(){ notice(); prune(); });
  else { notice(); prune(); }
})();
