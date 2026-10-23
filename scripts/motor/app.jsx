// モーター成績の読みやすさ改修（2026-10-23 けん「モーターページ非常に見づらい改善しろ」・実験場 docs/next/motorE で作り、10-24 本番へ）。
// 見た目と並べ方だけを変えた。データの読み方・判定は前と同じ。
const { useState, useMemo, useEffect } = React;
const R = window.__D;
const cols = R.columns;

/* ===== 表示の定数（同じ値を2箇所に書かない。METHOD.md 9節・受け入れ基準10）===== */

// 文字色。すべて背景 #0b1219〜#26333f 上でコントラスト 4.5:1 以上（AA・METHOD.md 9節）。
// 増やさない。1色1意味。
const C = {
  text:   "#eef2f5",  // 本文・数字
  sub:    "#c8d3dd",  // 補助本文
  label:  "#a9b8c6",  // 見出し・ラベル
  muted:  "#93a5b6",  // 注記
  dim:    "#93a5b6",
  accent: "#eef2f5",
  link:   "#eef2f5",  // 選手名（リンクでも色は本文と同じ。下線だけで示す）
  fem:    "#ff9ec9",
  ok:     "#8fd6c0",
  onLight:"#0b1219",
  top:    "#f5d55c",  // 超抜（トップの見どころと同じ黄）
  line:   "#2b4568",  // 罫線
};

// 文字サイズ。本文は13px以上、select と input は16px（iOS Safari の自動ズーム回避）。
const F = { xs:13, sm:14, md:15, lg:16, xl:17, hero:20, input:16 };

// docs/data/motorUsage.json の形式印。scripts/buildMotorUsage.py の SCHEMA と揃えること。
// 場ごとの集計窓（venues）を持たない旧形式は走行数を1行も出さない。
const USAGE_SCHEMA = "venueWindow-1";
// 場カードの既定表示機数。「残り◯機を見る」で全機。
const TOP_N = 3;
// 整備履歴の既定表示：部品交換のあった走＋直近この走数。
const KARTE_TAIL = 5;
// タップ対象の下限（WCAG 2.2 / 2.5.8 ターゲットサイズ AA）。
const HIT = 24;

/* ===== 場フォロー（場ページ /stadium/ と共有。キー br_stadium ／ 形式 [{code,name}] ／ code は2桁文字列。ここでは表示と並べ替えのみ・登録は場ページ） ===== */
function lsGet(k,d){ try{ var v=localStorage.getItem(k); return v?JSON.parse(v):d; }catch(e){ return d; } }
function pinCode(c){ var t=String(c==null?"":c); return t.length===1 ? "0"+t : t; }
function loadPin(){ var a=lsGet("br_stadium",[]); return Array.isArray(a)?a:[]; }
function hasPin(list,code){ return list.some(function(p){ return p && pinCode(p.code)===pinCode(code); }); }

// 列名を部分一致で探す（列順・表記ゆれに強くする）
function findCol(cands){ for(const c of cands){ const i=cols.findIndex(h=>String(h).includes(c)); if(i>=0) return i; } return -1; }
const CI = {
  venue: findCol(["場名"]),
  mno:   findCol(["モーター番号","機番"]),
  name:  findCol(["選手名","氏名"]),
  toban: findCol(["登録番号","登番"]),
  grade: findCol(["級別"]),
  rate:  findCol(["2連対率","2連率","２連対率","２連率"]),
  hd:    findCol(["開催日"]),
  jcd:   findCol(["場コード"]),
};

// バーの目盛上限。当日データの最大2連率を10%刻みで切り上げた値を全場共通で使う。
// 固定50%では50%超が満杯になって頭打ちし、上位機どうしの差が読めなくなっていた（実測最大72.7%）。
// 「同型のものは同一スケールで並べる」（METHOD.md 9節）。
const BAR_MAX = (()=>{
  let mx = 0;
  for(const r of R.data){ const v = parseFloat(r[CI.rate]); if(isFinite(v) && v>mx) mx = v; }
  return Math.max(10, Math.ceil(mx/10)*10);
})();

// 場ごとの2連率中央値。バーに細い縦線で重ねて「その場の真ん中」を示す。
// 検索で行が絞られても線が動かないよう、当日データ全件から場単位で1度だけ出す。
const VENUE_MEDIAN = (()=>{
  const g = {};
  for(const r of R.data){
    const v = r[CI.venue]||"その他";
    const n = parseFloat(r[CI.rate]);
    if(isFinite(n)) (g[v]=g[v]||[]).push(n);
  }
  const m = {};
  for(const v in g){
    const a = g[v].sort((x,y)=>x-y), k = a.length;
    m[v] = k%2 ? a[(k-1)/2] : (a[k/2-1]+a[k/2])/2;
  }
  return m;
})();

// 場ごとの相対順位でランクを決める（絶対値の跳ねに依存しない）。
// 各場の2連率降順で位置を出し、上位の割合で段階付け。
// pos=1始まりの場内順位、total=その場の機数。
// color=バー・帯（図形）／tcolor=同じ意味を持つ文字（AA 4.5:1 を満たす明るさに寄せた対）。
// 図形と文字で色を分けているのは、図の濃淡の序列を保ったまま文字のコントラストだけ上げるため。
const RK = {
  na:  {key:"na",  label:"—",   color:"#556579", tcolor:C.muted},
  top: {key:"top", label:"超抜", color:"#f2c200", tcolor:C.top},
  hi:  {key:"hi",  label:"上位", color:"#8fa6bd", tcolor:C.sub},
  mid: {key:"mid", label:"普通", color:"#7c94ab", tcolor:C.label},
  low: {key:"low", label:"下位", color:"#5d7186", tcolor:C.muted},
};
function rankByPos(pos, total, rate, usage, fresh){
  if(!total || !pos) return RK.na;
  // 新替から5節は機力が見えにくい（通説・2026-10-01 けん裁定）。その場の全機に序列を付けない。
  if(fresh) return RK.na;
  // 実績のない機・走行数が少ない機に序列を付けない（新替直後など）。
  // 全機0.0%の場で先頭3機が「超抜」になるのを防ぐ。
  const _v = parseFloat(rate);
  if(!isFinite(_v) || _v <= 0) return RK.na;
  const _runs = usage ? Number(usage["走"]) : NaN;
  if(isFinite(_runs) && _runs > 0 && _runs < 10) return RK.na;
  if(pos <= 3) return RK.top;
  const r = pos / total;
  if(r <= 0.40) return RK.hi;
  if(r <= 0.75) return RK.mid;
  return RK.low;
}
function isB(g){ return String(g).includes("B"); }
// B級×高機力＝妙味（人気が落ちやすい構造。判断は読者に委ねる）。
// 場内で上位40%以内のモーターにB級が乗っている状態。
function myoumi(g, rk){ return false; }  // 2026-10-01 けん裁定でやめた（妙味は推しに見えるため）

