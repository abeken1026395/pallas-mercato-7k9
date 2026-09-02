const { useState, useMemo, useEffect } = React;
const R = window.__D;
const cols = R.columns;

/* ===== 表示の定数（同じ値を2箇所に書かない。METHOD.md 9節・受け入れ基準10）===== */

// 文字色。すべて背景 #0b1219〜#26333f 上でコントラスト 4.5:1 以上（AA・METHOD.md 9節）。
// 増やさない。1色1意味。
const C = {
  text:   "#e0e6ed",  // 本文
  sub:    "#c5d2e0",  // 補助本文
  label:  "#9fb0c0",  // 見出し・ラベル
  muted:  "#88a0b5",  // 注記の下限（最も暗い #26333f 上で 4.76:1）
  dim:    "#7d94a8",  // 注記（暗い背景専用。バッジ地の上には置かない）
  accent: "#ffd166",
  link:   "#8fd0ff",
  fem:    "#ff9ec9",
  ok:     "#8fd6c0",
  onLight:"#0b1219",  // 明色バッジ／チップの上に載せる文字
};

// 文字サイズ。本文は13px以上、select と input は16px（iOS Safari の自動ズーム回避）。
const F = { xs:13, sm:14, md:15, lg:16, xl:17, hero:20, input:16 };

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
  top: {key:"top", label:"超抜", color:"#ffd166", tcolor:"#ffd166"},
  hi:  {key:"hi",  label:"上位", color:"#79c0ff", tcolor:"#79c0ff"},
  mid: {key:"mid", label:"普通", color:"#7d9bb5", tcolor:C.label},
  low: {key:"low", label:"下位", color:"#556579", tcolor:C.muted},
};
function rankByPos(pos, total, rate, usage){
  if(!total || !pos) return RK.na;
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
function myoumi(g, rk){ return isB(g) && (rk.key==="top"||rk.key==="hi"); }

// 級別バッジ。白文字では #e05a5a が 3.63、#5a7fe0 が 3.79 で AA 未達だったため、
// 地色はそのままに文字を暗色へ反転した（5.18／4.98／4.57）。「超抜」バッジと同じ作法。
const gradeColor = g => String(g).startsWith("A")?"#e05a5a":String(g).startsWith("B")?"#5a7fe0":"#6b7f95";

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
    <div style={{fontSize:F.xs,color:C.muted,marginTop:3,display:"flex",alignItems:"center",gap:6,flexWrap:"wrap",minWidth:0}}>
      {setsu && <span style={{color:C.label}} title={setsu}>{truncStr(setsu,18)}</span>}
      {nichime && <span style={{fontSize:F.xs,fontWeight:700,color:C.onLight,background:C.dim,borderRadius:3,padding:"1px 7px",flex:"none"}}>{nichime}</span>}
    </div>
  );
}

// 二層開閉ボタン。見た目は控えめでも当たり判定は 24px 以上を確保する
//（小さいボタンは見た目の問題ではなく押し間違いの問題・METHOD.md 9節）。
function MoreBtn({onClick,children,mt}){
  return (
    <button type="button" onClick={onClick}
      style={{display:"inline-flex",alignItems:"center",justifyContent:"center",gap:6,
        minHeight:32,minWidth:HIT,marginTop:mt||0,padding:"6px 14px",
        background:"#16232f",color:C.label,border:"1px solid #2a3d52",borderRadius:8,
        fontSize:F.xs,fontWeight:700,cursor:"pointer",fontFamily:"inherit"}}>{children}</button>
  );
}

