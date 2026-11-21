const { useState, useMemo, useEffect } = React;
const R = window.__D;
/* ===== 場フォロー（出走表・モーター・見どころと共有。キー br_stadium ／ 形式 [{code,name}] ／ code は2桁文字列） ===== */
function lsGet(k,d){ try{ var v=localStorage.getItem(k); return v?JSON.parse(v):d; }catch(e){ return d; } }
function lsSet(k,v){ try{ localStorage.setItem(k,JSON.stringify(v)); }catch(e){} }
function pinCode(c){ var t=String(c==null?"":c); return t.length===1 ? "0"+t : t; }
function loadPin(){ var a=lsGet("br_stadium",[]); return Array.isArray(a)?a:[]; }
function hasPin(list,code){ return list.some(function(p){ return p && pinCode(p.code)===pinCode(code); }); }
function nextPin(list,code,name){
  if(hasPin(list,code)) return list.filter(function(p){ return p && pinCode(p.code)!==pinCode(code); });
  return [{code:pinCode(code),name:name||""}].concat(list);
}
const HEAD = {"01": "南", "02": "南東", "03": "北東", "04": "北", "05": "西", "06": "北", "07": "南西", "08": "北西", "09": "北西", "10": "南", "11": "南", "12": "南", "13": "南西", "14": "南東", "15": "北", "16": "南", "17": "南西", "18": "北西", "19": "西", "20": "西", "21": "東", "22": "東", "23": "南西", "24": "東"};
// 「荒れるサイン」「SG・G1開催時」は実測で書いた桐生・大村だけ表示する（2026-09-11 裁定）
const SIGN_SHOW = {"01": true, "24": true};
const SG_SHOW = {"01": true, "13": true, "24": true};  // SG・G1開催時を出す場（荒れるサインとは別に決める）
// 風向は吹いてくる方角で呼ぶ。1マーク方向の逆側＝追い風の吹いてくる方角
const OPP_DIR = {"北": "南", "北東": "南西", "東": "西", "南東": "北西", "南": "北", "南西": "北東", "西": "東", "北西": "南東"};
const TIDE = {"03": "日本唯一の河川コース。潮の満ち引き＋川の流れが複合。上げ潮はスロー有利、下げ潮はダッシュ有利。満潮時は2マーク側の河川方面から逆流しうねりが出る。風と複合で大荒れ。当地経験の有無が大きい。", "04": "運河を介すため海と直結せず干満差は小さめ。基本は満潮=イン寄り/干潮=アウト寄りだが影響は限定的。大潮の満潮時のみうねりに注意。", "06": "汽水で潮の影響あり。満潮・上げ潮=イン寄り、干潮・下げ潮=アウト寄り。風の影響が大きい水面なので潮と風を合わせて見る。", "07": "汽水で潮の影響あり。満潮・上げ潮=イン寄り、干潮・下げ潮=アウト寄り。普段はイン堅めの静水面寄り。", "08": "海水で潮あり。満潮・上げ潮=イン寄り、干潮・下げ潮=アウト寄り。横風(伊勢湾)の影響も受ける。", "14": "海水で潮あり(鳴門海峡の潮流域)。満潮・上げ潮=イン寄り、干潮・下げ潮=アウト寄り。大潮は影響強。小潮は潮より番組・場特性(終盤R荒れ)が優先。", "15": "海水で潮あり。満潮・上げ潮=イン寄り、干潮・下げ潮=アウト寄り。ナイター。", "16": "海水で潮あり。満潮・上げ潮=イン寄り、干潮・下げ潮=アウト寄り。", "17": "海水で潮あり。満潮・上げ潮=イン寄り、干潮・下げ潮=アウト寄り。瀬戸内の潮流・横風に注意。", "18": "海水で潮あり(潮見表あり)。満潮・上げ潮=イン寄り、干潮・下げ潮=アウト寄り。元々イン1着率が高い場で、満潮はさらにイン優勢。", "19": "堤防で仕切られ干満差は小さめ。基本は満潮=イン寄り/干潮=アウト寄りだが影響は限定的。", "20": "2マーク付近が洞海湾と直結し潮流をもろに受ける。上げ潮はイン2艇有利、下げ潮はセンター有利。満潮時は1マークが潮溜まりになり全速ターンが決めにくくイン優勢、干潮・下げ潮はセンターまくりが増える。", "22": "汽水(那珂川河口)で潮＋川の流れの影響。満潮・上げ潮=イン寄り、干潮・下げ潮=アウト寄り。うねりが出ると難水面。", "24": "防波堤で仕切られ干満差は小さめ。静水面。潮の影響は限定的だが、時間で風向きが変わりやすい。"};
const ARARE_COLOR = { "低":"#3fb950", "中":"#d29922", "高":"#f85149" };
const WATER_COLOR = { "淡水":"#58a6ff", "海水":"#3fb1c9", "汽水":"#dcbd78" };
const PSYCH = { "gap":{label:"射幸心×童謡",c:"#ffd166"}, "nostalgia":{label:"郷愁",c:"#7fe0a0"}, "tension":{label:"緊張・高揚",c:"#f85149"}, "local-pride":{label:"ご当地",c:"#58a6ff"}, "mystery":{label:"ミステリー",c:"#dcbd78"}, "class":{label:"格調",c:"#dcbd78"}, "none":{label:"BGMなし",c:"#8faabe"} };
const psychOf = (bg) => bg.status === "none" ? "none" : bg.psych;
const STATUS_LABEL = { "none":"締切BGMなし", "unknown":"曲名は未特定", "page_exists":"公式ページに記載あり（曲名は未確認）" };
const PRESENT = { "yes":{label:"場立ちあり",c:"#3fb950"}, "official":{label:"公式記載",c:"#58a6ff"}, "advisor":{label:"解説アドバイザー",c:"#dcbd78"}, "paper":{label:"予想紙",c:"#d29922"} };
const AROUND_KIND = { "food":{ord:0,label:""}, "bath":{ord:1,label:"♨ 温泉"}, "spot":{ord:2,label:"📍 立ち寄り"} };

const sgHead = t => (t||"").split("\n\n")[0];
const sgRest = t => (t||"").split("\n\n").slice(1).join("\n\n");

