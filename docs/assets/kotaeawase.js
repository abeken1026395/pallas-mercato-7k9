/* 答え合わせ（再訪設計書 izonSekkei 段階2・2026-11-10）
   出走表で保存した買い目（dz_bets）・見送り（dz_skip）を、結果データ（/results/data/YYYYMMDD.json）と照らし合わせる。
   出走表・自分の記録・トップで共有する。保存データは引き継ぎなどで壊れていることがあるので、読むたびに形を確かめる。
   結果データは直近の約1か月ぶんしか置いていない。保存したレース・見送ったレースの結果は、届いたときに
   端末の dz_kekka へ必要な分だけ写しておき、サイトから消えたあとも答え合わせと振り返りを続ける（段階3・2026-11-11）。
   人気は /results/odds/YYYYMMDD.json（締切前の単勝オッズ・翌日の昼過ぎまでに入る）の順位を dz_kekka に写す */
(function(){
  var T={"3t":"3連単","3f":"3連複","2t":"2連単","2f":"2連複","kk":"拡連複","tn":"単勝","fk":"複勝"};
  var ARE=10000; /* 見送り成功の基準：3連単の配当がこれ以上（裁定B 2026-11-10） */
  var cache={}; /* hd -> {at, p(Promise), sig} */
  var TTL=5*60*1000;
  /* 更新の印（/results/data/now.json・直近2日の「取得時刻」とレース数・約100バイト）。2026-11-12
     結果データ（1日約0.2MB）を何度も読む代わりに、この印だけを15秒ごとに読み、変わった日だけ読み直す。
     印が読めないときは、従来どおり5分ごとに結果データを読み直す */
  var STTL=15*1000, stampC=null;
  function stamp(){
    var now=Date.now();
    if(stampC&&now-stampC.at<STTL) return stampC.p;
    var p=fetch("/results/data/now.json?_="+Math.floor(now/STTL),{cache:"no-store"}).then(function(r){ return r.ok?r.json():null; }).then(function(d){
      var o={}; if(d&&d.d&&typeof d.d==="object") Object.keys(d.d).forEach(function(hd){ var v=d.d[hd]; if(/^\d{8}$/.test(hd)&&v&&typeof v==="object") o[hd]=String(v.t||"")+"|"+String(v.n||""); });
      return o;
    }).catch(function(){ return null; });
    stampC={at:now,p:p};
    return p;
  }
  function okN(x){ return typeof x==="number"&&isFinite(x)&&x>=0&&x<1e9; }
  function obj(k){ try{ var v=JSON.parse(localStorage.getItem(k)||"{}"); return (v&&typeof v==="object"&&!Array.isArray(v))?v:{}; }catch(e){ return {}; } }
  /* 保存データ1レースぶんを、壊れた要素を捨てた形にそろえる */
  function entry(e){
    if(!e||typeof e!=="object"||Array.isArray(e)) return null;
    var b=(Array.isArray(e.b)?e.b:[]).filter(function(x){ return x&&typeof x==="object"&&T[x.t]&&Array.isArray(x.k); }).map(function(x){
      var o={t:x.t,k:x.k.filter(function(s){ return typeof s==="string"&&/^[1-6]([-=][1-6]){0,2}$/.test(s); })};
      if(x.m==="b"){ o.m="b"; o.s=(Array.isArray(x.s)?x.s:[]).filter(function(n){ return n>=1&&n<=6&&n===Math.floor(n); }); }
      if(okN(x.u)&&x.u>0) o.u=x.u; /* 買い目ごとの1点の金額（2026-11-14 けん：入力シートで金額も入れる） */
      /* 組ごとに割り振った金額（k と同じ並び・2026-11-14 けん：割り振りボタン） */
      if(Array.isArray(x.ku)&&x.ku.length===x.k.length&&o.k.length===x.k.length&&x.ku.every(function(n){ return okN(n)&&n>0; })) o.ku=x.ku.slice();
      return o;
    }).filter(function(x){ return x.k.length; });
    return {d:typeof e.d==="string"&&/^\d{1,2}:\d{2}$/.test(e.d)?e.d:"",b:b,a:okN(e.a)?e.a:null,p:okN(e.p)?e.p:null,u:okN(e.u)&&e.u>0?e.u:null};
  }
  var KK="dz_kekka";
  /* 写しの1レースぶん：{f:[1着,2着,3着], P:{"3連単":[["1-2-3",配当],…],…}, o:"人気の順位6桁（0は不明）"} */
  function kk(){ return obj(KK); }
  function kkSave(m){ try{ localStorage.setItem(KK,JSON.stringify(m)); }catch(e){} }
  /* 写しから、結果データと同じ形のレースを作る。壊れた写しは null */
  function fromKK(e){
    if(!e||typeof e!=="object"||!e.P||typeof e.P!=="object") return null;
    var P={};
    Object.keys(e.P).forEach(function(t){ if(Array.isArray(e.P[t])) P[t]=e.P[t].filter(function(w){ return Array.isArray(w)&&typeof w[0]==="string"&&okN(w[1]); }).map(function(w){ return {"組番":w[0],"配当":w[1]}; }); });
    var r={"払戻":P};
    if(Array.isArray(e.f)) [0,1,2].forEach(function(i){ var n=e.f[i]; if(n>=1&&n<=6&&n===Math.floor(n)) r[(i+1)+"着"]=n; });
    return r;
  }
  /* 届いた結果のうち、保存・見送りのあるレースだけを写す。券種は買った券種と3連単（見送りの判定用）だけ */
  function keep(m){
    var B=obj("dz_bets"), S=obj("dz_skip"), K=kk(), ch=false;
    Object.keys(m).forEach(function(rid){
      var en=entry(B[rid]), sk=S[rid]&&typeof S[rid]==="object";
      if(!(en&&en.b.length)&&!sk) return;
      var race=m[rid], P=race["払戻"], ts={"3連単":1};
      if(en) en.b.forEach(function(x){ ts[T[x.t]]=1; });
      var e=K[rid]&&typeof K[rid]==="object"?K[rid]:{}, o={f:[race["1着"],race["2着"],race["3着"]].map(function(n){ return n>=1&&n<=6?n:0; }),P:{}};
      Object.keys(ts).forEach(function(t){ if(Array.isArray(P[t])) o.P[t]=P[t].filter(function(w){ return w&&typeof w["組番"]==="string"&&okN(w["配当"]); }).map(function(w){ return [w["組番"],w["配当"]]; }); });
      if(typeof e.o==="string") o.o=e.o;
      if(JSON.stringify(o)!==JSON.stringify({f:e.f,P:e.P,o:e.o})){ K[rid]=o; ch=true; }
    });
    if(ch) kkSave(K);
  }
  /* 単勝オッズ6つを人気の順位にする。同じオッズは同じ順位。欠場など（null・0）は0 */
  function ranks(a){
    if(!Array.isArray(a)||a.length!==6) return "";
    return a.map(function(v){ if(!(typeof v==="number"&&v>0&&isFinite(v))) return 0; var n=1; a.forEach(function(w){ if(typeof w==="number"&&w>0&&w<v) n++; }); return Math.min(n,6); }).join("");
  }
  var ocache={};
  /* その日の人気を写す（保存したレースのうち、まだ人気の無いものだけ）。届いていない日は何もしない */
  function ninki(hd){
    if(!/^\d{8}$/.test(hd)) return Promise.resolve(false);
    if(ocache[hd]) return ocache[hd];
    var p=fetch("/results/odds/"+hd+".json",{cache:"no-store"}).then(function(r){ return r.ok?r.json():null; }).then(function(d){
      var W=d&&d["単勝"]; if(!W||typeof W!=="object") return false;
      var B=obj("dz_bets"), K=kk(), ch=false;
      Object.keys(B).forEach(function(rid){
        var q=rid.split("_"); if(q[1]!==hd) return;
        var row=W[q[0]]&&W[q[0]][String(+q[2])], rk=ranks(row);
        if(!rk) return;
        var e=K[rid]&&typeof K[rid]==="object"?K[rid]:{};
        if(e.o!==rk){ e.o=rk; K[rid]=e; ch=true; }
      });
      if(ch) kkSave(K);
      return ch;
    }).catch(function(){ delete ocache[hd]; return false; });
    ocache[hd]=p;
    return p;
  }
  /* 1レースの写し（人気・1着）。無ければ null */
  function kkGet(rid){ var e=kk()[rid]; return e&&typeof e==="object"?e:null; }
  function points(en){ var n=0; en.b.forEach(function(x){ n+=x.k.length; }); return n; }
  /* その日の結果を読む。返すのは {"12_20261110_5": レース, …}
     更新の印が前回と同じなら使い回し、変わっていたらすぐ読み直す。印に載らない日（3日以上前）は5分のあいだ使い回す */
  function day(hd){
    if(!/^\d{8}$/.test(hd)) return Promise.resolve({});
    return stamp().then(function(s){
      var sig=s&&s[hd]?s[hd]:null, c=cache[hd], now=Date.now();
      if(c&&(sig?c.sig===sig:(now-c.at<TTL))) return c.p;
      return load(hd,sig,now);
    });
  }
  function load(hd,sig,now){
    var p=fetch("/results/data/"+hd+".json?_="+encodeURIComponent(sig||String(Math.floor(now/TTL))),{cache:"no-store"}).then(function(r){ return r.ok?r.json():null; }).then(function(d){
      var m={};
      if(d&&Array.isArray(d["場"])) d["場"].forEach(function(v){
        if(!v||!Array.isArray(v["レース"])) return;
        v["レース"].forEach(function(r){
          var j=String((r&&r["場コード"])||v["場コード"]||""), n=parseInt(r&&r["レース"],10);
          if(/^\d{2}$/.test(j)&&n>=1&&n<=12&&r["払戻"]&&typeof r["払戻"]==="object") m[j+"_"+hd+"_"+n]=r;
        });
      });
      try{ keep(m); }catch(e){}
      /* サイトから消えた日は、写しから戻す */
      var K=kk(); Object.keys(K).forEach(function(rid){ if(rid.split("_")[1]===hd&&!m[rid]){ var r=fromKK(K[rid]); if(r) m[rid]=r; } });
      return m;
    }).catch(function(){ var m={},K=kk(); Object.keys(K).forEach(function(rid){ if(rid.split("_")[1]===hd){ var r=fromKK(K[rid]); if(r) m[rid]=r; } }); return m; });
    cache[hd]={at:now,p:p,sig:sig};
    return p;
  }
  /* 画面が見えているあいだ fn を15秒ごとに呼ぶ。別のアプリやタブから戻ったときはすぐ呼ぶ。
     fn が false を返したら（結果待ちのレースが無い）止める。後で live(fn) をまた呼べば動き出す */
  var lives=[];
  function tick(){ lives=lives.filter(function(f){ try{ return f()!==false; }catch(e){ return false; } }); if(!lives.length&&liveT){ clearInterval(liveT); liveT=0; } }
  var liveT=0;
  function live(fn){
    if(typeof fn!=="function") return;
    if(lives.indexOf(fn)<0) lives.push(fn);
    if(!liveT) liveT=setInterval(function(){ if(document.visibilityState==="visible") tick(); },STTL);
  }
  document.addEventListener("visibilitychange",function(){ if(document.visibilityState==="visible"&&lives.length) tick(); });
  window.addEventListener("pageshow",function(e){ if(e.persisted&&lives.length) tick(); });
  /* 1レースの答え合わせ。race は day() のレース（無ければ null）
     state：pending（結果待ち）／hit（的中）／miss（外れ）
     a・p は記録に使う額。手で入れた額があればそれを優先し、無ければ「1点あたり」から計算する */
  function judge(en,race){
    var r={state:"pending",hits:[],pay100:0,pts:points(en),a:en.a,p:en.p,autoA:false,autoP:false,san:null,dflt:false,even:null};
    /* 買い目ごとに1点の金額（x.u）があれば、それを先に使う。無い買い目はレースの1点の金額（en.u）を使う（2026-11-14） */
    var per=en.b.some(function(x){ return x.u||x.ku; }), allPer=en.b.length&&en.b.every(function(x){ return x.u||x.ku; });
    /* 金額を何も入れていないレースは、1点100円で均等に買ったとして出す（2026-11-12 けん裁定） */
    var u=en.u;
    if(!u&&en.a==null&&en.p==null){ u=100; r.dflt=!allPer; }
    /* 購入額がちょうど 100円×点数 なら、ボタンを押さなくても均等として払戻を出す */
    if(!u&&en.a!=null&&en.p==null&&r.pts&&en.a===r.pts*100) u=100;
    function uOf(x){ return x.u||u||null; }
    function kOf(x,i){ return x.ku?x.ku[i]:uOf(x); }
    var full=en.b.every(function(x){ return x.ku||uOf(x); }), us={};
    en.b.forEach(function(x){ if(x.ku) x.ku.forEach(function(n){ us[n]=1; }); else us[uOf(x)]=1; });
    r.u=full&&Object.keys(us).length===1?+Object.keys(us)[0]:(per?null:(u||null));
    if(en.a==null&&full&&r.pts){ r.a=0; en.b.forEach(function(x){ x.k.forEach(function(k,i){ r.a+=kOf(x,i); }); }); r.autoA=true; }
    /* 購入額だけが入っていて、点数で割って100円単位なら「均等に買った」ボタンの候補 */
    if(!u&&!per&&en.a!=null&&r.pts&&en.a>0&&en.a%r.pts===0&&(en.a/r.pts)%100===0) r.even=en.a/r.pts;
    if(!r.pts){ r.state="none"; return r; }  /* 金額やメモだけで、買い目が無いレース */
    if(!race) return r;
    var P=race["払戻"], s3=Array.isArray(P["3連単"])&&P["3連単"][0]&&okN(P["3連単"][0]["配当"])?P["3連単"][0]["配当"]:null, payU=0;
    r.san=s3;
    en.b.forEach(function(x){
      var arr=Array.isArray(P[T[x.t]])?P[T[x.t]]:[];
      x.k.forEach(function(k,i){
        arr.forEach(function(w){ if(w&&w["組番"]===k&&okN(w["配当"])){ r.hits.push({t:x.t,k:k,pay:w["配当"]}); r.pay100+=w["配当"]; payU+=w["配当"]*(kOf(x,i)||0)/100; } });
      });
    });
    r.state=r.hits.length?"hit":"miss";
    if(en.p==null&&full){ r.p=Math.round(payU); r.autoP=true; }
    return r;
  }
  /* 見送ったレースの判定：結果があり、3連単の配当が基準以上なら成功 */
  function skipJudge(race){
    if(!race) return {state:"pending",san:null};
    var P=race["払戻"], s3=Array.isArray(P["3連単"])&&P["3連単"][0]&&okN(P["3連単"][0]["配当"])?P["3連単"][0]["配当"]:null;
    return {state:s3==null?"pending":(s3>=ARE?"good":"plain"),san:s3};
  }
  window.DZK={T:T,ARE:ARE,obj:obj,entry:entry,points:points,day:day,live:live,judge:judge,skipJudge:skipJudge,okN:okN,ninki:ninki,kkGet:kkGet,ranks:ranks,kkRace:function(rid){ return fromKK(kk()[rid]); }};
})();