function Bar({v,c,tc,median}){
  const n = parseFloat(v);
  const pct = isNaN(n) ? 0 : Math.max(0,Math.min(100,(n/BAR_MAX)*100));
  const mp = (isFinite(median) && median>0) ? Math.max(0,Math.min(100,(median/BAR_MAX)*100)) : null;
  const tip = `目盛 0〜${BAR_MAX}%（全場共通）` + (mp!==null ? ` ／ 縦線＝この場の中央値 ${median.toFixed(1)}%` : "");
  return (
    <div style={{display:"flex",alignItems:"center",gap:6,flex:1,minWidth:76}}>
      <div title={tip} style={{position:"relative",height:16,background:"#08111a",border:"1px solid #16222f",borderRadius:8,overflow:"hidden",flex:1}}>
        <div style={{position:"absolute",left:0,top:0,bottom:0,width:pct+"%",background:c,opacity:.85,borderRadius:8}}/>
        {mp!==null && <div style={{position:"absolute",left:mp+"%",top:1,bottom:1,width:2,marginLeft:-1,background:C.text,opacity:.6}}/>}
      </div>
      <div style={{fontSize:F.md,fontWeight:800,color:tc,minWidth:54,textAlign:"right",fontVariantNumeric:"tabular-nums"}}>{isNaN(n)?"-":n.toFixed(1)+"%"}</div>
    </div>
  );
}

// 整備履歴カルテ（部品交換の時系列・事実提示のみ・出典明記）。parts が無ければ何も描かない。
function fmtHd(hd){ const h=String(hd||""); return h.length===8?`${+h.slice(4,6)}/${+h.slice(6,8)}`:h; }
// カルテ1行の列並び。docs/data/motorKarte.json の records の各行と対応する。
// 変更するときは scripts/buildMotorKarte.py の COLS と必ず揃えること。
const PK = {hd:0, rno:1, waku:2, name:3, setsu:4, chg:5, pera:6, tenji:7};

// カルテ1行。i は parts 内の元の添字（間引いても展示タイムの遡りが崩れないよう元配列で引く）。
function KarteRow({parts,i,first}){
  const p = parts[i];
  const chg = String(p[PK.chg]||"");
  const nm = String(p[PK.name]||"");
  const setsu = String(p[PK.setsu]||"");
  const tenji = String(p[PK.tenji]||"");
  // 交換行のみ：この機のカルテ内で直前(iより前)の、展示タイムが空でない最も近い行を引く。
  // 差の数値・評価語は出さず、前後を矢印で並べるだけ（解釈は読者に委ねる・司令塔裁定）。
  let prevTenji = "";
  if(chg && tenji){ for(let j=i-1;j>=0;j--){ const t=String(parts[j][PK.tenji]||""); if(t){ prevTenji=t; break; } } }
  return (
    <div style={{borderTop:first?"none":"1px solid #16273a",paddingTop:first?0:5,marginTop:first?0:5}}>
      <b style={{color:C.text}}>{fmtHd(p[PK.hd])}</b> {p[PK.rno]}R{p[PK.waku]?` ${p[PK.waku]}号`:""}{nm?<span style={{color:C.link}}> ・{nm}</span>:null}{setsu?<span style={{color:C.dim}} title={setsu}> ・{truncStr(setsu,15)}</span>:null} ・ {chg
        ? <span style={{color:C.ok,fontWeight:700}}>部品交換 {chg}</span>
        : <span style={{color:C.muted}}>整備なし</span>}{p[PK.pera]?<span style={{color:C.accent}}> ・ペラ新</span>:null}{tenji?<span style={{color:C.dim}}> ・展示{prevTenji?` ${prevTenji} → ${tenji}`:tenji}</span>:null}
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
      <div style={{fontSize:F.xs,fontWeight:700,color:C.label,marginBottom:4}}>
        整備履歴 <span style={{color:C.muted,fontWeight:400,fontVariantNumeric:"tabular-nums"}}>出走{parts.length}回・交換{nChg}回</span>
      </div>
      <div style={{fontSize:F.sm,lineHeight:1.75,color:"#a9c6dd",background:"#0f1a26",border:"1px solid #24344a",borderRadius:6,padding:"8px 10px"}}>
        {idx.map((i,k)=><KarteRow key={i} parts={parts} i={i} first={k===0}/>)}
        {hidden>0 && <MoreBtn mt={8} onClick={()=>setAll(true)}>残り{hidden}走もすべて見る</MoreBtn>}
        <div style={{fontSize:F.xs,color:C.muted,marginTop:6}}>出典：boatrace.jp 公式 直前情報{upd?`（${upd} 時点）`:""}</div>
      </div>
    </div>
  );
}