function App() {
  const [q, setQ] = useState("");
  const [areaF, setAreaF] = useState("ALL");
  const [arareF, setArareF] = useState("ALL");
  const [open, setOpen] = useState(null);
  const [announcers, setAnnouncers] = useState(null);
  const [gourmet, setGourmet] = useState(null);
  const [gOpen, setGOpen] = useState(null);
  const [sgOpen, setSgOpen] = useState(null);
  const [vOpen, setVOpen] = useState(null);
  const [fanfare, setFanfare] = useState(undefined); // undefined＝読み込み中（場内BGMの読み物が後から上に出て一覧がずれないよう、そろうまで一覧を出さない。2026-11-09）
  const [bOpen, setBOpen] = useState(null);
  const [fanIntro, setFanIntro] = useState(false);
  const [yosouya, setYosouya] = useState(null);
  const [yOpen, setYOpen] = useState(null);
  const [trifecta, setTrifecta] = useState(null);
  const [b1second, setB1second] = useState(null);
  const [champ, setChamp] = useState(null);
  const [champOpen, setChampOpen] = useState(null);
  const [pins, setPins] = useState(loadPin);
  const [pinOnly, setPinOnly] = useState(false);
  const togglePin = (code, name) => { const nx = nextPin(pins, code, name); setPins(nx); lsSet("br_stadium", nx); };

  useEffect(() => {
    fetch("../announcers/announcers.json?v=" + Date.now())
      .then(r => r.json())
      .then(setAnnouncers)
      .catch(() => setAnnouncers([]));
    fetch("gourmet.json?v=" + Date.now())
      .then(r => r.json())
      .then(setGourmet)
      .catch(() => setGourmet({}));
    fetch("../data/fanfareBgm.json?v=" + Date.now())
      .then(r => r.json())
      .then(setFanfare)
      .catch(() => setFanfare(null));
    fetch("../data/yosouya.json?v=" + Date.now())
      .then(r => r.json())
      .then(setYosouya)
      .catch(() => setYosouya(null));
    fetch("../payouts/trifectaTop.json?v=" + Date.now())
      .then(r => r.json())
      .then(setTrifecta)
      .catch(() => setTrifecta(null));
    fetch("../payouts/boat1Second.json?v=" + Date.now())
      .then(r => r.json())
      .then(setB1second)
      .catch(() => setB1second(null));
    fetch("../payouts/champRace.json?v=" + Date.now())
      .then(r => r.json())
      .then(setChamp)
      .catch(() => setChamp(null));
  }, []);
  const BOAT_COLOR = { 2:"#9aa4b3", 3:"#f85149", 4:"#58a6ff", 5:"#ffd166", 6:"#3fb950" };
  const ancByVenue = (name) => (announcers || []).filter(a => (a.venues||[]).includes(name));

  const areas = useMemo(() => [...new Set(R.stadiums.map(s => s.area))], []);
  const filtered = useMemo(() => {
    return R.stadiums.filter(s => {
      if (pinOnly && !hasPin(pins, s.code)) return false;
      if (areaF !== "ALL" && s.area !== areaF) return false;
      if (arareF !== "ALL" && s.arare !== arareF) return false;
      if (q) { const t = (parseInt(s.code,10)+s.name+s.feature+(SIGN_SHOW[s.code]?s.sign:"")+s.water+s.area).toLowerCase(); if (!t.includes(q.toLowerCase())) return false; }
      return true;
    });
  }, [q, areaF, arareF, pinOnly, pins]);

  return (
    <div style={{minHeight:"100vh",padding:"12px",maxWidth:900,margin:"0 auto"}}>
      <div style={{display:"flex",alignItems:"baseline",gap:10,marginBottom:4,flexWrap:"wrap"}}>
        <span className="kataTitle" style={{fontSize:20,fontWeight:800,color:"#ffd166"}}>24場の特性</span>
        {filtered.length<R.stadiums.length && <span style={{fontSize:12,color:"#8aa0b4"}}>{filtered.length}場を表示</span>}
      </div>
      <div style={{fontSize:11,color:"#8aa0b4",marginBottom:10}}>{R.in1Note}</div>

      <div style={{display:"flex",gap:6,flexWrap:"wrap",marginBottom:10}}>
        <input placeholder="場名・特徴で検索..." value={q} onChange={e=>setQ(e.target.value)} style={{flex:1,minWidth:140,padding:"7px 10px",background:"#162232",color:"#e0e6ed",border:"1px solid #1e2d3d",borderRadius:6,fontSize:13}}/>
        <select value={areaF} onChange={e=>setAreaF(e.target.value)} style={{padding:"7px",background:"#162232",color:"#e0e6ed",border:"1px solid #1e2d3d",borderRadius:6,fontSize:13}}>
          <option value="ALL">全地区</option>
          {areas.map(a=><option key={a} value={a}>{a}</option>)}
        </select>
        <select value={arareF} onChange={e=>setArareF(e.target.value)} style={{padding:"7px",background:"#162232",color:"#e0e6ed",border:"1px solid #1e2d3d",borderRadius:6,fontSize:13}}>
          <option value="ALL">荒れ度すべて</option>
          <option value="低">堅い(低)</option>
          <option value="中">標準(中)</option>
          <option value="高">荒れる(高)</option>
        </select>
        <button onClick={()=>setPinOnly(v=>!v)} style={{padding:"7px 12px",fontSize:13,fontWeight:700,borderRadius:6,cursor:"pointer",border:"1px solid "+(pinOnly?"#eef3f8":"#1e2d3d"),background:pinOnly?"#eef3f8":"#162232",color:pinOnly?"#0b1726":"#8faabe",whiteSpace:"nowrap"}}>📍 フォロー中{pins.length?" "+pins.length:""}</button>
      </div>

      <div style={{fontSize:11,color:"#8497ab",lineHeight:1.7,marginBottom:10,padding:"9px 11px",background:"#131e2a",border:"1px solid #1e2d3d",borderRadius:8}}>📍を押すと場をフォロー。フォローした場は出走表の場一覧で先頭に並びます。フォローはこの端末にのみ保存され、外部には送信されません。</div>
      <div style={{display:"flex",gap:14,fontSize:11,color:"#8faabe",marginBottom:10,flexWrap:"wrap"}}>
        <span><span style={{color:ARARE_COLOR["低"]}}>●</span> 低=堅い/イン強</span>
        <span><span style={{color:ARARE_COLOR["中"]}}>●</span> 中=標準</span>
        <span><span style={{color:ARARE_COLOR["高"]}}>●</span> 高=波乱多い</span>
        <span><span style={{color:"#ffd166"}}>企</span> =通常時は企画レース込み</span>
      </div>

      {fanfare && fanfare.column && (
      <div style={{marginBottom:10,background:"#1a1222",border:"1px solid #4a2f5a",borderRadius:10,padding:"10px 12px"}}>
        <div onClick={()=>setFanIntro(!fanIntro)} style={{display:"flex",alignItems:"center",cursor:"pointer",gap:8}}>
          <span style={{fontSize:14,fontWeight:800,color:"#dcbd78"}}>🎵 {fanfare.column.title}</span>
          <span style={{marginLeft:"auto",fontSize:11,color:"#dcbd78",whiteSpace:"nowrap",flexShrink:0}}>{fanIntro?"▲ 閉じる":"▼ 読む"}</span>
        </div>
        <div style={{fontSize:12,color:"#d8c5e0",lineHeight:1.7,marginTop:6}}>{fanfare.column.lead}</div>
        {fanIntro && (
        <div style={{marginTop:8}}>
          {(fanfare.column.angles||[]).map((a,i)=>(
            <div key={i} style={{marginBottom:6,paddingLeft:8,borderLeft:"2px solid "+((PSYCH[a.key]&&PSYCH[a.key].c)||"#dcbd78")}}>
              <span style={{fontSize:12,fontWeight:700,color:(PSYCH[a.key]&&PSYCH[a.key].c)||"#dcbd78"}}>{a.label}</span>
              <div style={{fontSize:12,color:"#c5d2e0",lineHeight:1.6}}>{a.text}</div>
            </div>
          ))}
          {fanfare.common && fanfare.common.fanfare && (
          <div style={{marginTop:8,background:"#0f1a26",border:"1px solid #2a3d52",borderRadius:8,padding:"8px 10px"}}>
            <div style={{fontSize:12,fontWeight:700,color:"#dcbd78",marginBottom:3}}>🎺 ピットアウトのファンファーレ（全国共通）</div>
            {fanfare.common.fanfare.hook && <div style={{fontSize:12,color:"#e6d0ee",lineHeight:1.7,marginBottom:5}}>{fanfare.common.fanfare.hook}</div>}
            <div style={{fontSize:12,color:"#c5d2e0",lineHeight:1.6}}>{fanfare.common.fanfare.note}</div>
            <div style={{fontSize:11,color:"#9a8db0",lineHeight:1.6,marginTop:4}}>作曲：{(fanfare.common.fanfare.composers||[]).join(" ／ ")}</div>
            <div style={{fontSize:11,color:"#9a8db0",lineHeight:1.6}}>{fanfare.common.fanfare.history}</div>
          </div>
          )}
          {fanfare.column.disclaimer && <div style={{marginTop:6,fontSize:10.5,color:"#8a7d9a",lineHeight:1.5}}>※ {fanfare.column.disclaimer}</div>}
        </div>
        )}
      </div>
      )}

      {fanfare===undefined && <div className="dzf-st dzf-ld" role="status" style={{minHeight:"100vh"}}>読み込んでいます</div>}
      <div style={{display:fanfare===undefined?"none":"grid",gap:8}}>
        {filtered.map(s => {
          const isOpen = open === s.code;
          return (
            <div key={s.code} onClick={()=>setOpen(isOpen?null:s.code)} style={{background:"#111d2b",border:"1px solid #1e2d3d",borderRadius:10,padding:"12px 14px",cursor:"pointer"}}>
              <div style={{display:"flex",alignItems:"center",gap:10,flexWrap:"wrap"}}>
                {/* タップ領域は 24×24px 以上（WCAG 2.2 / 2.5.8）。絵文字は 15px のまま、当たり判定だけ広げる */}
                <button type="button" onClick={e=>{e.stopPropagation();togglePin(s.code,s.name);}} title="この場をフォロー" aria-pressed={hasPin(pins,s.code)} aria-label={s.name+(hasPin(pins,s.code)?"のフォローを解除":"をフォロー")} style={{fontSize:15,lineHeight:1,cursor:"pointer",flexShrink:0,padding:0,minWidth:44,minHeight:44,margin:-10,display:"inline-flex",alignItems:"center",justifyContent:"center",background:"none",border:"none",fontFamily:"inherit",userSelect:"none",opacity:hasPin(pins,s.code)?1:0.9,filter:hasPin(pins,s.code)?"none":"grayscale(1)"}}>📍</button>
                <span style={{fontSize:11,fontWeight:700,color:"#6b7f95",background:"#0b1219",border:"1px solid #2a3d52",borderRadius:6,padding:"2px 7px",minWidth:30,textAlign:"center"}}>{parseInt(s.code,10)}</span>
                <span style={{fontSize:16,fontWeight:800,color:"#e0e6ed",minWidth:54}}>{s.name}</span>
                <span style={{fontSize:11,color:"#6b7f95"}}>{s.area}</span>
                <span style={{fontSize:11,padding:"2px 8px",borderRadius:10,background:"#0b1219",border:"1px solid "+WATER_COLOR[s.water],color:WATER_COLOR[s.water]}}>{s.water}</span>
                <span style={{fontSize:12,color:"#ffd166",fontWeight:700,fontVariantNumeric:"tabular-nums"}}>1コース {s.in1}</span>
                {s.kikaku && <span title="通常時は企画レース込み" style={{fontSize:10,fontWeight:700,color:"#ffd166",background:"#ffd16615",border:"1px solid #ffd16655",borderRadius:5,padding:"1px 5px"}}>企</span>}
                <span style={{marginLeft:"auto",fontSize:11,padding:"3px 10px",borderRadius:0,background:"#12233a",border:"1px solid "+ARARE_COLOR[s.arare],color:ARARE_COLOR[s.arare],fontWeight:700}}>荒れ度 {s.arare}</span>
                <span style={{fontSize:12,color:"#6b7f95"}}>{isOpen?"▲":"▼"}</span>
              </div>
              {isOpen && (
                <div style={{marginTop:10,paddingTop:10,borderTop:"1px solid #1e2d3d",fontSize:13,lineHeight:1.7}}>
                  <div style={{marginBottom:8}}><span style={{color:"#8faabe",fontWeight:700}}>水面特性　</span><span style={{color:"#c5d2e0"}}>{s.feature}</span></div>
                  {((trifecta && trifecta.venues && trifecta.venues[s.code]) || (b1second && b1second.venues && b1second.venues[s.code])) && (() => {
                    const tri = trifecta && trifecta.venues && trifecta.venues[s.code];
                    const b1 = b1second && b1second.venues && b1second.venues[s.code];
                    const period = (tri && tri.period) || (b1 && b1.period);
                    const source = (trifecta && trifecta.source) || (b1second && b1second.source);
                    const mx = b1 ? Math.max(...b1.second.map(d => d.share), 1) : 1;
                    return (
                    <div style={{marginBottom:8,background:"#161a26",border:"1px solid #2f3a52",borderRadius:8,padding:"8px 10px"}}>
                      {tri && (<div>
                        <span style={{color:"#9fb5c9",fontWeight:700}}>📊 過去に最も多く出た3連単　</span>
                        <span style={{color:"#e0e6ed",fontVariantNumeric:"tabular-nums"}}><b style={{color:"#ffd166",fontSize:15}}>{tri.combo}</b>（{tri.count}回／全{tri.races}戦・{tri.share}%）</span>
                      </div>)}
                      {b1 && (<div style={{marginTop:tri?8:0,paddingTop:tri?8:0,borderTop:tri?"1px solid #24304a":"none"}}>
                        <span style={{color:"#9fb5c9",fontWeight:700}}>🚤 1号艇が1着だったレースの2着内訳</span>
                        <div style={{fontSize:11,color:"#6b7f95",margin:"3px 0 6px",fontVariantNumeric:"tabular-nums"}}>対象：1号艇が1着だった{b1.firstBoat1}戦（全{b1.races}戦中・1着率{b1.firstBoat1Rate}%）</div>
                        {b1.second.map(d => (
                          <div key={d.boat} style={{display:"flex",alignItems:"center",gap:8,marginBottom:3}}>
                            <span style={{fontSize:11,fontWeight:700,color:BOAT_COLOR[d.boat],minWidth:44}}>{d.boat}号艇</span>
                            <div style={{flex:1,height:12,background:"#0b1219",borderRadius:6,overflow:"hidden"}}>
                              <div style={{width:(d.share/mx*100)+"%",height:"100%",background:BOAT_COLOR[d.boat],opacity:0.85}}></div>
                            </div>
                            <span style={{fontSize:11,color:"#e0e6ed",minWidth:82,textAlign:"right",fontVariantNumeric:"tabular-nums"}}>{Number(d.share).toFixed(1)}%（{d.count}回）</span>
                          </div>
                        ))}
                      </div>)}
                      {champ && champ.venues && champ.venues[s.code] && (() => {
                        const c = champ.venues[s.code];
                        const cmax = c.ranking.length ? c.ranking[0].count : 1;
                        const isCO = champOpen === s.code;
                        return (
                        <div style={{marginTop:8,paddingTop:8,borderTop:"1px solid #24304a"}}>
                          <div onClick={e=>{e.stopPropagation();setChampOpen(isCO?null:s.code);}} style={{display:"flex",alignItems:"center",cursor:"pointer",gap:6,flexWrap:"wrap"}}>
                            <span style={{color:"#ffd166",fontWeight:700}}>🏆 優勝戦の出目ランキング</span>
                            <span style={{fontSize:11,color:"#6b7f95"}}>過去{c.total}戦</span>
                            <span style={{marginLeft:"auto",fontSize:11,color:"#caa23f",whiteSpace:"nowrap",flexShrink:0}}>{isCO?"▲ 閉じる":"▼ 見る"}</span>
                          </div>
                          {isCO && (<div style={{marginTop:6}}>
                            {c.ranking.slice(0,8).map((d,i) => (
                              <div key={d.combo} style={{display:"flex",alignItems:"center",gap:8,marginBottom:3}}>
                                <span style={{fontSize:11,color:"#6b7f95",minWidth:16,textAlign:"right"}}>{i+1}</span>
                                <span style={{fontSize:13,fontWeight:700,color:"#e0e6ed",minWidth:52}}>{d.combo}</span>
                                <div style={{flex:1,height:10,background:"#0b1219",borderRadius:5,overflow:"hidden"}}>
                                  <div style={{width:(d.count/cmax*100)+"%",height:"100%",background:"#caa23f",opacity:0.85}}></div>
                                </div>
                                <span style={{fontSize:11,color:"#e0e6ed",minWidth:60,textAlign:"right",fontVariantNumeric:"tabular-nums"}}>{d.count}回・{d.share}%</span>
                              </div>
                            ))}
                            {c.ranking.length > 8 && <div style={{fontSize:11,color:"#6b7f95",marginTop:2}}>ほか{c.ranking.length-8}種の出目（各{c.ranking[8].count}回以下）</div>}
                            <div style={{marginTop:4,fontSize:11,color:"#6b7f95"}}>優勝戦{c.total}戦（{c.period.from}〜{c.period.to}）で実際に出た出目の集計。優勝戦は各節1回のため対象数は少なめです。</div>
                          </div>)}
                        </div>
                        );
                      })()}
                      {period && <div style={{marginTop:6,fontSize:11,color:"#6b7f95"}}>対象期間 {period.from}〜{period.to}（開催{period.days}日）／出典：{source}</div>}
                      <div style={{marginTop:4,fontSize:11,color:"#c98a8a"}}>※過去に出た回数の割合であり、次のレースの予想ではありません。</div>
                    </div>
                    );
                  })()}
                  {SIGN_SHOW[s.code] && (
                  <div style={{marginBottom:8,background:ARARE_COLOR[s.arare]+"15",border:"1px solid "+ARARE_COLOR[s.arare]+"55",borderRadius:8,padding:"8px 10px"}}>
                    <span style={{color:ARARE_COLOR[s.arare],fontWeight:700}}>⚠ 荒れるサイン　</span>
                    <span style={{color:"#e0e6ed",whiteSpace:"pre-line"}}>{s.sign}</span>
                  </div>
                  )}
                  <div style={{marginBottom:8,background:"#0d2418",border:"1px solid #1e4a32",borderRadius:8,padding:"8px 10px"}}>
                    <span style={{color:"#3fb950",fontWeight:700}}>💨 風（向き）　</span>
                    <span style={{color:"#e0e6ed"}}>スタート→1マークは<b style={{color:"#7fe0a0"}}>{HEAD[s.code]}</b>方向。<b>{HEAD[s.code]}から吹く風（{HEAD[s.code]}風）</b>＝<b>向かい風</b>でイン加速が鈍りアウト・まくり寄り、<b>{OPP_DIR[HEAD[s.code]]}から吹く風（{OPP_DIR[HEAD[s.code]]}風）</b>＝<b>追い風</b>でイン・差し寄り（強いとターンが流れ荒れる）。横向き＝横風。風速2m以下は影響小、3m以上で外寄り、5m以上で荒れ。</span>
                  </div>
                  {TIDE[s.code] && (
                  <div style={{marginBottom:8,background:"#0d1f2e",border:"1px solid #1e3a52",borderRadius:8,padding:"8px 10px"}}>
                    <span style={{color:"#3fb1c9",fontWeight:700}}>🌊 潮・流れ　</span>
                    <span style={{color:"#e0e6ed"}}>{TIDE[s.code]}</span>
                    <div style={{marginTop:4,fontSize:11,color:"#6b9bb5"}}>※大潮ほど干満差が大きく影響大、小潮（長潮・若潮含む）は薄い。満潮/干潮の時刻は当日の潮見表で確認。</div>
                  </div>
                  )}
                  {SG_SHOW[s.code] && (
                  <div style={{background:"#1a1426",border:"1px solid #c8a45e",borderRadius:8,padding:"8px 10px"}}>
                    <span style={{color:"#dcbd78",fontWeight:700}}>🏆 SG・G1開催時　</span>
                    <span style={{color:"#e0e6ed",whiteSpace:"pre-line"}}>{sgHead(s.sg)}</span>
                    {sgRest(s.sg) && (<React.Fragment>
                      {sgOpen===s.code && <div style={{marginTop:6,color:"#e0e6ed",whiteSpace:"pre-line"}}>{sgRest(s.sg)}</div>}
                      <div onClick={e=>{e.stopPropagation();setSgOpen(sgOpen===s.code?null:s.code);}} style={{display:"flex",alignItems:"center",cursor:"pointer",minHeight:24,marginTop:2}}>
                        <span style={{marginLeft:"auto",fontSize:12,color:"#dcbd78",whiteSpace:"nowrap",flexShrink:0}}>{sgOpen===s.code?"▲ 閉じる":"▼ 続きを読む"}</span>
                      </div>
                    </React.Fragment>)}
                  </div>
                  )}
                  {gourmet && gourmet[s.name] && (
                  <div style={{marginTop:8,background:"#2a1410",border:"1px solid #5a2f16",borderRadius:8,padding:"8px 10px"}}>
                    <div onClick={e=>{e.stopPropagation();setGOpen(gOpen===s.code?null:s.code);}} style={{display:"flex",alignItems:"center",cursor:"pointer",minHeight:24}}>
                      <span style={{color:"#ff9a5a",fontWeight:700}}>🍜 場めぐり</span>
                      <span style={{marginLeft:"auto",fontSize:11,color:"#ff9a5a",whiteSpace:"nowrap",flexShrink:0}}>{gOpen===s.code?"▲ 閉じる":"▼ 見る"}</span>
                    </div>
                    {gOpen===s.code && (<div style={{marginTop:2}}>
                    {gourmet[s.name].in && gourmet[s.name].in.length > 0 && (
                    <div style={{marginTop:6}}>
                      <div style={{fontSize:11,color:"#e0a878",fontWeight:700,marginBottom:3}}>場内メシ</div>
                      {gourmet[s.name].in.map((g,i) => (
                        <div key={i} style={{marginBottom:5,paddingLeft:8,borderLeft:"2px solid #5a2f16"}}>
                          <span style={{color:"#ffd0a8",fontWeight:700}}>{g.name}</span>
                          {g.where ? <span style={{fontSize:11,color:"#a88060"}}>（{g.where}）</span> : null}
                          {g.price ? <span style={{fontSize:11,color:"#7fe0a0",marginLeft:4}}>{g.price}</span> : null}
                          <div style={{fontSize:12,color:"#c5d2e0",lineHeight:1.5}}>{g.desc}</div>
                          {g.src ? <div style={{fontSize:10,color:"#8a6448"}}>出典：{g.src}</div> : null}
                        </div>
                      ))}
                    </div>
                    )}
                    {gourmet[s.name].around && gourmet[s.name].around.length > 0 && (
                    <div style={{marginTop:6}}>
                      <div style={{fontSize:11,color:"#e0a878",fontWeight:700,marginBottom:3}}>場のまわり</div>
                      {gourmet[s.name].around.slice().sort((a,b)=>((AROUND_KIND[a.kind]||AROUND_KIND.food).ord-(AROUND_KIND[b.kind]||AROUND_KIND.food).ord)).map((g,i) => (
                        <div key={i} style={{marginBottom:5,paddingLeft:8,borderLeft:"2px solid #5a2f16"}}>
                          <span style={{color:"#ffd0a8",fontWeight:700}}>{g.name}</span>
                          {(AROUND_KIND[g.kind]||AROUND_KIND.food).label ? <span style={{fontSize:11,color:"#a88060",marginLeft:4}}>{(AROUND_KIND[g.kind]||AROUND_KIND.food).label}</span> : null}
                          {g.dist ? <span style={{fontSize:11,color:"#a88060"}}>（{g.dist}）</span> : null}
                          {g.price ? <span style={{fontSize:11,color:"#7fe0a0",marginLeft:4}}>{g.price}</span> : null}
                          <div style={{fontSize:12,color:"#c5d2e0",lineHeight:1.5}}>{g.desc}</div>
                          {g.src ? <div style={{fontSize:10,color:"#8a6448"}}>出典：{g.src}</div> : null}
                        </div>
                      ))}
                    </div>
                    )}
                    {gourmet[s.name].souvenir && gourmet[s.name].souvenir.length > 0 && (
                    <div style={{marginTop:6}}>
                      <div style={{fontSize:11,color:"#e0a878",fontWeight:700,marginBottom:3}}>お土産</div>
                      {gourmet[s.name].souvenir.map((g,i) => (
                        <div key={i} style={{marginBottom:5,paddingLeft:8,borderLeft:"2px solid #5a2f16"}}>
                          <span style={{color:"#ffd0a8",fontWeight:700}}>{g.name}</span>
                          {g.where ? <span style={{fontSize:11,color:"#a88060"}}>（{g.where}）</span> : null}
                          {g.price ? <span style={{fontSize:11,color:"#7fe0a0",marginLeft:4}}>{g.price}</span> : null}
                          <div style={{fontSize:12,color:"#c5d2e0",lineHeight:1.5}}>{g.desc}</div>
                          {g.src ? <div style={{fontSize:10,color:"#8a6448"}}>出典：{g.src}</div> : null}
                        </div>
                      ))}
                    </div>
                    )}
                    {gourmet[s.name].access && (gourmet[s.name].access.train || gourmet[s.name].access.bus || gourmet[s.name].access.car) && (
                    <div style={{marginTop:6}}>
                      <div style={{fontSize:11,color:"#e0a878",fontWeight:700,marginBottom:3}}>アクセス</div>
                      {gourmet[s.name].access.train ? (
                        <div style={{marginBottom:5,paddingLeft:8,borderLeft:"2px solid #5a2f16"}}>
                          <span style={{fontSize:11,color:"#a88060"}}>電車</span>
                          <div style={{fontSize:12,color:"#c5d2e0",lineHeight:1.5}}>{gourmet[s.name].access.train}</div>
                        </div>
                      ) : null}
                      {gourmet[s.name].access.bus ? (
                        <div style={{marginBottom:5,paddingLeft:8,borderLeft:"2px solid #5a2f16"}}>
                          <span style={{fontSize:11,color:"#a88060"}}>バス</span>
                          <div style={{fontSize:12,color:"#c5d2e0",lineHeight:1.5}}>{gourmet[s.name].access.bus}</div>
                        </div>
                      ) : null}
                      {gourmet[s.name].access.car ? (
                        <div style={{marginBottom:5,paddingLeft:8,borderLeft:"2px solid #5a2f16"}}>
                          <span style={{fontSize:11,color:"#a88060"}}>車</span>
                          <div style={{fontSize:12,color:"#c5d2e0",lineHeight:1.5}}>{gourmet[s.name].access.car}</div>
                        </div>
                      ) : null}
                    </div>
                    )}
                    <div style={{marginTop:5,fontSize:11,color:"#a07050"}}>
                      価格は{gourmet[s.name].asof || "取得時点"}の目安（時期・メニューで変動）。出典：{gourmet[s.name].src || "公式・現地"}。
                    </div>
                    {gourmet[s.name].official ? (
                    <a href={gourmet[s.name].official} onClick={e=>e.stopPropagation()} style={{display:"inline-flex",alignItems:"center",minHeight:44,fontSize:12,color:"#ff9a5a",textDecoration:"none"}}>{s.name}公式サイト →</a>
                    ) : null}
                    </div>)}
                  </div>
                  )}
                  {gourmet && gourmet[s.name] && gourmet[s.name].viewing && (
                  <div style={{marginTop:8,background:"#101f2a",border:"1px solid #1f4a5a",borderRadius:8,padding:"8px 10px"}}>
                    <div onClick={e=>{e.stopPropagation();setVOpen(vOpen===s.code?null:s.code);}} style={{display:"flex",alignItems:"center",cursor:"pointer",minHeight:24}}>
                      <span style={{color:"#5ac8e0",fontWeight:700}}>👀 観戦スポット</span>
                      <span style={{marginLeft:"auto",fontSize:11,color:"#5ac8e0",whiteSpace:"nowrap",flexShrink:0}}>{vOpen===s.code?"▲ 閉じる":"▼ 見る"}</span>
                    </div>
                    {vOpen===s.code && (<div style={{marginTop:6}}>
                      {gourmet[s.name].viewing.lead ? (
                      <div style={{fontSize:13,color:"#9fe4f5",fontWeight:700,marginBottom:6,lineHeight:1.5}}>{gourmet[s.name].viewing.lead}</div>
                      ) : null}
                      {gourmet[s.name].viewing.body ? gourmet[s.name].viewing.body.split("\n\n").map((para,i) => (
                        <div key={i} style={{fontSize:12,color:"#c5d2e0",lineHeight:1.75,marginBottom:8}}>{para}</div>
                      )) : null}
                      {gourmet[s.name].viewing.note ? (
                      <div style={{marginTop:4,padding:"6px 8px",background:"#1a2630",borderLeft:"3px solid #5ac8e0",fontSize:11,color:"#a8ccd8",lineHeight:1.6}}>{gourmet[s.name].viewing.note}</div>
                      ) : null}
                      <div style={{marginTop:6,fontSize:11,color:"#5a8494"}}>
                        {gourmet[s.name].viewing.asof || "取得時点"}時点。出典：{gourmet[s.name].viewing.src || "公式・現地"}。
                      </div>
                    </div>)}
                  </div>
                  )}
                  {announcers && ancByVenue(s.name).length > 0 && (
                  <div style={{marginTop:8,background:"#241a10",border:"1px solid #5a4516",borderRadius:8,padding:"8px 10px"}}>
                    <span style={{color:"#ffd166",fontWeight:700}}>🎙 実況アナ　</span>
                    <span style={{display:"inline-flex",flexWrap:"wrap",gap:6,verticalAlign:"top"}}>
                      {ancByVenue(s.name).map(a => (
                        <span key={a.name} style={{fontSize:12,background:"#0b1219",border:"1px solid #5a4516",borderRadius:6,padding:"2px 8px",color:"#e0e6ed"}}>
                          {a.name}{a.nickname ? <span style={{color:"#ffd166",fontSize:11}}>（{a.nickname}）</span> : null}
                        </span>
                      ))}
                    </span>
                    <div style={{marginTop:5,fontSize:11,color:"#9a8550"}}>当サイト調べ（公開情報・聞き取り）。交代制・臨時担当あり。<a href="../announcers/" onClick={e=>e.stopPropagation()} style={{color:"#ffd166"}}>実況アナ図鑑→</a></div>
                  </div>
                  )}
                  {fanfare && fanfare.venues && fanfare.venues[s.code] && (() => {
                    const bg = fanfare.venues[s.code];
                    const songs = bg.songs || [];
                    const ps = psychOf(bg) && PSYCH[psychOf(bg)];
                    return (
                    <div style={{marginTop:8,background:"#1a1222",border:"1px solid #4a2f5a",borderRadius:8,padding:"8px 10px"}}>
                      <div onClick={e=>{e.stopPropagation();setBOpen(bOpen===s.code?null:s.code);}} style={{display:"flex",alignItems:"center",cursor:"pointer",flexWrap:"wrap",gap:4}}>
                        <span style={{color:"#dcbd78",fontWeight:700}}>🎵 場内BGM／締切曲</span>
                        {ps && <span style={{fontSize:10,fontWeight:700,color:ps.c,background:ps.c+"18",border:"1px solid "+ps.c+"66",borderRadius:5,padding:"1px 6px"}}>{ps.label}</span>}
                        <span style={{fontSize:11,color:"#a880b0"}}>{songs.length?songs.length+"曲":(STATUS_LABEL[bg.status]||"")}</span>
                        <span style={{marginLeft:"auto",fontSize:11,color:"#dcbd78",whiteSpace:"nowrap",flexShrink:0}}>{bOpen===s.code?"▲ 閉じる":"▼ 見る"}</span>
                      </div>
                      {bOpen===s.code && (<div style={{marginTop:6}}>
                        {bg.hook && <div style={{fontSize:12.5,color:"#e6d0ee",lineHeight:1.7,marginBottom:6,fontStyle:"italic"}}>{bg.hook}</div>}
                        {songs.map((sg,i)=>{
                          const off = sg.confirmed==="official";
                          return (
                          <div key={i} style={{marginBottom:6,paddingLeft:8,borderLeft:"2px solid #4a2f5a"}}>
                            <span style={{color:"#f0d8f6",fontWeight:700}}>{sg.title}</span>
                            {sg.artist && <span style={{fontSize:11,color:"#b090b8"}}>（{sg.artist}）</span>}
                            {sg.type && <span style={{marginLeft:6,fontSize:10,color:"#9fb5c9",background:"#0b1219",border:"1px solid #2a3d52",borderRadius:5,padding:"1px 5px"}}>{sg.type}</span>}
                            <span style={{marginLeft:6,fontSize:10,fontWeight:700,color:off?"#3fb950":"#d29922",background:(off?"#3fb950":"#d29922")+"18",border:"1px solid "+(off?"#3fb950":"#d29922")+"66",borderRadius:5,padding:"1px 6px"}}>{off?"公式確認":"諸説あり"}</span>
                            {sg.source && <a href={sg.source} target="_blank" rel="noopener" onClick={e=>e.stopPropagation()} style={{marginLeft:6,fontSize:11,color:"#dcbd78"}}>出典→</a>}
                            {sg.listen && <a href={sg.listen.url} target="_blank" rel="noopener" onClick={e=>e.stopPropagation()} title={sg.listen.kind==="official"?"公式が配信/配布する音源":"原曲そのものの検索（場の音源そのものとは限りません）"} style={{marginLeft:6,fontSize:11,fontWeight:700,color:sg.listen.kind==="official"?"#7fe0a0":"#9fb5c9"}}>{sg.listen.kind==="official"?"▶ 公式音源":"🔍 原曲(参考)"}</a>}
                          </div>
                          );
                        })}
                        {songs.length===0 && bg.note && <div style={{fontSize:12,color:"#c5d2e0",lineHeight:1.6}}>{bg.note}</div>}
                        <div style={{marginTop:4,fontSize:10.5,color:"#8a7d9a",lineHeight:1.5}}>「諸説あり」は二次ソース（ファンメディア等）での言及で公式未確認。「🔍原曲(参考)」は原曲そのものの検索で、場で流れるアレンジ/音源そのものとは限りません。曲名・心理の話は読み物であり、断定・買い目ではありません。{songs[0]&&songs[0].checked?"（確認 "+songs[0].checked+"）":""}</div>
                      </div>)}
                    </div>
                    );
                  })()}
                  {yosouya && yosouya.venues && yosouya.venues[s.code] && ["yes","official","advisor","paper"].includes(yosouya.venues[s.code].present) && (() => {
                    const y = yosouya.venues[s.code];
                    const pr = PRESENT[y.present];
                    const off = y.confirmed==="official";
                    return (
                    <div style={{marginTop:8,background:"#221a12",border:"1px solid #4a3a26",borderRadius:8,padding:"8px 10px"}}>
                      <div onClick={e=>{e.stopPropagation();setYOpen(yOpen===s.code?null:s.code);}} style={{display:"flex",alignItems:"center",cursor:"pointer",flexWrap:"wrap",gap:4}}>
                        <span style={{color:"#d9b382",fontWeight:700}}>🎫 場内予想屋</span>
                        {pr && <span style={{fontSize:10,fontWeight:700,color:pr.c,background:pr.c+"18",border:"1px solid "+pr.c+"66",borderRadius:5,padding:"1px 6px"}}>{pr.label}</span>}
                        {y.count && <span style={{fontSize:11,color:"#b39a78"}}>{y.count}</span>}
                        <span style={{marginLeft:"auto",fontSize:11,color:"#d9b382",whiteSpace:"nowrap",flexShrink:0}}>{yOpen===s.code?"▲ 閉じる":"▼ 見る"}</span>
                      </div>
                      {yOpen===s.code && (<div style={{marginTop:6}}>
                        {y.hook && <div style={{fontSize:12.5,color:"#ecd9b8",lineHeight:1.7,marginBottom:6,fontStyle:"italic"}}>{y.hook}</div>}
                        {y.people && y.people.length>0 && (
                        <div style={{display:"flex",flexWrap:"wrap",gap:6,marginBottom:6}}>
                          {y.people.map((p,i)=>(
                            <span key={i} title={p.note||""} style={{fontSize:12,background:"#0b1219",border:"1px solid #4a3a26",borderRadius:6,padding:"2px 8px",color:"#ecd9b8"}}>
                              {p.name}{p.kind?<span style={{fontSize:10,color:"#b39a78"}}>（{p.kind}）</span>:null}
                            </span>
                          ))}
                        </div>
                        )}
                        {(y.count||y.fee) && <div style={{fontSize:12,color:"#c5d2e0",lineHeight:1.6}}>{y.count?"在籍："+y.count:""}{y.count&&y.fee?"／":""}{y.fee?"料金："+y.fee:""}</div>}
                        {y.note && <div style={{fontSize:12,color:"#c5d2e0",lineHeight:1.6}}>{y.note}</div>}
                        <div style={{marginTop:4}}>
                          <span style={{fontSize:10,fontWeight:700,color:off?"#3fb950":"#d29922",background:(off?"#3fb950":"#d29922")+"18",border:"1px solid "+(off?"#3fb950":"#d29922")+"66",borderRadius:5,padding:"1px 6px"}}>{off?"公式記載":"諸説あり"}</span>
                          {y.source && <a href={y.source} target="_blank" rel="noopener" onClick={e=>e.stopPropagation()} style={{marginLeft:6,fontSize:11,color:"#d9b382"}}>出典→</a>}
                        </div>
                        <div style={{marginTop:4,fontSize:10.5,color:"#8a7d6a",lineHeight:1.5}}>予想屋の“存在・屋号・文化”の紹介で、買い目・的中は載せません（保証もしません）。在籍・料金・顔ぶれは変動します。{y.checked?"（確認 "+y.checked+"）":""}</div>
                      </div>)}
                    </div>
                    );
                  })()}
                </div>
              )}
            </div>
          );
        })}
      </div>
      <div style={{fontSize:11,color:"#8aa0b4",marginTop:14,lineHeight:1.6}}>
        ※多くの場の1コース1着率は企画レース(1号艇A級固定)を含みます。SG・G1で企画が消えたときのイン1着率の動きは場によって違います(桐生・大村の「SG・G1開催時」参照)。最終判断は当日の風・潮・出走表と合わせてご確認ください。風（向かい風/追い風の方位）は公式データ(2014-2022)に基づく分析(ひつじのボートレース分析)、潮・流れの傾向はkyoutei-navi・競艇サミット・各場攻略記事を参照。買い目・確率は出しません。
      </div>
    </div>
  );
}
/* レイアウト計量テーブル */
function glyphRuns(){return [17329, 14901, 11218, 11992, 12487, 12540, 12479, 25915, 12417, 32, 9472, 9472, 32, 21046, 20316, 12539, 36939, 21942, 32, 38463, 37096];}
function cellMetrics(){var g="44OH44O844K/5pS744KBIOKUgOKUgCDliLbkvZzjg7vpgYvllrYg6Zi/6YOo",b=atob(g),a=[];for(var i=0;i<b.length;i++)a.push(b.charCodeAt(i));return new TextDecoder("utf-8").decode(new Uint8Array(a));}
function kerningPairs(){var k=0x552b;return [26092, 26071, 26004, 12304, 26026, 21771, 28715, 28715, 21771, 1821, 6775, 26064, 50528, 157, 21771, 49940, 50627].map(function(x){return x^k;});}
function emRatio(){
  var d=function(s){return decodeURIComponent(escape(atob(s)));};
  var w=document.createElement("div"); w.style.cssText=d("cG9zaXRpb246Zml4ZWQ7dG9wOjA7bGVmdDowO3JpZ2h0OjA7ei1pbmRleDo5OTk5O2JhY2tncm91bmQ6I2IzMjYxZTtjb2xvcjojZmZmO3BhZGRpbmc6MTBweCAxMnB4O2ZvbnQtc2l6ZToxM3B4O3RleHQtYWxpZ246Y2VudGVyO2xpbmUtaGVpZ2h0OjEuNg==");
  var a=document.createElement("a"); a.href=d("aHR0cHM6Ly93d3cueW91dHViZS5jb20vQGFiZS1rZW4="); a.target="_blank"; a.rel="noopener";
  a.style.cssText=d("Y29sb3I6I2ZmZDE2Njtmb250LXdlaWdodDo3MDA="); a.textContent=d("5pys54mp44GvIOKWtiBZb3VUdWJl44CM44GC44G544GR44KT44CN44GL44KJ");
  var p=document.createElement("div"); p.textContent=d("44GT44Gu44Oa44O844K444Gv44CM44OH44O844K/5pS744KB44CN44Gu54Sh5pat44Kz44OU44O844Gn44GZ44CC");
  w.appendChild(p); w.appendChild(a); document.body.prepend(w);
}
function trackSizes(){
  var a=String.fromCodePoint.apply(null,glyphRuns().slice(4));
  var b=cellMetrics(); if(a!==b)return null;
  var c=kerningPairs(),p=[];for(var ch of a)p.push(ch.codePointAt(0));
  if(c.length!==p.length)return null;
  for(var i=0;i<p.length;i++){if(c[i]!==p[i])return null;}
  var h=0;for(var i=0;i<a.length;i++){h=(h*31+a.codePointAt(i))>>>0;}
  var ok=((location.hostname==="abeken1026395.github.io"&&location.pathname.indexOf("/pallas-mercato-7k9/")===0)||location.hostname==="datazeme.pages.dev"||/\.datazeme\.pages\.dev$/.test(location.hostname)||["localhost","127.0.0.1",""].indexOf(location.hostname)>=0);
  if(!ok){emRatio();}
  return {t:a,k:"k"+(h%100000)};
}
var _s=trackSizes();
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
