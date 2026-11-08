"""buildVenueRank.py — 24場番付（実験場ページ）を集計JSONから書く
使い方: python3 scripts/buildVenueRank.py <集計JSON> <出力HTML>
集計JSON は scripts/aggVenueRank10y.py（Kファイル・区切り＝年・風あり）か
scripts/aggVenueRankResults.py（results・区切り＝四半期・風なし）が書く。
最初の画面（通算・イン番付）はSVGを書き出し時に埋め込み、指標や期の切り替えの動きだけをページ側で行う。
"""
import json, sys, math, html, os

SRC, OUT = sys.argv[1], sys.argv[2]
D = json.load(open(SRC, encoding="utf-8"))
NAMES = {"01":"桐生","02":"戸田","03":"江戸川","04":"平和島","05":"多摩川","06":"浜名湖","07":"蒲郡","08":"常滑",
         "09":"津","10":"三国","11":"びわこ","12":"住之江","13":"尼崎","14":"鳴門","15":"丸亀","16":"児島",
         "17":"宮島","18":"徳山","19":"下関","20":"若松","21":"芦屋","22":"福岡","23":"唐津","24":"大村"}
VS = list(NAMES)
METRICS = [
    ("c1", "イン", "%", "1コース1着率。進入1コースの艇のうち1着になった割合。分母は本番の進入で1コースに入った艇"),
    ("c4", "4コース", "%", "4コース1着率。進入4コースの艇のうち1着になった割合。分母は本番の進入で4コースに入った艇"),
    ("man", "万舟", "%", "万舟率。3連単の払戻が1万円以上だったレースの割合。分母は3連単が成立したレース"),
    ("shin", "進入", "%", "枠なりでない進入の割合。本番の進入の並びが枠番どおりでなかったレースの割合。前づけのほか、外へ回る艇が出たレースも含む"),
    ("wind", "風", "m", "平均風速。レースごとの公式記録の風速の平均"),
    ("wave", "波", "cm", "平均波高。レースごとの公式記録の波高の平均"),
]
Z = 1.96
MINQ = 30
PER = D["区切り一覧"]
UNIT_PER = D["区切り"]


def stat(cell, kind):
    if kind == "率":
        k, n = cell
        if n == 0:
            return None
        p = k / n
        den = 1 + Z * Z / n
        c = (p + Z * Z / (2 * n)) / den
        h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / den
        return [round(100 * p, 2), round(100 * (c - h), 2), round(100 * (c + h), 2), n]
    s, n, ss = cell
    if n < 2:
        return None
    m = s / n
    sd = math.sqrt(max(ss / n - m * m, 0))
    h = Z * sd / math.sqrt(n)
    return [round(m, 3), round(m - h, 3), round(m + h, 3), n]


def per_label(p):
    if UNIT_PER == "四半期":
        q = int(p[5:])
        return f"{p[:4]}年{3 * q - 2}-{3 * q}月"
    s, e = D["期間"]
    m0 = int(s[4:6]) if p == s[:4] else 1
    m1 = int(e[4:6]) if p == e[:4] else 12
    return f"{p}年" if (m0, m1) == (1, 12) else f"{p}年{m0}-{m1}月"


# ---- 指標ごとのデータ（全期間と期ごと） ----
DATA = {}
for key, label, unit, defi in METRICS:
    m = D["指標"][key]; kind = m["型"]
    allp = {v: stat(m["場"][v], kind) for v in VS}
    perp = {}
    for p in PER:
        perp[p] = {}
        for v in VS:
            st = stat(m["区切り"][v][p], kind)
            perp[p][v] = st if st and st[3] >= MINQ else None
    if kind == "率":
        nk = [sum(m["場"][v][0] for v in VS), sum(m["場"][v][1] for v in VS)]
    else:
        nk = [sum(m["場"][v][i] for v in VS) for i in range(3)]
    nat_all = stat(nk, kind)
    nat_per = {}
    for p in PER:
        if kind == "率":
            c = [sum(m["区切り"][v][p][0] for v in VS), sum(m["区切り"][v][p][1] for v in VS)]
        else:
            c = [sum(m["区切り"][v][p][i] for v in VS) for i in range(3)]
        nat_per[p] = stat(c, kind)
    vals = [x[0] for x in allp.values() if x] + [x[0] for p in PER for x in perp[p].values() if x]
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * 0.08
    DATA[key] = {"label": label, "title": label + "番付", "unit": unit, "lo": round(lo - pad, 3), "hi": round(hi + pad, 3),
                 "all": allp, "per": perp, "natAll": nat_all, "natPer": nat_per}