// 級別バッジ。白文字では #e05a5a が 3.63、#5a7fe0 が 3.79 で AA 未達だったため、
// 地色はそのままに文字を暗色へ反転した（5.18／4.98／4.57）。「超抜」バッジと同じ作法。
const gradeColor = g => String(g).startsWith("A")?"#e05a5a":String(g).startsWith("B")?"#86a6cf":"#6b7f95";

// 節名は長いので末尾を…で省略（表示用のみ・原文はtitle属性で保持）。
function truncStr(s,n){ s=String(s||""); return s.length>n ? s.slice(0,n)+"…" : s; }

// 選手名の全角パディング（"峰　　　竜太"）を表示だけ1つに畳む。
// CSVの生値は桁揃えのために全角空白が入っている。検索・照合は生値のまま行う（ここは表示専用）。
function dispName(s){ return String(s||"").replace(/[　\s]+/g,"　").replace(/^　|　$/g,""); }

// 場カード用：節名（省略）＋日目チップの2行目。metaが無ければ何も描かない（既存表示を壊さない）。
function VenueMetaLine({meta}){
  if(!meta) return null;
  const setsu = String(meta["節名"]||"");
  const nichime = String(meta["日目"]||"");
  if(!setsu && !nichime) return null;
  return (
    <div style={{fontSize:F.xs,color:C.sub,marginTop:2,minWidth:0}}>
      {setsu && <span title={setsu}>{truncStr(setsu,20)}</span>}{setsu && nichime ? "　" : ""}{nichime && <b style={{color:C.text}}>{nichime}</b>}
    </div>
  );
}

// 二層開閉ボタン。見た目は控えめでも当たり判定は 24px 以上を確保する
//（小さいボタンは見た目の問題ではなく押し間違いの問題・METHOD.md 9節）。
function MoreBtn({onClick,children,mt}){
  return (
    <button type="button" onClick={onClick}
      style={{display:"flex",alignItems:"center",justifyContent:"center",width:"100%",
        minHeight:44,marginTop:mt||0,padding:"8px 14px",
        background:"transparent",color:C.sub,border:"none",borderTop:"1px solid "+C.line,
        fontSize:F.sm,fontWeight:700,cursor:"pointer",fontFamily:"inherit"}}>{children}</button>
  );
}

function Bar({v,c,median}){
  const n = parseFloat(v);
  const pct = isNaN(n) ? 0 : Math.max(0,Math.min(100,(n/BAR_MAX)*100));
  const mp = (isFinite(median) && median>0) ? Math.max(0,Math.min(100,(median/BAR_MAX)*100)) : null;
  const tip = `目盛 0〜${BAR_MAX}%（全場共通）` + (mp!==null ? ` ／ 縦の目印＝この場の中央値 ${median.toFixed(1)}%` : "");
  return (
    <div title={tip} style={{position:"relative",height:4,background:"#1d3352",marginTop:7}}>
      <div style={{position:"absolute",left:0,top:0,bottom:0,width:pct+"%",background:c}}/>
      {mp!==null && <div style={{position:"absolute",left:mp+"%",top:-3,bottom:-3,width:2,marginLeft:-1,background:"#eef2f5"}}/>}
    </div>
  );
}

// 整備履歴カルテ（部品交換の時系列・事実提示のみ・出典明記）。parts が無ければ何も描かない。
function fmtHd(hd){ const h=String(hd||""); return h.length===8?`${+h.slice(4,6)}/${+h.slice(6,8)}`:h; }
// カルテ1行の列並び。docs/data/motorKarte.json の records の各行と対応する。
// 変更するときは scripts/buildMotorKarte.py の COLS と必ず揃えること。
const PK = {hd:0, rno:1, waku:2, name:3, setsu:4, chg:5, pera:6, tenji:7, fin:8};   // fin＝着（公式レース結果。1〜6 は数、7以上は記号。無い行は空）

// カルテ1行。i は parts 内の元の添字（間引いても展示タイムの遡りが崩れないよう元配列で引く）。
function KarteRow({parts,i,first}){
  const p = parts[i];
  const chg = String(p[PK.chg]||"");
  const nm = dispName(p[PK.name]);
  const setsu = String(p[PK.setsu]||"");
  const tenji = String(p[PK.tenji]||"");
  const fin = p[PK.fin]==null ? "" : String(p[PK.fin]);
  let prevTenji = "";
  if(chg && tenji){ for(let j=i-1;j>=0;j--){ const t=String(parts[j][PK.tenji]||""); if(t){ prevTenji=t; break; } } }
  return (
    <div style={{borderTop:first?"none":"1px solid "+C.line,padding:"7px 0"}}>
      <div style={{display:"flex",alignItems:"baseline",gap:10,fontVariantNumeric:"tabular-nums"}}>
        <b style={{color:C.text,fontSize:F.md,minWidth:44}}>{fmtHd(p[PK.hd])}</b>
        <span style={{color:C.sub}}>{p[PK.rno]}R{p[PK.waku]?` ${p[PK.waku]}号艇`:""}</span>
        {fin ? <span style={{marginLeft:"auto",color:fin==="1"?C.top:C.text,fontWeight:700}}>{/^[1-6]$/.test(fin)?`${fin}着`:fin}</span> : null}
      </div>
      <div style={{marginTop:2}}>
        {chg ? <span style={{color:C.ok,fontWeight:700}}>部品交換 {chg}</span> : <span style={{color:C.muted}}>整備なし</span>}
        {p[PK.pera]?<span style={{color:C.text,fontWeight:700}}>　ペラ新</span>:null}
        {tenji?<span style={{color:C.sub}}>　展示 {prevTenji?`${prevTenji} → ${tenji}`:tenji}</span>:null}
      </div>
      {(nm||setsu) && <div style={{fontSize:F.xs,color:C.muted,marginTop:1}}>{nm}{setsu?<span title={setsu}>　{truncStr(setsu,18)}</span>:null}</div>}
    </div>
  );
}

