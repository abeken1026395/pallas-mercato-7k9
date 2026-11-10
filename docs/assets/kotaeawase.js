/* 答え合わせ（再訪設計書 izonSekkei 段階2・2026-11-10）
   出走表で保存した買い目（dz_bets）・見送り（dz_skip）を、結果データ（/results/data/YYYYMMDD.json）と照らし合わせる。
   出走表・自分の記録・トップで共有する。保存データは引き継ぎなどで壊れていることがあるので、読むたびに形を確かめる。
   結果データは直近の約1か月ぶんしか置いていないので、古い日は「結果データなし」になる */
(function(){
  var T={"3t":"3連単","3f":"3連複","2t":"2連単","2f":"2連複","kk":"拡連複","tn":"単勝","fk":"複勝"};
  var ARE=10000; /* 見送り成功の基準：3連単の配当がこれ以上（裁定B 2026-11-10） */
  var cache={}; /* hd -> {at, p(Promise), map} */
  var TTL=5*60*1000;
  function okN(x){ return typeof x==="number"&&isFinite(x)&&x>=0&&x<1e9; }
  function obj(k){ try{ var v=JSON.parse(localStorage.getItem(k)||"{}"); return (v&&typeof v==="object"&&!Array.isArray(v))?v:{}; }catch(e){ return {}; } }
  /* 保存データ1レースぶんを、壊れた要素を捨てた形にそろえる */
  function entry(e){
    if(!e||typeof e!=="object"||Array.isArray(e)) return null;
    var b=(Array.isArray(e.b)?e.b:[]).filter(function(x){ return x&&typeof x==="object"&&T[x.t]&&Array.isArray(x.k); }).map(function(x){
      var o={t:x.t,k:x.k.filter(function(s){ return typeof s==="string"&&/^[1-6]([-=][1-6]){0,2}$/.test(s); })};
      if(x.m==="b"){ o.m="b"; o.s=(Array.isArray(x.s)?x.s:[]).filter(function(n){ return n>=1&&n<=6&&n===Math.floor(n); }); }
      return o;
    }).filter(function(x){ return x.k.length; });
    return {d:typeof e.d==="string"&&/^\d{1,2}:\d{2}$/.test(e.d)?e.d:"",b:b,a:okN(e.a)?e.a:null,p:okN(e.p)?e.p:null,u:okN(e.u)&&e.u>0?e.u:null};
  }
  function points(en){ var n=0; en.b.forEach(function(x){ n+=x.k.length; }); return n; }
  /* その日の結果を読む（同じ日は5分のあいだ使い回す）。返すのは {"12_20261110_5": レース, …} */
  function day(hd){
    if(!/^\d{8}$/.test(hd)) return Promise.resolve({});
    var c=cache[hd], now=Date.now();
    if(c&&(now-c.at<TTL)) return c.p;
    var p=fetch("/results/data/"+hd+".json?_="+Math.floor(now/TTL),{cache:"no-store"}).then(function(r){ return r.ok?r.json():null; }).then(function(d){
      var m={};
      if(d&&Array.isArray(d["場"])) d["場"].forEach(function(v){
        if(!v||!Array.isArray(v["レース"])) return;
        v["レース"].forEach(function(r){
          var j=String((r&&r["場コード"])||v["場コード"]||""), n=parseInt(r&&r["レース"],10);
          if(/^\d{2}$/.test(j)&&n>=1&&n<=12&&r["払戻"]&&typeof r["払戻"]==="object") m[j+"_"+hd+"_"+n]=r;
        });
      });
      return m;
    }).catch(function(){ return {}; });
    cache[hd]={at:now,p:p};
    return p;
  }
  /* 1レースの答え合わせ。race は day() のレース（無ければ null）
     state：pending（結果待ち）／hit（的中）／miss（外れ）
     a・p は記録に使う額。手で入れた額があればそれを優先し、無ければ「1点あたり」から計算する */
  function judge(en,race){
    var r={state:"pending",hits:[],pay100:0,pts:points(en),a:en.a,p:en.p,autoA:false,autoP:false,san:null};
    if(en.a==null&&en.u){ r.a=r.pts*en.u; r.autoA=true; }
    if(!r.pts){ r.state="none"; return r; }  /* 金額やメモだけで、買い目が無いレース */
    if(!race) return r;
    var P=race["払戻"], s3=Array.isArray(P["3連単"])&&P["3連単"][0]&&okN(P["3連単"][0]["配当"])?P["3連単"][0]["配当"]:null;
    r.san=s3;
    en.b.forEach(function(x){
      var arr=Array.isArray(P[T[x.t]])?P[T[x.t]]:[];
      x.k.forEach(function(k){
        arr.forEach(function(w){ if(w&&w["組番"]===k&&okN(w["配当"])){ r.hits.push({t:x.t,k:k,pay:w["配当"]}); r.pay100+=w["配当"]; } });
      });
    });
    r.state=r.hits.length?"hit":"miss";
    if(en.p==null&&en.u){ r.p=Math.round(r.pay100*en.u/100); r.autoP=true; }
    return r;
  }
  /* 見送ったレースの判定：結果があり、3連単の配当が基準以上なら成功 */
  function skipJudge(race){
    if(!race) return {state:"pending",san:null};
    var P=race["払戻"], s3=Array.isArray(P["3連単"])&&P["3連単"][0]&&okN(P["3連単"][0]["配当"])?P["3連単"][0]["配当"]:null;
    return {state:s3==null?"pending":(s3>=ARE?"good":"plain"),san:s3};
  }
  window.DZK={T:T,ARE:ARE,obj:obj,entry:entry,points:points,day:day,judge:judge,skipJudge:skipJudge,okN:okN};
})();