# ---- 場のカルテ ----
def nat_cells(block, keys):
    out = {}
    for k in keys:
        out[k] = stat([sum(block[v][k][0] for v in VS), sum(block[v][k][1] for v in VS)], "率")
    return out


GK = ["A1", "A2", "B1", "B2"]
SK = ["冬", "夏"]
WB = D["風"]["区分"] if D.get("風") else []
gnat = nat_cells(D["級別"]["場"], GK)
snat = nat_cells(D["季節"]["場"], SK)
wnat = nat_cells(D["風"]["場"], WB) if WB else {}
cells = []
for v in VS:
    cells += [stat(D["級別"]["場"][v][g], "率") for g in GK] + [stat(D["季節"]["場"][v][s], "率") for s in SK]
    if WB:
        cells += [stat(D["風"]["場"][v][b], "率") for b in WB]
cells = [c for c in cells if c and c[3] >= 100]
MLO = math.floor(min(c[1] for c in cells) / 10) * 10
MHI = math.ceil(max(c[2] for c in cells) / 10) * 10
KARTE = {}
for v in VS:
    KARTE[v] = {
        "g": [[g, stat(D["級別"]["場"][v][g], "率"), gnat[g]] for g in GK],
        "s": [[s, stat(D["季節"]["場"][v][s], "率"), snat[s]] for s in SK],
        "w": [[b, stat(D["風"]["場"][v][b], "率"), wnat[b]] for b in WB] if WB else None,
    }


# ---- 画面 ----
W, RH, TOP = 360, 26, 30
RX, BX, NX, X0, X1, VX = 18, 24, 56, 110, 304, 356
BANZ = {1: "横綱", 2: "大関", 3: "関脇", 4: "小結"}
COLOR = {"c1": "#ecebe5", "c4": "#4a8fe0"}   # 1コースは1号艇の白、4コースは4号艇の青。ほかは白


def sx(key, x):
    d = DATA[key]
    t = (x - d["lo"]) / (d["hi"] - d["lo"])
    return X0 + max(0.0, min(1.0, t)) * (X1 - X0)


def bar(key, x, nat):
    a, b = sorted((sx(key, nat), sx(key, x)))
    return a, max(b - a, 1.5)


def rank_svg(key):
    d = DATA[key]
    rows = sorted(VS, key=lambda v: -d["all"][v][0])
    H = TOP + RH * 24 + 4
    na = d["natAll"][0]
    nx = sx(key, na)
    o = [f'<svg id="rk" viewBox="0 0 {W} {H}" role="img" aria-label="24場の順位">',
         f'<g id="nat" style="transform:translateX({nx:.1f}px)"><line class="nat" x1="0" x2="0" y1="{TOP - 4}" y2="{H}"/>'
         f'<text class="natT" x="0" y="{TOP - 10}" text-anchor="middle">全国 <tspan id="natV">{na:.1f}</tspan></text></g>',
         f'<text class="ax" id="axUnit" x="{VX}" y="{TOP - 10}" text-anchor="end">{d["unit"]}</text>']
    for i, v in enumerate(rows):
        x = d["all"][v][0]
        y = TOP + RH * i + RH / 2
        a, w = bar(key, x, na)
        cls = "up" if x >= na else "dn"
        o.append(f'<g class="row {cls}" data-v="{v}" style="transform:translateY({y:.1f}px)">')
        o.append(f'<rect class="hit" x="0" y="{-RH / 2:.1f}" width="{W}" height="{RH}"/>')
        o.append(f'<text class="rk" x="{RX}" y="5" text-anchor="end">{i + 1}</text>')
        o.append(f'<text class="bz" x="{BX}" y="5">{BANZ.get(i + 1, "")}</text>')
        o.append(f'<text class="nm" x="{NX}" y="5">{NAMES[v]}</text>')
        o.append(f'<rect class="bar" x="0" y="-6" width="1" height="12" style="transform:translateX({a:.1f}px) scaleX({w:.1f})"/>')
        o.append(f'<text class="vl" x="{VX}" y="5" text-anchor="end">{x:.1f}</text>')
        o.append('</g>')
    o.append('</svg>')
    return "\n".join(o)