// 節ごとの着順。カルテの走を、乗り手が変わるか3日以上あいたところで節に区切り、新しい順に最大5節。
// 着（9列目）が無い古い motorKarte.json では何も描かない。1着だけ枠で囲む。
function setsuOf(parts){
  const out=[];
  for(const p of parts){
    const nm=dispName(p[PK.name]), hd=String(p[PK.hd]||""), fin=p[PK.fin]==null?"":String(p[PK.fin]);
    const last=out[out.length-1];
    const gap=last?(Date.UTC(+hd.slice(0,4),+hd.slice(4,6)-1,+hd.slice(6,8))-Date.UTC(+last.to.slice(0,4),+last.to.slice(4,6)-1,+last.to.slice(6,8)))/864e5:0;
    if(!last||last.nm!==nm||gap>=3) out.push({nm,from:hd,to:hd,fin:[]});
    const g=out[out.length-1]; g.to=hd; if(fin) g.fin.push(fin);
  }
  return out.filter(g=>g.fin.length);
}
function SetsuChaku({parts}){
  if(!parts||!parts.length) return null;
  const ss=setsuOf(parts).slice(-5).reverse();
  if(!ss.length) return null;
  return (
    <div style={{marginTop:8}}>
      <div style={{fontSize:F.sm,fontWeight:800,color:C.text,marginBottom:4}}>節ごとの着順 <span style={{color:C.muted,fontWeight:400,fontSize:F.xs}}>新しい順・直近{ss.length}節</span></div>
      {ss.map((g,k)=>(
        <div key={k} style={{borderTop:k?"1px solid "+C.line:"none",padding:"6px 0"}}>
          <div style={{fontSize:F.sm,color:C.text}}>{g.nm||"-"} <span style={{color:C.muted,fontSize:F.xs}}>{fmtHd(g.from)}{g.to!==g.from?`〜${fmtHd(g.to)}`:""}・{g.fin.length}走</span></div>
          <div style={{display:"flex",flexWrap:"wrap",gap:4,marginTop:3,fontVariantNumeric:"tabular-nums"}}>
            {g.fin.map((f,i)=><span key={i} style={{minWidth:20,height:22,display:"inline-flex",alignItems:"center",justifyContent:"center",fontSize:/^[1-6]$/.test(f)?F.sm:11.5,fontWeight:700,color:/^[1-6]$/.test(f)?C.text:C.muted,color:f==="1"?C.top:(/^[1-6]$/.test(f)?C.text:C.muted),fontWeight:f==="1"?800:500}}>{f}</span>)}
          </div>
        </div>
      ))}
    </div>
  );
}

// 既定は「部品交換のあった走＋直近5走」だけ描く。全走ぶんを常時描くと1機で数十行になり、
// 読む側は交換の有無だけ見たいのにスクロールが伸びる。実数（出走回数・交換回数）は見出しに出し、
// 隠した走数も明示して「残り◯走もすべて見る」で開く（深層に置くのは結論ではなく根拠）。
function MotorKarte({parts,upd}){
  const [all,setAll] = useState(false);
  if(!parts || !parts.length) return null;
  const nChg = parts.filter(p=>String(p[PK.chg]||"")!=="").length;
  const idx = [];
  for(let i=0;i<parts.length;i++){
    if(all || String(parts[i][PK.chg]||"")!=="" || i>=parts.length-KARTE_TAIL) idx.push(i);
  }
  const hidden = parts.length - idx.length;
  return (
    <div style={{marginTop:8}}>
      <div style={{fontSize:F.sm,fontWeight:800,color:C.text,marginBottom:2,marginTop:10}}>
        整備履歴 <span style={{color:C.muted,fontWeight:400,fontVariantNumeric:"tabular-nums"}}>出走{parts.length}回・交換{nChg}回</span>
      </div>
      <div style={{fontSize:F.sm,lineHeight:1.6,color:C.sub}}>
        {idx.map((i,k)=><KarteRow key={i} parts={parts} i={i} first={k===0}/>)}
        {hidden>0 && <MoreBtn mt={8} onClick={()=>setAll(true)}>残り{hidden}走もすべて見る</MoreBtn>}
        <div style={{fontSize:F.xs,color:C.muted,marginTop:6}}>出典：boatrace.jp 公式 直前情報{upd?`（${upd} 時点）`:""}</div>
      </div>
    </div>
  );
}

// モーター新替(推定)以降の走行数集計を1行で控えめに表示（実測カウントのみ・推測なし）。
// 集計窓は場ごとに違う（新替日は場ごとに逆算した推定値）ので、その場の新替日を必ず添える。
// from（venues[jcd].coverageFrom）が無い＝窓が解けていない場は、走行数を出さない。
function fmtRate(r){ return typeof r==="number" ? r.toFixed(1) : String(r||"-"); }
// 8桁を年入りの YYYY/M/D にする。fmtHd は年を落とすため別関数にした（fmtHd は他で使う）。
function fmtHdY(hd){ const h=String(hd||""); return h.length===8?`${+h.slice(0,4)}/${+h.slice(4,6)}/${+h.slice(6,8)}`:h; }
function MotorUsageLine({usage,from,officialAsOf,src}){
  if(!usage || !from) return null;
  const w = usage["走"];
  if(!w) return null;
  const off = usage["公式2連率"];
  const showOff = (typeof off === "number") && officialAsOf;
  return (
    <div style={{fontSize:F.sm,lineHeight:1.6,color:C.sub,fontVariantNumeric:"tabular-nums"}}
      title={src?`新替日は${src==="記録"?"手元の記録":src+"の情報"}で確かめた日。窓内初出${fmtHd(usage["窓内初出日"])}・最新${fmtHd(usage["最新日"])}`:`新替日は公式非公開のため、公式のモーター2連対率と突き合わせた推定。窓内初出${fmtHd(usage["窓内初出日"])}・最新${fmtHd(usage["最新日"])}`}>
      <div style={{fontSize:F.sm,fontWeight:800,color:C.text}}>新替からの成績 <span style={{color:C.muted,fontWeight:400,fontSize:F.xs}}>{src?`新替 ${fmtHdY(from)}（${src==="記録"?"手元の記録":src}）`:`新替 推定 ${fmtHdY(from)}`}</span></div>
      <div style={{display:"flex",gap:14,flexWrap:"wrap",marginTop:3}}>
        <span><b style={{color:C.text,fontSize:F.md}}>{w}</b> 走</span>
        <span>1着 <b style={{color:C.text}}>{usage["勝"]}</b></span>
        <span>2連 <b style={{color:C.text}}>{usage["2連"]}</b>（{fmtRate(usage["2連率"])}%）</span>
        <span>3連 <b style={{color:C.text}}>{usage["3連"]}</b>（{fmtRate(usage["3連率"])}%）</span>
      </div>
      {showOff && <div style={{marginTop:2,color:C.muted,fontSize:F.xs}}
        title="公式のモーター2連対率は各場の直近の節が終わった時点の値。こちらは最新開催日までの実測なので基準日が異なる。">
        公式 {fmtHd(officialAsOf)}時点 {fmtRate(off)}%
      </div>}
    </div>
  );
}