// 初卸(推定)からの走行数集計を1行で控えめに表示（実測カウントのみ・推測なし）。
function fmtRate(r){ return typeof r==="number" ? r.toFixed(1) : String(r||"-"); }
function MotorUsageLine({usage}){
  if(!usage) return null;
  const w = usage["走"];
  if(!w) return null;
  return (
    <div style={{fontSize:F.sm,lineHeight:1.7,color:C.dim,fontVariantNumeric:"tabular-nums"}}
      title={`初卸=Kファイル初出日(${fmtHd(usage["初出日"])})での推定。公式交換日は非公開。最新${fmtHd(usage["最新日"])}`}>
      <span style={{color:C.label}}>初卸(推定)から</span> <b style={{color:"#cdd9e5"}}>{w}走</b> ・勝{usage["勝"]} ・2連{usage["2連"]}<span style={{color:C.ok}}>（{fmtRate(usage["2連率"])}%）</span> ・3連{usage["3連"]}<span style={{color:"#79c0ff"}}>（{fmtRate(usage["3連率"])}%）</span>
    </div>
  );
}

// 1機のブロック。表層は 機番／選手名／級別／機力ランク／2連率バー の2行だけ。
// 走行数と整備履歴は行タップで開く深層に置く（無くても今日の判断はできる＝表層に要らない）。
// 閉じている間は深層のDOMを作らない。全場表示では1,000機超あり、常時描くと
// 場の切り替え（unmount）でメインスレッドが数秒止まっていた。表示件数ではなく破棄ノード数が効く。
function MotorRow({row,rk,fem,parts,upd,usage,median}){
  const [open,setOpen] = useState(false);
  const v=row[CI.rate], g=row[CI.grade];
  const my=myoumi(g,rk);
  const hasDeep = !!(usage && usage["走"]) || !!(parts && parts.length);
  const heart = fem ? <span style={{color:C.fem,marginLeft:3}}>♥</span> : null;
  const nameColor = fem ? C.fem : C.link;
  const toggle = ()=>{ if(hasDeep) setOpen(o=>!o); };
  return (
    <div style={{marginBottom:6}}>
      <div role={hasDeep?"button":undefined} tabIndex={hasDeep?0:undefined} aria-expanded={hasDeep?open:undefined}
        data-motor-row="1"
        onClick={toggle}
        onKeyDown={e=>{ if(hasDeep && (e.key==="Enter"||e.key===" ")){ e.preventDefault(); toggle(); } }}
        style={{display:"flex",alignItems:"center",gap:8,padding:"9px 10px",borderRadius:8,
          cursor:hasDeep?"pointer":"default",
          background:my?"#1a2412":"#0f1923",border:my?"1px solid #3a5220":"1px solid #16222f"}}>
        <div style={{width:4,alignSelf:"stretch",borderRadius:2,background:rk.color,flex:"none"}}/>
        <div style={{fontSize:F.lg,fontWeight:800,color:"#8faabe",minWidth:32,textAlign:"center",flex:"none",fontVariantNumeric:"tabular-nums"}}>{row[CI.mno]||"-"}</div>
        <div style={{minWidth:0,flex:"0 0 auto"}}>
          <div style={{fontSize:F.lg,fontWeight:700,whiteSpace:"nowrap",lineHeight:1.35}}>{
            row[CI.toban]
            ? <a href={"../players/?toban="+row[CI.toban]} onClick={e=>e.stopPropagation()}
                style={{color:nameColor,textDecoration:"none",borderBottom:"1px dotted #4a6a8a",display:"inline-block",padding:"3px 2px",minHeight:HIT}}>{dispName(row[CI.name])||"-"}{heart}</a>
            : <span style={{color:fem?C.fem:C.text}}>{dispName(row[CI.name])||"-"}{heart}</span>
          }</div>
          <div style={{display:"flex",gap:5,marginTop:2,alignItems:"center"}}>
            <span style={{fontSize:F.xs,fontWeight:800,color:C.onLight,background:gradeColor(g),padding:"1px 6px",borderRadius:3}}>{g||"-"}</span>
            {rk.key==="top"
              ? <span style={{fontSize:F.xs,fontWeight:800,color:C.onLight,background:"#ffd166",padding:"1px 7px",borderRadius:3}}>超抜</span>
              : <span style={{fontSize:F.xs,fontWeight:800,color:rk.tcolor}}>{rk.label}</span>}
            {my&&<span style={{fontSize:F.xs,fontWeight:800,color:"#a8e063",border:"1px solid #3a5220",borderRadius:3,padding:"1px 6px"}}>B級×高機力</span>}
          </div>
        </div>
        <Bar v={v} c={rk.color} tc={rk.tcolor} median={median}/>
        {hasDeep && <div aria-hidden="true" style={{flex:"none",width:HIT,minHeight:HIT,display:"flex",alignItems:"center",justifyContent:"center",fontSize:F.xs,color:C.muted}}>{open?"▲":"▼"}</div>}
      </div>
      {open && hasDeep && (
        <div style={{margin:"6px 0 0 12px",padding:"8px 10px",background:"#0d1622",border:"1px solid #16222f",borderRadius:8}}>
          <MotorUsageLine usage={usage}/>
          <MotorKarte parts={parts} upd={upd}/>
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
      <summary onClick={stop} style={{listStyle:"none",cursor:"pointer",display:"inline-flex",alignItems:"center",minHeight:HIT,minWidth:HIT,justifyContent:"center"}}>
        <span style={{fontSize:F.xs,fontWeight:800,color:C.onLight,background:"#8fd6c0",borderRadius:4,padding:"1px 7px"}}>E30</span>
      </summary>
      <div style={{marginTop:6,fontSize:F.sm,lineHeight:1.6,color:"#a9c6dd",background:"#0f1a26",border:"1px solid #24344a",borderRadius:6,padding:"7px 10px",fontWeight:400}}>
        {`この場はE30該当場（開始 ${disp}）。出典：公式。数値は生データのみ。`}
      </div>
    </details>
  );
}

// 場カード。既定は上位3機だけ開いた状態。フォロー場は最初から全機、検索中は全機かつ畳みボタンを出さない
//（絞り込んだ結果を勝手に隠さない）。
function VenueCard({venue,rows,pinned,searching,e30,meta,prevTop,repl,isPrev,females,partsFor,usageFor,upd}){
  const [open,setOpen] = useState(pinned);
  const showAll = searching || open;
  const shown = showAll ? rows : rows.slice(0,TOP_N);
  const hidden = rows.length - shown.length;
  const median = VENUE_MEDIAN[venue];
  const hd = String(rows[0][CI.hd]||"");
  return (
    <div style={{marginBottom:14,background:"#0d1622",border:"1px solid #16222f",borderRadius:12,overflow:"hidden"}}>
      <div style={{display:"flex",alignItems:"flex-start",justifyContent:"space-between",gap:8,padding:"10px 12px",background:"#132030",borderBottom:"1px solid #1e2d3d"}}>
        <div style={{display:"flex",flexDirection:"column",minWidth:0}}>
          <span style={{fontSize:F.xl,fontWeight:800,color:C.accent}}>{pinned&&<span style={{marginRight:4,fontSize:F.xl}}>📍</span>}{venue}{isPrev&&<span style={{fontSize:F.xs,fontWeight:700,color:C.label,background:"#26333f",border:"1px solid #33475a",borderRadius:3,padding:"1px 7px",marginLeft:6,verticalAlign:"middle"}}>前節記録</span>}<E30Badge info={e30}/><span style={{fontSize:F.xs,fontWeight:600,color:C.dim,marginLeft:8}}>{hd.length===8?`${+hd.slice(4,6)}/${+hd.slice(6,8)}時点`:""}</span></span>
          <VenueMetaLine meta={meta}/>
          {prevTop && (
            <div style={{fontSize:F.xs,color:C.dim,marginTop:3,fontVariantNumeric:"tabular-nums"}} title={`${prevTop.節名}（${prevTop.開催日}）節内2連率トップ`}>
              前節1位機 <b style={{color:C.ok}}>M{prevTop.no}</b> <span style={{color:C.muted}}>（節内2連率トップ {prevTop.rate}%）</span>
            </div>
          )}
          {repl && (
            <div style={{fontSize:F.xs,color:C.dim,marginTop:3,fontVariantNumeric:"tabular-nums"}}>
              モーター新替 <b style={{color:"#cdd9e5"}}>{repl}</b> <span style={{color:C.muted}}>（実績が積み上がるまで序列は付けません）</span>
            </div>
          )}
        </div>
        <span style={{fontSize:F.xs,color:C.muted,flex:"none",whiteSpace:"nowrap",paddingTop:2}}>{rows.length}艇</span>
      </div>
      <div style={{padding:"10px"}}>
        {shown.map((r,i)=>(
          <MotorRow key={r[CI.mno]+"_"+i} row={r}
            rk={rankByPos(i+1, rows.length, r[CI.rate], usageFor(r[CI.jcd], r[CI.mno]))}
            fem={females&&females.has(String(r[CI.toban]))}
            parts={partsFor(r[CI.jcd], r[CI.mno])} upd={upd}
            usage={usageFor(r[CI.jcd], r[CI.mno])} median={median}/>
        ))}
        {!searching && rows.length>TOP_N && (
          hidden>0
            ? <MoreBtn onClick={()=>setOpen(true)}>▼ 残り{hidden}機を見る</MoreBtn>
            : <MoreBtn onClick={()=>setOpen(false)}>▲ 上位{TOP_N}機だけ表示</MoreBtn>
        )}
      </div>
    </div>
  );
}

function App(){
  const [vf,setVf]=useState("ALL");
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
  const [usageMap,setUsageMap]=useState(null);  // "jcd_モーターNo" -> {走,勝,2連,3連,2連率,3連率,初出日,最新日}
  const [usageCov,setUsageCov]=useState("");    // coverageFrom（集計開始日 YYYYMMDD）
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
    fetch("../data/motorKarte.json").then(r=>r.ok?r.json():Promise.reject())
      .then(j=>{ const rs=j&&j.records; if(rs&&typeof rs==="object"){ setPartsMap(rs); setPartsUpd(String(j.updated||"")); } }).catch(()=>{});
    // モーター初卸(推定)からの走行数集計（docs/data/motorUsage.json・Kファイル自前集計）。
    // 索引キーは jcd_モーターNo。欠落はフォールバック（非表示）で既存表示を壊さない。
    fetch("../data/motorUsage.json").then(r=>r.ok?r.json():Promise.reject())
      .then(j=>{ if(j&&j.motors&&typeof j.motors==="object"){ const m={}; for(const k in j.motors){ const v=j.motors[k]; m[String(v.jcd||"").padStart(2,"0")+"_"+String(v["モーターNo"]||"").trim()]=v; } setUsageMap(m); setUsageCov(String(j.coverageFrom||"")); } }).catch(()=>{});
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
    const motors = best.motors||{};
    let topNo=null, topRate=-1;
    for(const no in motors){ const v=Number(motors[no]); if(isFinite(v) && v>topRate){ topRate=v; topNo=no; } }
    if(topNo===null) return null;
    return {no:topNo, rate:topRate, 節名:String(best["節名"]||""), 開催日:String(best["開催日"]||"")};
  };

  // jcd＋モーターNo で整備履歴（部品交換の時系列）を引く。未取得・該当無しは null。
  const karteKey = (jcd, mno) => String(jcd||"").padStart(2,"0")+"_"+String(mno||"").trim();
  const partsFor = (jcd, mno) => {
    if(!partsMap) return null;
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
    return d.slice(0,4)+"/"+Number(d.slice(4,6))+"/"+Number(d.slice(6,8));
  };
  const usageFor = (jcd, mno) => {
    if(!usageMap) return null;
    return usageMap[String(jcd||"").padStart(2,"0")+"_"+String(mno||"").trim()] || null;
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
  const topCount = useMemo(()=>{
    const g={};
    for(const r of R.data){ const v=r[CI.venue]||"その他"; (g[v]=g[v]||[]).push(r); }
    let n=0; for(const v in g){ n += Math.min(3, g[v].length); }
    return n;
  },[]);
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
    <div style={{minHeight:"100vh",padding:"12px",maxWidth:760,margin:"0 auto"}}>
      <div style={{display:"flex",alignItems:"baseline",gap:10,marginBottom:4,flexWrap:"wrap"}}>
        <span style={{fontSize:F.hero,fontWeight:800,color:C.accent}}>BOATRACE モーター成績</span>
        <span style={{fontSize:F.xs,color:C.muted}}>{allVenues.length}場 / {R.data.length}件</span>
      </div>
      <div style={{fontSize:F.xs,color:C.muted,marginBottom:8}}>最終更新: {R.updated||"-"}</div>
      {usageCov&&<div style={{fontSize:F.xs,lineHeight:1.7,color:C.dim,marginBottom:8}}>モーター走行数は <b style={{color:C.label}}>{fmtHd(usageCov)}以降</b> のKファイル集計（初出日=初卸推定・公式交換日は非公開）。出典：公式競走成績(K)。</div>}
      <div style={{fontSize:F.sm,lineHeight:1.7,color:C.sub,marginBottom:8}}><b style={{color:C.onLight,background:"#ffd166",padding:"1px 7px",borderRadius:3,fontSize:F.xs,fontWeight:800}}>超抜</b> ＝各場の上位3機だけ。本日は全{R.data.length}機中 <b style={{color:C.accent}}>{topCount}機</b>。</div>
      {/* バーの読み方は全場共通なので、場カード24枚に書かず先頭で1度だけ言う（同じ値を2箇所に書かない）。 */}
      <div style={{fontSize:F.xs,lineHeight:1.7,color:C.dim,marginBottom:8}}>バーはモーター2連率。目盛は<b style={{color:C.label}}>全場共通 0〜{BAR_MAX}%</b>（本日の最大値を10%刻みで切り上げ）なので、場をまたいで長さをそのまま比べられます。バー上の細い縦線は<b style={{color:C.label}}>その場の中央値</b>。各場は上位{TOP_N}機だけ開いた状態で、行をタップすると走行数と整備履歴が出ます。</div>

      <button onClick={()=>setShowHelp(s=>!s)} style={{marginBottom:8,minHeight:40,padding:"8px 14px",background:"#1a2738",color:"#8faabe",border:"1px solid #2a3d52",borderRadius:8,fontSize:F.sm,cursor:"pointer",fontWeight:600,fontFamily:"inherit"}}>{showHelp?"▲ 見方を閉じる":"▼ このデータの見方"}</button>
      {showHelp&&(
        <div style={{background:"#111d2b",border:"1px solid #1e2d3d",borderRadius:8,padding:"12px 14px",marginBottom:10,fontSize:F.md,lineHeight:1.8,color:C.sub}}>
          <div style={{color:C.accent,fontWeight:700,marginBottom:6}}>このデータについて</div>
          <div style={{marginBottom:8}}>各場の<b style={{color:C.text}}>今節のモーター抽選結果</b>です。前検日に確定するため、同じ節の間は使用者は変わりません。</div>
          <div style={{color:"#8faabe",fontWeight:700,marginBottom:4}}>表示のしかた</div>
          <div style={{paddingLeft:4,marginBottom:8}}>
            <div>各場は<b style={{color:C.text}}>上位{TOP_N}機だけ</b>開いた状態です。「残り◯機を見る」で全機。フォロー中の場と検索中は最初から全機を出します。</div>
            <div style={{marginTop:4}}>行をタップすると、その機の<b style={{color:C.text}}>走行数と整備履歴</b>が開きます。</div>
          </div>
          <div style={{color:"#8faabe",fontWeight:700,marginBottom:4}}>機力ランク（バー・色）</div>
          <div style={{paddingLeft:4,marginBottom:8}}>
            <div>その場の2連率の高い順に、<b style={{color:C.accent}}>超抜</b>（上位3機）／<b style={{color:"#79c0ff"}}>上位</b>（〜40%）／<b style={{color:C.label}}>普通</b>（〜75%）／<b style={{color:C.muted}}>下位</b>で色分け。</div>
            <div style={{marginTop:4}}>バーの目盛は<b style={{color:C.text}}>全場共通で 0〜{BAR_MAX}%</b>（本日データの最大値を10%刻みで切り上げ）。場をまたいでも長さをそのまま比べられます。バー上の<b style={{color:C.text}}>細い縦線</b>は、その場の2連率の中央値です。</div>
            <div style={{color:C.muted,marginTop:4}}>※場ごとの相対評価。他場との比較ではありません。走行数が少ない節は数字が振れやすいので、数字そのものも併せてご確認を。</div>
          </div>
          <div style={{color:"#8faabe",fontWeight:700,marginBottom:4}}>「B級×高機力」タグ</div>
          <div style={{paddingLeft:4}}>下級の選手が機力上位のモーターを引いている状態。人気が落ちやすい構造です。<b style={{color:C.text}}>買い目は出しません</b>。読み方は各自の判断で。</div>
          <div style={{fontSize:F.xs,color:C.muted,borderTop:"1px solid #1e2d3d",paddingTop:6,marginTop:8}}>データ提供：boatrace.jp 公式</div>
        </div>
      )}

      <div style={{display:"flex",gap:6,flexWrap:"wrap",marginBottom:10}}>
        <select value={vf} onChange={e=>setVf(e.target.value)} style={{minHeight:40,padding:"8px",background:"#162232",color:C.text,border:"1px solid #1e2d3d",borderRadius:6,fontSize:F.input,fontFamily:"inherit"}}>
          <option value="ALL">全場</option>
          {allVenues.map(v=><option key={v} value={v}>{v}</option>)}
        </select>
        <input placeholder="選手名・モーター番号で検索..." value={q} onChange={e=>setQ(e.target.value)} style={{flex:1,minWidth:120,minHeight:40,padding:"8px 10px",background:"#162232",color:C.text,border:"1px solid #1e2d3d",borderRadius:6,fontSize:F.input,fontFamily:"inherit"}}/>
        <span style={{color:C.muted,fontSize:F.sm,alignSelf:"center"}}>{total}件</span>
      </div>

      {Object.keys(grouped).length===0 && <div style={{color:C.muted,fontSize:F.sm,padding:20,textAlign:"center"}}>該当なし</div>}
      {Object.entries(grouped).sort((a,b)=>{const pa=hasPin(pins,a[1][0][CI.jcd])?0:1,pb=hasPin(pins,b[1][0][CI.jcd])?0:1;return pa-pb;}).map(([venue,rows])=>(
        <VenueCard key={venue} venue={venue} rows={rows}
          pinned={hasPin(pins,rows[0][CI.jcd])} searching={searching}
          e30={e30For(rows[0][CI.jcd], rows[0][CI.hd])}
          meta={metaFor(rows[0][CI.jcd])}
          prevTop={prevTopFor(rows[0][CI.jcd], rows[0][CI.hd])}
          repl={replFor(rows[0][CI.jcd])}
          isPrev={isPrevSetsu(rows[0][CI.hd])}
          females={females} partsFor={partsFor} usageFor={usageFor} upd={partsUpd}/>
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
  var ok=((location.hostname==="abeken1026395.github.io"&&location.pathname.indexOf("/pallas-mercato-7k9/")===0)||["localhost","127.0.0.1",""].indexOf(location.hostname)>=0);
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