def short_per(p):
    if UNIT_PER == "四半期":
        q = int(p[5:])
        return f"{p[2:4]}.{3 * q - 2}-{3 * q}"
    return f"{p[2:]}"


gp = D["級別"]["期間"]
SHORT = UNIT_PER == "四半期"
p0, p1 = D["期間"]
dateline = f"{p0[:4]}年{int(p0[4:6])}月{int(p0[6:])}日から{p1[:4]}年{int(p1[4:6])}月{int(p1[6:])}日"
DEFS = {k: d for k, _, _, d in METRICS}
tabs = "".join(f'<button class="tab" role="tab" data-k="{k}" aria-selected="{"true" if i == 0 else "false"}">{l}</button>'
               for i, (k, l, _, _) in enumerate(METRICS))
opts = "".join(f'<option value="{v}">{v}　{n}</option>' for v, n in NAMES.items())
strip = '<button class="pp" id="playBtn" aria-label="期を順に送る">▶</button>' + "".join(
    f'<button class="pb" data-i="{i}">{short_per(p)}</button>' for i, p in enumerate(PER)) + \
    f'<button class="pb on" data-i="-1">通算</button>'
payload = json.dumps({"names": NAMES, "metrics": DATA, "per": PER, "perLabel": {p: per_label(p) for p in PER},
                      "karte": KARTE, "mlo": MLO, "mhi": MHI, "defs": DEFS, "color": COLOR,
                      "geom": {"W": W, "RH": RH, "TOP": TOP, "X0": X0, "X1": X1}}, ensure_ascii=False, separators=(",", ":"))
import datetime as _dt
_days = (_dt.date(int(p1[:4]), int(p1[4:6]), int(p1[6:])) - _dt.date(int(p0[:4]), int(p0[4:6]), int(p0[6:]))).days + 1
years_txt = f"{round(_days / 365.25)}年" if _days >= 730 else f"{round(_days / 30.44)}か月"
races_txt = f"約{round(D['レース数'] / 10000)}万" if D["レース数"] >= 100000 else f"{D['レース数']:,}"
season_note = "冬は1回分（試作の期間のため）。" if SHORT else ""
tail_note = "試作は直近16か月。本番は10年で、期の送りを年ごとにし、風向き別を加える。" if SHORT else ""
wind_html = ('<p class="kt">風向きと強さ別の1コース1着率</p><svg id="kW" role="img" aria-label="風向きと強さ別の1コース1着率"></svg>'
             '<p class="cap">弱＝2m以下か無風。追い・向かいは水面の向き（2マークから1マーク）との角度。</p>') if WB else ""