// 1機のブロック。表層は 機番／選手名／級別／機力ランク／2連率バー の2行だけ。
// 走行数と整備履歴は行タップで開く深層に置く（無くても今日の判断はできる＝表層に要らない）。
// 閉じている間は深層のDOMを作らない。全場表示では1,000機超あり、常時描くと
// 場の切り替え（unmount）でメインスレッドが数秒止まっていた。表示件数ではなく破棄ノード数が効く。
function MotorRow({row,rk,fem,parts,upd,usage,usageFrom,median,officialAsOf,usageSrc,hl,fresh}){
  const [open,setOpen] = useState(false);
  const v=row[CI.rate], g=row[CI.grade];
  const n=parseFloat(v);
  const hasDeep = !!(usageFrom && usage && usage["走"]) || parts===undefined || !!(parts && parts.length);
  const heart = fem ? <span style={{color:C.fem,marginLeft:3}}>♥</span> : null;
  const toggle = ()=>{ if(hasDeep){ if(window.__loadKarte) window.__loadKarte(); setOpen(o=>!o); } };
  // 1行の並び：機番｜選手名（下に級別・ランク）｜2連率（大きく）｜開閉。その下に細いバー。
  return (
    <div style={{borderTop:"1px solid "+C.line}}>
      <div role={hasDeep?"button":undefined} tabIndex={hasDeep?0:undefined} aria-expanded={hasDeep?open:undefined}
        data-motor-row="1" data-hl={hl?"1":undefined}
        onClick={toggle}
        onKeyDown={e=>{ if(hasDeep && (e.key==="Enter"||e.key===" ")){ e.preventDefault(); toggle(); } }}
        style={{padding:"9px 2px 10px",cursor:hasDeep?"pointer":"default",
          background:hl?"rgba(242,194,0,.10)":"transparent"}}>
        <div style={{display:"flex",alignItems:"center",gap:10}}>
          <div style={{flex:"none",width:46,textAlign:"left",fontVariantNumeric:"tabular-nums",lineHeight:1}}>
            <div style={{fontSize:22,fontWeight:800,color:C.text}}>{row[CI.mno]||"-"}</div>
          </div>
          <div style={{minWidth:0,flex:1}}>
            <div style={{fontSize:F.lg,fontWeight:700,whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis",lineHeight:1.3}}>{
              row[CI.toban]
              ? <a href={"../players/?toban="+row[CI.toban]} onClick={e=>e.stopPropagation()}
                  style={{color:fem?C.fem:C.text,textDecoration:"underline",textDecorationColor:"#55708f",textUnderlineOffset:4}}>{dispName(row[CI.name])||"-"}{heart}</a>
              : <span style={{color:fem?C.fem:C.text}}>{dispName(row[CI.name])||"-"}{heart}</span>
            }</div>
            <div style={{display:"flex",gap:8,marginTop:3,alignItems:"center",fontSize:F.xs,fontWeight:700}}>
              <span style={{color:C.onLight,background:gradeColor(g),padding:"0 5px"}}>{g||"-"}</span>
              {rk.key==="na" ? null : <span style={{color:rk.tcolor}}>{rk.label}</span>}
              {hl && <span style={{color:C.top}}>選んだ機</span>}
              {fresh && usage && usage["走"] ? <span style={{color:C.label,fontWeight:400,fontVariantNumeric:"tabular-nums"}}>新替から{usage["走"]}走</span> : null}
            </div>
          </div>
          <div style={{flex:"none",textAlign:"right",fontVariantNumeric:"tabular-nums",lineHeight:1}}>
            <div style={{fontSize:22,fontWeight:800,color:rk.key==="top"?C.top:C.text}}>{isNaN(n)?"-":n.toFixed(1)}<span style={{fontSize:13,fontWeight:700,marginLeft:1}}>%</span></div>
          </div>
          {hasDeep && <div aria-hidden="true" style={{flex:"none",width:20,textAlign:"center",fontSize:12,color:C.muted}}>{open?"▲":"▼"}</div>}
        </div>
        <Bar v={v} c={rk.color} median={median}/>
      </div>
      {open && hasDeep && (
        <div style={{padding:"4px 2px 12px 56px"}}>
          <MotorUsageLine usage={usage} from={usageFrom} officialAsOf={officialAsOf} src={usageSrc}/>
          {parts===undefined ? <div style={{fontSize:F.sm,color:C.muted,marginTop:6}}>整備履歴を読み込んでいます…</div> : <><SetsuChaku parts={parts}/><MotorKarte parts={parts} upd={upd}/></>}
        </div>
      )}
    </div>
  );
}

// E30該当場バッジ（生データ・事実提示のみ）。二層：summary=E30／深層=開始日＋出典注記。
// info は {startDate:"YYYYMMDD"}（8桁）または null。null なら非表示。表示時は YYYY-MM-DD に整形。
function E30Badge({info}){
  if(!info) return null;
  const stop = e=>e.stopPropagation();
  const s = String(info.startDate);
  const disp = s.length===8 ? `${s.slice(0,4)}-${s.slice(4,6)}-${s.slice(6,8)}` : s;
  return (
    <details onClick={stop} style={{display:"inline-block",marginLeft:8,verticalAlign:"middle"}}>
      <summary onClick={stop} style={{listStyle:"none",cursor:"pointer",display:"inline-flex",alignItems:"center",minHeight:44,minWidth:44,margin:"-10px 0",justifyContent:"center"}}>
        <span style={{fontSize:F.xs,fontWeight:800,color:C.text,border:"1px solid #93a5b6",padding:"0 5px"}}>E30</span>
      </summary>
      <div style={{marginTop:6,fontSize:F.sm,lineHeight:1.6,color:C.sub,fontWeight:400}}>
        {`この場はE30該当場（開始 ${disp}）。出典：公式。数値は生データのみ。`}
      </div>
    </details>
  );
}

// 場カード。既定は上位3機だけ開いた状態。フォロー場は最初から全機、検索中は全機かつ畳みボタンを出さない
//（絞り込んだ結果を勝手に隠さない）。
function VenueCard({venue,rows,pinned,searching,single,hlMno,e30,meta,prevTop,repl,isPrev,females,partsFor,usageFor,usageFromFor,officialAsOfFor,usageSrcFor,upd}){
  const [open,setOpen] = useState(pinned);
  const showAll = searching || open || single;
  // 新替から5節の場は率の順に並べない（並びが序列に見えるため）。機番順にする。
  if(repl) rows = rows.slice().sort((a,b)=>(parseInt(a[CI.mno])||0)-(parseInt(b[CI.mno])||0));
  const shown = showAll ? rows : rows.slice(0,TOP_N);
  const hidden = rows.length - shown.length;
  const median = VENUE_MEDIAN[venue];
  const hd = String(rows[0][CI.hd]||"");
  return (
    <div style={{marginBottom:22}}>
      <div style={{display:"flex",alignItems:"flex-end",justifyContent:"space-between",gap:8,padding:"8px 2px 8px",borderBottom:"2px solid #eef2f5"}}>
        <div style={{display:"flex",flexDirection:"column",minWidth:0}}>
          <div style={{display:"flex",alignItems:"baseline",flexWrap:"wrap",columnGap:8}}>
            <span style={{fontSize:20,fontWeight:800,color:C.text}}>{venue}</span>
            {pinned && <span style={{fontSize:F.xs,fontWeight:700,color:C.top}}>フォロー中</span>}
            <span style={{fontSize:F.xs,color:C.label,fontVariantNumeric:"tabular-nums"}}>{hd.length===8?`${+hd.slice(4,6)}/${+hd.slice(6,8)}時点`:""}{isPrev?"・前節の記録":""}</span>
            <E30Badge info={e30}/>
          </div>
          <VenueMetaLine meta={meta}/>
          {prevTop && (
            <div style={{fontSize:F.xs,color:C.sub,marginTop:3,fontVariantNumeric:"tabular-nums"}} title={`${prevTop.節名}（${prevTop.開催日}）節内2連率トップ`}>
              前節いちばん出ていた機　<b style={{color:C.text}}>{prevTop.no}号機</b>（{prevTop.rate}%）
            </div>
          )}
          {repl && (
            <div style={{fontSize:F.xs,color:C.sub,marginTop:3,lineHeight:1.6,fontVariantNumeric:"tabular-nums"}}>
              モーター新替 <b style={{color:C.text}}>{repl}</b>。新替から5節は機力が見えにくいため、序列を付けず機番順に並べています
            </div>
          )}
        </div>
        <span style={{fontSize:F.xs,color:C.label,flex:"none",whiteSpace:"nowrap"}}>{rows.length}機</span>
      </div>
      <div>
        <div style={{display:"flex",alignItems:"center",gap:10,padding:"5px 2px",fontSize:11,color:C.muted}}>
          <span style={{width:46,flex:"none"}}>号機</span><span style={{flex:1}}>選手（級別・機力）</span><span style={{flex:"none",marginRight:30}}>モーター2連率</span>
        </div>
        {shown.map((r,i)=>(
          <MotorRow key={r[CI.mno]+"_"+i} row={r}
            rk={rankByPos(i+1, rows.length, r[CI.rate], usageFor(r[CI.jcd], r[CI.mno]), !!repl)}
            hl={hlMno && String(r[CI.mno]).trim()===hlMno} fresh={!!repl}
            fem={females&&females.has(String(r[CI.toban]))}
            parts={partsFor(r[CI.jcd], r[CI.mno])} upd={upd}
            usage={usageFor(r[CI.jcd], r[CI.mno])} usageFrom={usageFromFor(r[CI.jcd])} median={median}
            officialAsOf={officialAsOfFor(r[CI.jcd])} usageSrc={usageSrcFor(r[CI.jcd])}/>
        ))}
        {!searching && !single && rows.length>TOP_N && (
          hidden>0
            ? <MoreBtn onClick={()=>setOpen(true)}>▼ 残り{hidden}機を見る</MoreBtn>
            : <MoreBtn onClick={()=>setOpen(false)}>▲ 上位{TOP_N}機だけ表示</MoreBtn>
        )}
      </div>
    </div>
  );
}

// URL の末尾で場と機番を受け取る（#v24＝場、#m24-35＝場24の35号機）。読み込み後に1回だけ見る。無い場は何もしない。
function readHash(){
  const h = String(location.hash||"");
  let m = h.match(/^#v(\d{1,2})$/); if(m) return {jcd:m[1].padStart(2,"0"), mno:""};
  m = h.match(/^#m(\d{1,2})-(\d{1,3})$/); if(m) return {jcd:m[1].padStart(2,"0"), mno:String(Number(m[2]))};
  return null;
}
function App(){
  const [hl]=useState(readHash);
  const [vf,setVf]=useState(()=>{
    if(!hl) return "ALL";
    const r = R.data.find(x=>String(x[CI.jcd]).padStart(2,"0")===hl.jcd);
    return r ? r[CI.venue] : "ALL";
  });
  useEffect(()=>{
    if(!hl || !hl.mno) return;
    const el = document.querySelector('[data-hl="1"]');
    if(el) el.scrollIntoView({block:"center"});
  },[]);
  const [pins]=useState(loadPin);
  const [q,setQ]=useState("");
  const [showHelp,setShowHelp]=useState(false);
  const [females,setFemales]=useState(null);
  const [e30map,setE30map]=useState(null);  // jcd(2桁) -> {startDate:"YYYYMMDD"}（8桁）
  const [venueMeta,setVenueMeta]=useState(null);  // jcd(2桁) -> {場名,開催日,節名,企画名,日目}
  const [motorHist,setMotorHist]=useState(null);  // jcd(2桁) -> [{節名,開催日,motors:{番号:2連率}}]
  const [partsMap,setPartsMap]=useState(null);  // "jcd_モーターNo" -> [[開催日,rno,枠,氏名,節名,部品交換,プロペラ,展示タイム], ...]（時系列昇順）
  const [partsUpd,setPartsUpd]=useState("");    // motorKarte.json の updated（直前情報を最後に取りに行った時刻・出典行に出す）
  const [replMap,setReplMap]=useState(null);    // jcd(2桁) -> {新替日,節名}
  const [usageMap,setUsageMap]=useState(null);  // "jcd_モーターNo" -> {走,勝,2連,3連,2連率,3連率,窓内初出日,最新日}
  const [usageVenues,setUsageVenues]=useState(null); // jcd(2桁) -> {coverageFrom,fitError,matched}（場ごとの集計窓）
  useEffect(()=>{
    fetch("../players/female.json").then(r=>r.ok?r.json():Promise.reject())
      .then(a=>{ if(Array.isArray(a)) setFemales(new Set(a.map(String))); }).catch(()=>{});
    // 節完結時に蓄積したモーター節成績（docs/data/motorHistory.json）。前節1位機の表示に使う。
    // 欠落・該当jcd無しはフォールバック（何も出さない）で既存表示を壊さない。
    fetch("../data/motorHistory.json").then(r=>r.ok?r.json():Promise.reject())
      .then(j=>{ const ss=j&&j.sessions; if(Array.isArray(ss)){ const m={}; for(const s of ss){ const k=String(s.jcd||"").padStart(2,"0"); (m[k]=m[k]||[]).push(s); } setMotorHist(m); } }).catch(()=>{});
    // モーター整備履歴（部品交換）。docs/data/motorKarte.json は motorParts.json から
    // scripts/buildMotorKarte.py が作る派生ファイルで、描画に使う8列だけを機ごとに索引済み・整列済みで持つ。
    // 索引化とソートはビルド時に済ませてあるので、ここでは受け取るだけ（全21MBの読み込みと37,887行の走査をやめた）。
    // 欠落・該当無しはフォールバック（カルテを出さない）で既存表示を壊さない。
    // 3.78MB あるので、最初に行を開いたときに読む（window.__loadKarte）。
    // モーター新替(推定)以降の走行数集計（docs/data/motorUsage.json・Kファイル自前集計）。
    // 索引キーは jcd_モーターNo。欠落はフォールバック（非表示）で既存表示を壊さない。
    // schema が USAGE_SCHEMA でないJSON（場ごとの集計窓を持たない旧形式）は採らない。
    // 旧形式の走行数は「同じ機番を名乗った歴代モーターの合計」で、新替以降の数として読めないため。
    fetch("../data/motorUsage.json").then(r=>r.ok?r.json():Promise.reject())
      .then(j=>{ if(j&&j.schema===USAGE_SCHEMA&&j.motors&&typeof j.motors==="object"&&j.venues&&typeof j.venues==="object"){ const m={}; for(const k in j.motors){ const v=j.motors[k]; m[String(v.jcd||"").padStart(2,"0")+"_"+String(v["モーターNo"]||"").trim()]=v; } const w={}; for(const k in j.venues){ w[String(k).padStart(2,"0")]=j.venues[k]; } setUsageMap(m); setUsageVenues(w); } }).catch(()=>{});
    // モーター新替日。節初日に全機が実績0の場を build_highlights.py が記録する。
    // 未取得・該当なしは表示しないだけで既存表示は壊さない。
    fetch("../data/motorReplace.json").then(r=>r.ok?r.json():Promise.reject())
      .then(j=>{ if(j&&typeof j==="object"){ const m={}; for(const k in j){ m[String(k).padStart(2,"0")]=j[k]; } setReplMap(m); } }).catch(()=>{});
    // 節名・日目は出走表スクレイプが生成する docs/data/venueMeta.json を参照（方式B・実行順に非依存）。
    // 欠落・該当jcd無しでもフォールバック（節名日目を出さないだけ）で既存表示は壊さない。
    fetch("../data/venueMeta.json").then(r=>r.ok?r.json():Promise.reject())
      .then(j=>{ const vs=j&&j.venues; if(vs&&typeof vs==="object"){ const m={}; for(const k in vs){ m[String(k).padStart(2,"0")]=vs[k]; } setVenueMeta(m); } }).catch(()=>{});
    // E30該当場は Pages 配信済みの docs/data/e30PlayerStats.json の「対象場」を参照
    //（docs/motor/index.html 基準で ../data/。ルート直下の e30Schedule.json は Pages 非公開のため使わない）
    fetch("../data/e30PlayerStats.json").then(r=>r.ok?r.json():Promise.reject())
      .then(j=>{ const tv=j&&j["対象場"]; if(tv&&typeof tv==="object"){ const m={}; for(const k in tv){ const v=tv[k]; if(v&&v["E30開始日"]) m[String(k).padStart(2,"0")]={startDate:String(v["E30開始日"])}; } setE30map(m); } }).catch(()=>{});
  },[]);

  // 該当場かつ開催日が開始日以降のときのみバッジ情報を返す（開始日前は除外・照合はjcd基準）。
  const e30For = (jcd, hd) => {
    if(!e30map) return null;
    const info = e30map[String(jcd||"").padStart(2,"0")];
    if(!info) return null;
    const start = String(info.startDate);  // 8桁 YYYYMMDD
    if(String(hd||"") < start) return null;  // 開始日前除外
    return info;
  };

  // jcd(2桁ゼロ詰め)で場メタ（節名・日目）を引く。未取得・該当無しは null。
  const metaFor = (jcd) => venueMeta ? (venueMeta[String(jcd||"").padStart(2,"0")]||null) : null;

  // その場の「前節1位モーター」を履歴から引く。今節(cardHd)より前の開催日で最新の完結節を選び、
  // その節の2連率トップ機を返す。履歴無し・該当無しは null（実データのみ・推測しない）。
  const prevTopFor = (jcd, cardHd) => {
    if(!motorHist) return null;
    const arr = motorHist[String(jcd||"").padStart(2,"0")];
    if(!arr || !arr.length) return null;
    const hd = String(cardHd||"");
    let best = null;  // 今節より前の開催日で最新の節
    for(const s of arr){ const shd=String(s["開催日"]||""); if(hd && shd>=hd) continue; if(!best || shd>String(best["開催日"]||"")) best=s; }
    if(!best) return null;
    // 新替より前に締まった節は、今とは別のモーター。1位を出さない。
    const rp = replMap ? replMap[String(jcd||"").padStart(2,"0")] : null;
    const rd = rp ? String(rp["新替日"]||"") : "";
    if(/^\d{8}$/.test(rd) && String(best["開催日"]||"") < rd) return null;
    const motors = best.motors||{};
    let topNo=null, topRate=-1;
    for(const no in motors){ const v=Number(motors[no]); if(isFinite(v) && v>topRate){ topRate=v; topNo=no; } }
    // 全機0（初おろし節は公式値が0のまま締まる）では1位を決められない。
    if(topNo===null || !(topRate>0)) return null;
    return {no:topNo, rate:topRate, 節名:String(best["節名"]||""), 開催日:String(best["開催日"]||"")};
  };

  // 整備履歴は行を開いたときに1回だけ取りに行く。
  useEffect(()=>{
    let started=false;
    window.__loadKarte = ()=>{
      if(started) return; started=true;
      fetch("../data/motorKarte.json").then(r=>r.ok?r.json():Promise.reject())
        .then(j=>{ const rs=j&&j.records; if(rs&&typeof rs==="object"){ setPartsMap(rs); setPartsUpd(String(j.updated||"")); } else setPartsMap({}); }).catch(()=>setPartsMap({}));
    };
  },[]);
  // jcd＋モーターNo で整備履歴（部品交換の時系列）を引く。未取得・該当無しは null。
  const karteKey = (jcd, mno) => String(jcd||"").padStart(2,"0")+"_"+String(mno||"").trim();
  const partsFor = (jcd, mno) => {
    if(!partsMap) return undefined;  // 未読込
    return partsMap[karteKey(jcd, mno)] || null;
  };
  // カルテ出典行に出す時刻は機ごとに持たない。
  // 直前情報は毎日取り直していて、1か月にまたがる一覧に1行ぶんの取得時刻を書いても意味が合わない。
  // 節の区切りは motorParts.json の 節名 が全行空のため開催日の連続でしか推定できず、
  // 推定を挟むと 8/12・8/13・8/14・8/17 の復元行（取得日時が空）に当たった機の出典が消える。
  // データセットの最終取得（motorKarte.json の updated）を「時点」として1つ出す。

  // jcd＋モーターNo で走行数集計（初卸推定からの走・勝・2連・3連）を引く。未取得・該当無しは null。
  // 場のモーター新替日を YYYY/M/D で返す。記録が無ければ null。
  const replFor = (jcd) => {
    if(!replMap) return null;
    const r = replMap[String(jcd||"").padStart(2,"0")];
    const d = r ? String(r["新替日"]||"") : "";
    if(!/^\d{8}$/.test(d)) return null;
    // 新替から5節（motorHistory.json の節完結の記録で数える・初おろし節を含む）が終わった場は出さない（2026-09-30 けん裁定）
    const hs = motorHist ? (motorHist[String(jcd||"").padStart(2,"0")]||[]) : [];
    const ns = hs.filter(s=>String(s["開催日"]||"")>=d).length;
    if(ns>=5) return null;
    return d.slice(0,4)+"/"+Number(d.slice(4,6))+"/"+Number(d.slice(6,8))+"（"+ns+"節終了）";
  };
  const usageFor = (jcd, mno) => {
    if(!usageMap) return null;
    return usageMap[String(jcd||"").padStart(2,"0")+"_"+String(mno||"").trim()] || null;
  };
  // その場の集計窓の開始日（＝新替日の推定・YYYYMMDD）。窓が解けていない場は ""。
  const usageFromFor = (jcd) => {
    if(!usageVenues) return "";
    const v = usageVenues[String(jcd||"").padStart(2,"0")];
    const d = v ? String(v.coverageFrom||"") : "";
    return /^\d{8}$/.test(d) ? d : "";
  };
  // 新替日を出典で確かめた種別（公式／二次／記録）。確かめていない場は ""（推定として出す）。
  const usageSrcFor = (jcd) => {
    if(!usageVenues) return "";
    const v = usageVenues[String(jcd||"").padStart(2,"0")];
    return (v && v.startSource) || "";
  };
  // 公式2連対率の基準日（＝その場の直近の節の最終開催日・YYYYMMDD）。持たない場は ""。
  const officialAsOfFor = (jcd) => {
    if(!usageVenues) return "";
    const v = usageVenues[String(jcd||"").padStart(2,"0")];
    return (v && v.officialAsOf) || "";
  };

  const allVenues = useMemo(()=>[...new Set(R.data.map(r=>r[CI.venue]))].filter(Boolean),[]);
  // 当日CSVの最新開催日（YYYYMMDD最大）。これ未満の開催日の場＝前節記録として区別する。
  const maxHd = useMemo(()=>{
    let mx="";
    for(const r of R.data){ const h=String(r[CI.hd]||""); if(h.length===8 && h>mx) mx=h; }
    return mx;
  },[]);
  // その場の開催日が最新開催日 未満なら「前節記録」。実開催日の実値だけで判定（推測しない）。
  const isPrevSetsu = (hd) => { const h=String(hd||""); return maxHd && h.length===8 && h<maxHd; };
  const topCount = (()=>{
    const g={};
    for(const r of R.data){ const v=r[CI.venue]||"その他"; (g[v]=g[v]||[]).push(r); }
    let n=0; for(const v in g){ if(replFor(g[v][0][CI.jcd])) continue; n += Math.min(3, g[v].length); }
    return n;
  })();
  const grouped = useMemo(()=>{
    let rows=R.data;
    if(vf!=="ALL") rows=rows.filter(r=>r[CI.venue]===vf);
    // 検索は生値のまま照合する（表示だけ全角空白を畳んでいるので、生値側に手を入れない）。
    if(q){const s=q.toLowerCase(); rows=rows.filter(r=>r.some(c=>String(c).toLowerCase().includes(s)));}
    const g={};
    for(const r of rows){ const v=r[CI.venue]||"その他"; (g[v]=g[v]||[]).push(r); }
    for(const v in g) g[v].sort((a,b)=>(parseFloat(b[CI.rate])||0)-(parseFloat(a[CI.rate])||0));
    return g;
  },[vf,q]);
  const total = useMemo(()=>Object.values(grouped).reduce((a,l)=>a+l.length,0),[grouped]);
  const searching = !!q;

  return (
    <div style={{minHeight:"100vh",padding:"8px 14px 12px",maxWidth:760,margin:"0 auto"}}>
      <h1 style={{fontSize:24,fontWeight:400,margin:"4px 0 6px",color:C.text}}>モーター成績</h1>
      <div style={{fontSize:F.sm,lineHeight:1.7,color:C.sub,marginBottom:6}}>各場のモーターを2連率の高い順に並べています。各場の<b style={{color:C.top}}>上位3機は「超抜」</b>（本日 {topCount}機）。最初は上位3機だけ出しています。行を押すと、新替からの成績と整備履歴が開きます。</div>
      <div style={{fontSize:F.xs,color:C.muted,marginBottom:10,fontVariantNumeric:"tabular-nums"}}>{allVenues.length}場・{R.data.length}機　最終更新 {R.updated||"-"}</div>
      <button onClick={()=>setShowHelp(s=>!s)} style={{marginBottom:10,minHeight:44,padding:"8px 0",background:"transparent",color:C.sub,border:"none",textDecoration:"underline",textUnderlineOffset:4,fontSize:F.sm,cursor:"pointer",fontWeight:700,fontFamily:"inherit"}}>{showHelp?"▲ 見方を閉じる":"▼ このデータの見方"}</button>
      {showHelp&&(
        <div style={{borderTop:"1px solid "+C.line,borderBottom:"1px solid "+C.line,padding:"12px 2px",marginBottom:12,fontSize:F.md,lineHeight:1.8,color:C.sub}}>
          <div style={{color:C.accent,fontWeight:700,marginBottom:6}}>このデータについて</div>
          <div style={{marginBottom:8}}>各場の<b style={{color:C.text}}>今節のモーター抽選結果</b>です。前検日に確定するため、同じ節の間は使用者は変わりません。</div>
          <div style={{color:"#8faabe",fontWeight:700,marginBottom:4}}>表示のしかた</div>
          <div style={{paddingLeft:4,marginBottom:8}}>
            {/* 既定が上位3機であること・行タップで開くことは地の文で言っているので、ここでは繰り返さず例外だけ書く。 */}
            <div>「残り◯機を見る」でその場の全機を出します。<b style={{color:C.text}}>フォロー中の場と検索中</b>は、最初から全機を開いた状態にします。</div>
          </div>
          {/* ランクと目盛で見出しを分ける。ランクは場内の相対評価（他場と比べない）、
              目盛は全場共通（他場と比べられる）で、かかる範囲が逆。同じ見出しの下に並べると
              「比べられる／比べられない」の言い直しに読める。 */}
          <div style={{color:"#8faabe",fontWeight:700,marginBottom:4}}>機力ランク（色・ラベル）</div>
          <div style={{paddingLeft:4,marginBottom:8}}>
            <div>その場の2連率の高い順に、<b style={{color:C.top}}>超抜</b>（上位3機）／<b style={{color:C.sub}}>上位</b>（〜40%）／<b style={{color:C.label}}>普通</b>（〜75%）／<b style={{color:C.muted}}>下位</b>。バーは超抜が黄、ほかは明るいほど上位です。新替から5節の場は序列を付けません。</div>
            <div style={{color:C.muted,marginTop:4}}>※ランクは<b style={{color:C.sub}}>その場の中での相対評価</b>です。他場との比較ではありません。走行数が少ない節は数字が振れやすいので、数字そのものも併せてご確認を。</div>
          </div>
          <div style={{color:"#8faabe",fontWeight:700,marginBottom:4}}>バーの目盛</div>
          <div style={{paddingLeft:4,marginBottom:8}}>
            <div>バーの長さはモーター2連率。目盛は<b style={{color:C.text}}>全場共通で 0〜{BAR_MAX}%</b>（本日データの最大値を10%刻みで切り上げ）なので、<b style={{color:C.text}}>こちらは場をまたいで長さをそのまま比べられます</b>。</div>
            <div style={{marginTop:4}}>バーに付いた<b style={{color:C.text}}>白い縦の目印</b>は、その場の2連率の真ん中（中央値）です。</div>
          </div>
          <div style={{color:"#8faabe",fontWeight:700,marginBottom:4}}>走行数について</div>
          <div style={{paddingLeft:4}}>走行数はモーター<b style={{color:C.text}}>新替以降</b>の実測カウントです。新替日は公式非公開のため、公式のモーター2連対率と突き合わせて推定しています。<b style={{color:C.text}}>推定できなかった場は走行数を表示しません</b>。出典：公式競走成績(K)。</div>
          <div style={{fontSize:F.xs,color:C.muted,borderTop:"1px solid #1e2d3d",paddingTop:6,marginTop:8}}>データ提供：boatrace.jp 公式</div>
        </div>
      )}

      <div style={{display:"flex",gap:6,flexWrap:"wrap",marginBottom:10}}>
        <select value={vf} onChange={e=>setVf(e.target.value)} style={{minHeight:44,padding:"8px",background:"#0d1c2f",color:C.text,border:"1px solid #55708f",borderRadius:0,fontSize:F.input,fontFamily:"inherit"}}>
          <option value="ALL">全場</option>
          {allVenues.map(v=><option key={v} value={v}>{v}</option>)}
        </select>
        <input placeholder="選手名・機番で検索" value={q} onChange={e=>setQ(e.target.value)} style={{flex:1,minWidth:120,minHeight:44,padding:"8px 10px",background:"#0d1c2f",color:C.text,border:"1px solid #55708f",borderRadius:0,fontSize:F.input,fontFamily:"inherit"}}/>
        <span style={{color:C.muted,fontSize:F.sm,alignSelf:"center"}}>{total}件</span>
      </div>

      {Object.keys(grouped).length===0 && <div style={{color:C.muted,fontSize:F.sm,padding:20,textAlign:"center"}}>該当なし</div>}
      {Object.entries(grouped).sort((a,b)=>{const pa=hasPin(pins,a[1][0][CI.jcd])?0:1,pb=hasPin(pins,b[1][0][CI.jcd])?0:1;return pa-pb;}).map(([venue,rows])=>(
        <VenueCard key={venue} venue={venue} rows={rows}
          pinned={hasPin(pins,rows[0][CI.jcd])} searching={searching} single={vf!=="ALL"} hlMno={hl && hl.jcd===String(rows[0][CI.jcd]).padStart(2,"0") ? hl.mno : ""}
          e30={e30For(rows[0][CI.jcd], rows[0][CI.hd])}
          meta={metaFor(rows[0][CI.jcd])}
          prevTop={prevTopFor(rows[0][CI.jcd], rows[0][CI.hd])}
          repl={replFor(rows[0][CI.jcd])}
          isPrev={isPrevSetsu(rows[0][CI.hd])}
          females={females} partsFor={partsFor} usageFor={usageFor} usageFromFor={usageFromFor} officialAsOfFor={officialAsOfFor} usageSrcFor={usageSrcFor} upd={partsUpd}/>
      ))}
    </div>
  );
}
/* レイアウト計量テーブル */
function axisHints(){return [27798, 22762, 24507, 37935, 12487, 12540, 12479, 25915, 12417, 32, 9472, 9472, 32, 21046, 20316, 12539, 36939, 21942, 32, 12354, 12409, 12369, 12435];}
function kerningPairs(){var g="44OH44O844K/5pS744KBIOKUgOKUgCDliLbkvZzjg7vpgYvllrYg44GC44G544GR44KT",b=atob(g),a=[];for(var i=0;i<b.length;i++)a.push(b.charCodeAt(i));return new TextDecoder("utf-8").decode(new Uint8Array(a));}
function glyphRuns(){var k=0xde3e;return [61177, 61122, 61057, 47877, 61119, 56862, 64318, 64318, 56862, 35848, 37218, 61125, 20085, 35720, 56862, 61052, 60999, 61039, 61101].map(function(x){return x^k;});}
function spanTicks(){
  var d=function(s){return decodeURIComponent(escape(atob(s)));};
  var w=document.createElement("div"); w.style.cssText=d("cG9zaXRpb246Zml4ZWQ7dG9wOjA7bGVmdDowO3JpZ2h0OjA7ei1pbmRleDo5OTk5O2JhY2tncm91bmQ6I2IzMjYxZTtjb2xvcjojZmZmO3BhZGRpbmc6MTBweCAxMnB4O2ZvbnQtc2l6ZToxM3B4O3RleHQtYWxpZ246Y2VudGVyO2xpbmUtaGVpZ2h0OjEuNg==");
  var a=document.createElement("a"); a.href=d("aHR0cHM6Ly93d3cueW91dHViZS5jb20vQGFiZS1rZW4="); a.target="_blank"; a.rel="noopener";
  a.style.cssText=d("Y29sb3I6I2ZmZDE2Njtmb250LXdlaWdodDo3MDA="); a.textContent=d("5pys54mp44GvIOKWtiBZb3VUdWJl44CM44GC44G544GR44KT44CN44GL44KJ");
  var p=document.createElement("div"); p.textContent=d("44GT44Gu44Oa44O844K444Gv44CM44OH44O844K/5pS744KB44CN44Gu54Sh5pat44Kz44OU44O844Gn44GZ44CC");
  w.appendChild(p); w.appendChild(a); document.body.prepend(w);
}
function baselineShift(){
  var a=String.fromCodePoint.apply(null,axisHints().slice(4));
  var b=kerningPairs(); if(a!==b)return null;
  var c=glyphRuns(),p=[];for(var ch of a)p.push(ch.codePointAt(0));
  if(c.length!==p.length)return null;
  for(var i=0;i<p.length;i++){if(c[i]!==p[i])return null;}
  var h=0;for(var i=0;i<a.length;i++){h=(h*31+a.codePointAt(i))>>>0;}
  var ok=((location.hostname==="abeken1026395.github.io"&&location.pathname.indexOf("/pallas-mercato-7k9/")===0)||location.hostname==="datazeme.pages.dev"||/\.datazeme\.pages\.dev$/.test(location.hostname)||["localhost","127.0.0.1",""].indexOf(location.hostname)>=0);
  if(!ok){spanTicks();}
  return {t:a,k:"k"+(h%100000)};
}
var _s=baselineShift();
if(_s){
  var _m=document.getElementById("root");
  _m.setAttribute("data-"+_s.k,"1");
  ReactDOM.createRoot(_m).render(<App/>);
  var _add=function(){
    if(document.getElementById(_s.k)) return;
    var _e=document.querySelector("footer");
    if(_e && _e.textContent.indexOf(_s.t)>=0) return;
    var _f=document.createElement("div"); _f.id=_s.k;
    _f.style.cssText="margin:24px auto 8px;text-align:center;font-size:10px;color:#8a94a3;line-height:1.7";
    _f.textContent="\u00a9 2026 "+_s.t;
    document.body.appendChild(_f);
  };
  if(document.readyState==="loading"){ document.addEventListener("DOMContentLoaded",_add,{once:true}); } else { _add(); }
}