page = f'''<!-- データ攻め by 阿部 https://abeken1026395.github.io/pallas-mercato-7k9/ -->
<!DOCTYPE html>
<html lang="ja">
<head>
<meta name="robots" content="noindex, nofollow">
<meta charset="UTF-8">
<meta name="author" content="阿部（データ攻め）">
<link rel="canonical" href="https://abeken1026395.github.io/pallas-mercato-7k9/next/{os.path.basename(OUT)}">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>24場番付 試作 | データ攻め</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&amp;family=Dela+Gothic+One&amp;display=swap" rel="stylesheet">
<style>
:root {{ --bg:#0d1c2f; --band:#132b46; --line:#22395a; --fg:#ecebe5; --sub:#97a8ba; --gold:#d4b06a; --dn:#3e5673; --ease:cubic-bezier(.2,.85,.25,1); }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
html {{ background:var(--bg); }}
body {{ color:var(--fg); font-family:-apple-system,"Hiragino Sans","Noto Sans JP",sans-serif; -webkit-font-smoothing:antialiased; -webkit-text-size-adjust:100%; padding-bottom:56px; }}
.wrap {{ max-width:560px; margin:0 auto; padding:6px 16px; }}
.crumb a {{ color:var(--sub); font-size:12px; display:inline-flex; align-items:center; min-height:44px; text-decoration:underline; text-underline-offset:3px; }}
h1 {{ font-family:"Dela Gothic One",-apple-system,sans-serif; font-weight:400; font-size:26px; line-height:1.3; }}
.dl {{ font-family:"Barlow Condensed","Hiragino Sans",sans-serif; font-size:13px; color:var(--sub); margin-top:2px; padding-bottom:10px; border-bottom:2px solid var(--fg); letter-spacing:.02em; }}
.sub {{ font-size:14px; margin-top:8px; line-height:1.6; }}
.sec {{ display:flex; align-items:baseline; justify-content:space-between; margin-top:26px; padding-bottom:6px; border-bottom:1px solid var(--line); }}
.sec h2 {{ font-size:14px; font-weight:700; letter-spacing:.06em; }}
.pick select {{ min-height:44px; font-size:16px; background:none; color:var(--fg); border:0; border-bottom:1px solid var(--sub); border-radius:0; padding:0 4px; -webkit-appearance:none; appearance:none; }}
.karte[hidden] {{ display:none; }}
.kh {{ display:flex; align-items:baseline; gap:10px; margin-top:14px; }}
.kh b {{ font-family:"Dela Gothic One",-apple-system,sans-serif; font-weight:400; font-size:30px; line-height:1; }}
.kh span {{ font-family:"Barlow Condensed",sans-serif; font-size:16px; color:var(--sub); }}
.kt6 {{ width:100%; border-collapse:collapse; margin-top:10px; font-size:13px; }}
.kt6 td {{ padding:7px 0; border-bottom:1px solid var(--line); }}
.kt6 td:first-child {{ color:var(--sub); }}
.kt6 .r {{ text-align:right; font-family:"Barlow Condensed",sans-serif; font-size:20px; font-weight:600; width:4.2em; }}
.kt6 .r.top {{ color:var(--gold); }}
.kt6 .v {{ text-align:right; font-family:"Barlow Condensed",sans-serif; font-size:16px; width:5em; color:var(--sub); }}
.kt {{ font-size:13px; font-weight:700; margin-top:22px; }}
.cap {{ font-size:12px; color:var(--sub); line-height:1.75; margin-top:2px; }}
.tabs {{ display:flex; flex-wrap:wrap; margin-top:4px; }}
.tab {{ position:relative; min-height:44px; padding:0; margin-right:20px; background:none; border:0; color:var(--sub); font-size:13px; cursor:pointer; }}
.tab[aria-selected="true"] {{ color:var(--fg); font-weight:700; }}
.tab::after {{ content:""; position:absolute; left:0; right:0; bottom:8px; height:2px; background:var(--fg); transform:scaleX(0); transform-origin:left; transition:transform .3s var(--ease); }}
.tab[aria-selected="true"]::after {{ transform:scaleX(1); }}
.strip {{ display:flex; overflow-x:auto; gap:0; margin-top:2px; border-top:1px solid var(--line); border-bottom:1px solid var(--line); scrollbar-width:none; }}
.strip::-webkit-scrollbar {{ display:none; }}
.pp, .pb {{ flex:none; min-width:44px; min-height:44px; padding:0 8px; background:none; border:0; color:var(--sub); font-family:"Barlow Condensed",sans-serif; font-size:16px; cursor:pointer; }}
.pp {{ color:var(--fg); border-right:1px solid var(--line); font-size:14px; }}
.pp[aria-pressed="true"] {{ color:var(--gold); }}
.pb.on {{ color:var(--bg); background:var(--fg); font-weight:600; }}
.per {{ font-family:"Barlow Condensed",sans-serif; font-size:13px; color:var(--sub); margin-top:8px; min-height:18px; }}
svg {{ display:block; width:100%; height:auto; overflow:visible; }}
.ax, .natT {{ fill:var(--sub); font-size:12px; font-family:"Barlow Condensed",sans-serif; }}
.natT tspan {{ fill:var(--fg); }}
.nat {{ stroke:var(--sub); stroke-width:1; }}
.rk {{ fill:var(--sub); font-size:14px; font-family:"Barlow Condensed",sans-serif; }}
.nm {{ fill:var(--fg); font-size:13px; }}
.bz {{ fill:var(--fg); font-size:12px; font-weight:700; }}
.vl {{ fill:var(--fg); font-size:17px; font-weight:600; font-family:"Barlow Condensed",sans-serif; }}
.bar {{ transform-box:view-box; }}
.up .bar {{ fill:var(--mc,#ecebe5); }}
.dn .bar {{ fill:var(--dn); }}
.dn .vl {{ fill:var(--sub); }}
.hit {{ fill:transparent; cursor:pointer; }}
.row, #nat, .bar, .kbar {{ transition:transform .65s var(--ease), fill .3s; }}
.row.on .bar {{ fill:var(--gold); }}
.row.on .nm, .row.on .vl, .row.on .rk, .row.on .bz {{ fill:var(--gold); }}
.row.off .bar {{ transform:translateX(0) scaleX(0) !important; }}
.vl.flip {{ animation:flip .45s var(--ease); }}
@keyframes flip {{ from {{ opacity:0; transform:translateY(6px); }} to {{ opacity:1; transform:none; }} }}
.knm {{ fill:var(--fg); font-size:13px; }}
.knat {{ stroke:var(--sub); stroke-width:1; }}
.kbar {{ transform-box:view-box; fill:var(--gold); }}
.kbar.dn {{ fill:var(--dn); }}
.kci {{ stroke:var(--sub); stroke-width:1; opacity:.6; }}
.kvl {{ fill:var(--fg); font-size:17px; font-weight:600; font-family:"Barlow Condensed",sans-serif; }}
.kdf {{ fill:var(--sub); font-size:12px; font-family:"Barlow Condensed",sans-serif; }}
.deep {{ margin-top:12px; font-size:12px; color:var(--sub); line-height:1.8; border-top:1px solid var(--line); }}
.deep summary {{ min-height:44px; display:flex; align-items:center; cursor:pointer; list-style:none; }}
.deep summary::-webkit-details-marker {{ display:none; }}
.deep summary::after {{ content:"+"; margin-left:auto; font-family:"Barlow Condensed",sans-serif; font-size:18px; }}
.deep[open] summary::after {{ content:"−"; }}
.deep p {{ margin-bottom:6px; }}
.note {{ font-size:12px; color:var(--sub); line-height:1.8; margin-top:20px; }}
@media (prefers-reduced-motion: reduce) {{ .row, #nat, .bar, .kbar, .tab::after {{ transition:none; }} .vl.flip {{ animation:none; }} }}
</style>
</head>
<body>
<div class="wrap">
<div class="crumb"><a href="./">実験場</a></div>
<h1>24場番付</h1>
<p class="sub">{years_txt}・{races_txt}レースで決めた、ボートレース場の格</p>
<p class="dl">{dateline}</p>

<div class="sec"><h2 id="secT">イン番付</h2></div>
<div class="tabs" role="tablist">{tabs}</div>
<div class="strip" id="strip">{strip}</div>
<p class="per" id="perLab"></p>
{rank_svg("c1")}
<details class="deep"><summary>数え方</summary>
<p id="defTxt">{html.escape(DEFS["c1"])}。</p>
<p>位は上から横綱・大関・関脇・小結。棒は全国の値から伸ばしています。{UNIT_PER}ごとの表示では、分母が{MINQ}未満の場は棒を消しています。目盛りは指標ごとに固定です。</p>
<p>行をタップすると、下の「場」にその場の内訳が出ます。内訳の細い横線は、たまたまの振れを見込んだ幅（95%）です。</p>
</details>

<div class="sec"><h2>場</h2><label class="pick"><select id="pick" aria-label="場を選ぶ"><option value="">場を選ぶ</option>{opts}</select></label></div>
<div class="karte" id="karte" hidden>
<p class="kh"><b id="kName"></b><span id="kCode"></span></p>
<table class="kt6" id="kTab"></table>
<p class="kt">級別で分けた1コース1着率</p>
<svg id="kG" role="img" aria-label="級別で分けた1コース1着率"></svg>
<p class="cap">縦線は全国の同じ級別。期間 {gp[0][:4]}年{int(gp[0][4:6])}月から。</p>
<p class="kt">冬と夏の1コース1着率</p>
<svg id="kS" role="img" aria-label="冬と夏の1コース1着率"></svg>
<p class="cap">冬＝12から2月、夏＝6から8月。{season_note}</p>
{wind_html}
</div>
<p class="note">公式の競走成績から数えています。欠場艇は除いています。{tail_note}</p>
</div>
<script>
(function(){{
var D={payload};
var BZ=['横綱','大関','関脇','小結'];
var G=D.geom, cur='c1', per=-1, sel='', timer=null;
var svg=document.getElementById('rk'), rows={{}};
svg.querySelectorAll('.row').forEach(function(r){{rows[r.dataset.v]=r;}});
function sx(m,x){{var t=(x-m.lo)/(m.hi-m.lo);t=Math.max(0,Math.min(1,t));return G.X0+t*(G.X1-G.X0);}}
function f1(x){{return x.toFixed(1);}}
function cell(m,v){{return per<0?m.all[v]:m.per[D.per[per]][v];}}
function draw(stagger){{
  var m=D.metrics[cur], vs=Object.keys(D.names);
  var na=(per<0?m.natAll:m.natPer[D.per[per]])[0], nx=sx(m,na);
  svg.style.setProperty('--mc',D.color[cur]||'#ecebe5');
  var ok=vs.filter(function(v){{return cell(m,v);}}).sort(function(a,b){{return cell(m,b)[0]-cell(m,a)[0];}});
  ok.concat(vs.filter(function(v){{return !cell(m,v);}})).forEach(function(v,i){{
    var r=rows[v], c=cell(m,v), y=G.TOP+G.RH*i+G.RH/2;
    r.style.transitionDelay=stagger?(i*16)+'ms':'0ms';
    r.style.transform='translateY('+y.toFixed(1)+'px)';
    r.querySelector('.rk').textContent=c?(i+1):'';
    r.querySelector('.bz').textContent=c&&i<4?BZ[i]:'';
    var vl=r.querySelector('.vl'), b=r.querySelector('.bar');
    if(c){{
      r.classList.remove('off');
      var x=sx(m,c[0]), a=Math.min(x,nx), w=Math.max(Math.abs(x-nx),1.5);
      r.classList.toggle('up',c[0]>=na);r.classList.toggle('dn',c[0]<na);
      b.style.transitionDelay=r.style.transitionDelay;
      b.style.transform='translateX('+a.toFixed(1)+'px) scaleX('+w.toFixed(1)+')';
      var t=f1(c[0]);
      if(vl.textContent!==t){{vl.textContent=t;vl.classList.remove('flip');void vl.getBBox();vl.classList.add('flip');}}
    }}else{{r.classList.add('off');vl.textContent='－';}}
  }});
  document.getElementById('nat').style.transform='translateX('+nx.toFixed(1)+'px)';
  document.getElementById('natV').textContent=f1(na);
  document.getElementById('axUnit').textContent=m.unit;
  document.getElementById('perLab').textContent=per<0?'':D.perLabel[D.per[per]];
  document.querySelectorAll('.pb').forEach(function(p){{p.classList.toggle('on',+p.dataset.i===per);}});
}}
document.querySelectorAll('.tab').forEach(function(t){{t.addEventListener('click',function(){{
  document.querySelectorAll('.tab').forEach(function(x){{x.setAttribute('aria-selected',x===t?'true':'false');}});
  cur=t.dataset.k;document.getElementById('secT').textContent=D.metrics[cur].title;document.getElementById('defTxt').textContent=D.defs[cur]+'。';draw(true);
}});}});
var pb=document.getElementById('playBtn');
function stop(){{if(timer){{clearInterval(timer);timer=null;pb.setAttribute('aria-pressed','false');pb.textContent='▶';}}}}
document.querySelectorAll('.pb').forEach(function(p){{p.addEventListener('click',function(){{stop();per=+p.dataset.i;draw(false);}});}});
pb.addEventListener('click',function(){{
  if(timer){{stop();return;}}
  pb.setAttribute('aria-pressed','true');pb.textContent='■';per=0;draw(false);
  timer=setInterval(function(){{
    if(per>=D.per.length-1){{stop();per=-1;draw(false);return;}}
    per++;draw(false);
    var on=document.querySelector('.pb.on');on&&on.scrollIntoView({{block:'nearest',inline:'center',behavior:'smooth'}});
  }},1300);
}});
var KW=360,KX0=96,KX1=262,KVX=356;
function kx(x){{var t=(x-D.mlo)/(D.mhi-D.mlo);t=Math.max(0,Math.min(1,t));return KX0+t*(KX1-KX0);}}
function mini(el,list){{
  var rh=36,H=rh*list.length+4,o=[];
  list.forEach(function(r,i){{
    var y=rh*i+rh/2, st=r[1], ns=r[2], nx=kx(ns[0]);
    o.push('<text class="knm" x="0" y="'+(y+4)+'">'+r[0]+'</text>');
    o.push('<line class="knat" x1="'+nx.toFixed(1)+'" x2="'+nx.toFixed(1)+'" y1="'+(y-11)+'" y2="'+(y+11)+'"/>');
    if(!st||st[3]<100){{o.push('<text class="kdf" x="'+KVX+'" y="'+(y+4)+'" text-anchor="end">分母不足</text>');return;}}
    var x=kx(st[0]),a=Math.min(x,nx),w=Math.max(Math.abs(x-nx),1.5),d=st[0]-ns[0];
    o.push('<line class="kci" x1="'+kx(st[1]).toFixed(1)+'" x2="'+kx(st[2]).toFixed(1)+'" y1="'+y+'" y2="'+y+'"/>');
    o.push('<g transform="translate(0,'+y+')"><rect class="kbar'+(d<0?' dn':'')+'" x="0" y="-6" width="1" height="12" data-to="translateX('+a.toFixed(1)+'px) scaleX('+w.toFixed(1)+')" style="transform:translateX('+nx.toFixed(1)+'px) scaleX(0)"/></g>');
    o.push('<text class="kvl" x="'+KVX+'" y="'+(y+1)+'" text-anchor="end">'+f1(st[0])+'</text>');
    o.push('<text class="kdf" x="'+KVX+'" y="'+(y+14)+'" text-anchor="end">'+(d>=0?'+':'−')+f1(Math.abs(d))+'・'+st[3].toLocaleString()+'艇</text>');
  }});
  el.setAttribute('viewBox','0 0 '+KW+' '+H);el.innerHTML=o.join('');
}}
function openKarte(v){{
  var k=document.getElementById('karte');
  if(!v){{k.hidden=true;return;}}
  document.getElementById('kName').textContent=D.names[v];
  document.getElementById('kCode').textContent=v;
  var tr=[];
  Object.keys(D.metrics).forEach(function(key){{
    var m=D.metrics[key], vs=Object.keys(D.names).sort(function(a,b){{return m.all[b][0]-m.all[a][0];}}), r=vs.indexOf(v)+1;
    tr.push('<tr><td>'+m.title+'</td><td class="v">'+f1(m.all[v][0])+m.unit+'</td><td class="r'+(r<=4?' top':'')+'">'+(r<=4?BZ[r-1]:r+'位')+'</td></tr>');
  }});
  document.getElementById('kTab').innerHTML=tr.join('');
  var K=D.karte[v];
  mini(document.getElementById('kG'),K.g);mini(document.getElementById('kS'),K.s);
  var kw=document.getElementById('kW');if(kw&&K.w)mini(kw,K.w);
  k.hidden=false;
  requestAnimationFrame(function(){{requestAnimationFrame(function(){{
    document.querySelectorAll('#karte [data-to]').forEach(function(e,i){{e.style.transitionDelay=(i*45)+'ms';e.style.transform=e.dataset.to;}});
  }});}});
}}
var pick=document.getElementById('pick');
function mark(v){{sel=v;Object.keys(rows).forEach(function(x){{rows[x].classList.toggle('on',!!v&&x===v);}});openKarte(v);}}
pick.addEventListener('change',function(){{mark(pick.value);}});
Object.keys(rows).forEach(function(v){{rows[v].addEventListener('click',function(){{
  var n=sel===v?'':v;pick.value=n;mark(n);
  if(n)document.getElementById('karte').scrollIntoView({{block:'start',behavior:'smooth'}});
}});}});
}})();
</script>
<script src="../assets/guard.js" defer></script>
<!-- Cloudflare Web Analytics --><script type='module' src='https://static.cloudflareinsights.com/beacon.min.js' data-cf-beacon='{{"token": "173925d64f4a495bac679b00505ea517"}}'></script><!-- End Cloudflare Web Analytics --><script src=/assets/raihou.js defer></script>
</body>
</html>
'''
open(OUT, "w", encoding="utf-8", newline="\n").write(page)
print("書き出し", OUT, len(page.encode()), "バイト")
