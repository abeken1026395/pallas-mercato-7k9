"""buildVenueRank.py — 24場を数字で並べる（実験場ページ）を集計JSONから書く。図は書き出し時にSVGで埋め込む
使い方: python3 scripts/buildVenueRank.py <集計JSON> <出力HTML>
集計JSON は scripts/aggVenueRank10y.py（Kファイル・区切り＝年・風あり）か
scripts/aggVenueRankResults.py（results・区切り＝四半期・風なし）が書く
"""
import json, sys, math, html

SRC, OUT = sys.argv[1], sys.argv[2]
D = json.load(open(SRC, encoding="utf-8"))
NAMES = {"01":"桐生","02":"戸田","03":"江戸川","04":"平和島","05":"多摩川","06":"浜名湖","07":"蒲郡","08":"常滑",
         "09":"津","10":"三国","11":"びわこ","12":"住之江","13":"尼崎","14":"鳴門","15":"丸亀","16":"児島",
         "17":"宮島","18":"徳山","19":"下関","20":"若松","21":"芦屋","22":"福岡","23":"唐津","24":"大村"}
VS = list(NAMES)
METRICS = [
    ("c1", "1コース1着率", "%", "進入1コースの艇のうち1着になった割合。分母は本番の進入で1コースに入った艇"),
    ("c4", "4コース1着率", "%", "進入4コースの艇のうち1着になった割合。分母は本番の進入で4コースに入った艇"),
    ("man", "万舟率", "%", "3連単の払戻が1万円以上だったレースの割合。分母は3連単が成立したレース"),
    ("shin", "枠なりでない進入", "%", "本番の進入の並びが枠番どおりでなかったレースの割合。前づけのほか、外へ回る艇が出たレースも含む"),
    ("wind", "平均風速", "m", "レースごとの公式記録の風速の平均"),
    ("wave", "平均波高", "cm", "レースごとの公式記録の波高の平均"),
]
Z = 1.96


def stat(cell, kind):
    """値・下限・上限・分母（率は％、平均はそのまま）"""
    if kind == "率":
        k, n = cell
        if n == 0:
            return None
        p = k / n
        den = 1 + Z * Z / n
        c = (p + Z * Z / (2 * n)) / den
        h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / den
        return 100 * p, 100 * (c - h), 100 * (c + h), n
    s, n, ss = cell
    if n < 2:
        return None
    m = s / n
    sd = math.sqrt(max(ss / n - m * m, 0))
    h = Z * sd / math.sqrt(n)
    return m, m - h, m + h, n


def nat(key):
    m = D["指標"][key]
    if m["型"] == "率":
        return stat([sum(m["場"][v][0] for v in VS), sum(m["場"][v][1] for v in VS)], "率")
    return stat([sum(m["場"][v][i] for v in VS) for i in range(3)], "平均")


def f1(x, u):
    return f"{x:.1f}{u}"


# ---- 順位の表 ----
W, RH, TOP = 360, 24, 30
X0, X1, VX, S0, S1 = 62, 236, 286, 296, 354
RANKS = {}


def rank_svg(key, label, unit):
    m = D["指標"][key]; kind = m["型"]
    rows = []
    for v in VS:
        st = stat(m["場"][v], kind)
        rows.append((v,) + st)
    rows.sort(key=lambda r: -r[1])
    for i, r in enumerate(rows):
        RANKS[(key, r[0])] = (i + 1, r[1], r[4])
    lo = min(r[2] for r in rows); hi = max(r[3] for r in rows)
    pad = (hi - lo) * 0.06; lo -= pad; hi += pad
    sx = lambda x: X0 + (x - lo) / (hi - lo) * (X1 - X0)
    na = nat(key)
    qs = D["区切り一覧"]
    qv = {}
    for v in VS:
        for q in qs:
            st = stat(m["区切り"][v][q], kind)
            if st and st[3] >= 30:
                qv[(v, q)] = st[0]
    qlo, qhi = min(qv.values()), max(qv.values())
    H = TOP + RH * len(rows) + 8
    o = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{label}の24場の順位">',
         f'<text class="tk" x="{X0}" y="14">低い</text><text class="tk" x="{X1}" y="14" text-anchor="end">高い</text>',
         f'<text class="tk" x="{VX}" y="14" text-anchor="end">値</text>',
         f'<text class="tk" x="{(S0 + S1) / 2}" y="14" text-anchor="middle">{D["区切り"]}</text>']
    ax = sx(na[0])
    o.append(f'<line class="avg" x1="{ax:.1f}" x2="{ax:.1f}" y1="20" y2="{H - 6}"/>')
    o.append(f'<text class="avgt" x="{ax:.1f}" y="26" text-anchor="middle">全国 {f1(na[0], unit)}</text>')
    for i, (v, x, a, b, n) in enumerate(rows):
        y = TOP + RH * i + RH / 2 + 4
        o.append(f'<g class="row" data-v="{v}"><rect class="hit" x="0" y="{y - RH / 2 - 4:.1f}" width="{W}" height="{RH}"/>')
        o.append(f'<text class="nm" x="4" y="{y + 4:.1f}">{i + 1:>2} {NAMES[v]}</text>')
        o.append(f'<line class="trk" x1="{X0}" x2="{X1}" y1="{y:.1f}" y2="{y:.1f}"/>')
        o.append(f'<line class="ci" x1="{sx(a):.1f}" x2="{sx(b):.1f}" y1="{y:.1f}" y2="{y:.1f}"/>')
        o.append(f'<circle class="dot" cx="{sx(x):.1f}" cy="{y:.1f}" r="4.5"><title>{NAMES[v]} {f1(x, unit)}（幅 {f1(a, "")}から{f1(b, unit)}・分母 {n:,}）</title></circle>')
        o.append(f'<text class="vl" x="{VX}" y="{y + 4:.1f}" text-anchor="end">{f1(x, unit)}</text>')
        pts = []
        for j, q in enumerate(qs):
            if (v, q) in qv:
                px = S0 + j / (len(qs) - 1) * (S1 - S0)
                py = y + 7 - (qv[(v, q)] - qlo) / (qhi - qlo) * 14
                pts.append(f"{px:.1f},{py:.1f}")
        if len(pts) >= 2:
            o.append(f'<polyline class="spk" points="{" ".join(pts)}"/>')
        o.append('</g>')
    o.append('</svg>')
    return "\n".join(o), na


# ---- 場のカルテ ----
CW, CX0, CX1, CVX = 360, 60, 250, 354


def mini(rows, lo, hi, aria):
    """rows: (ラベル, この場の stat, 全国の stat)。全国は縦の目盛り、この場は点と幅"""
    rh = 30
    sx = lambda x: CX0 + (x - lo) / (hi - lo) * (CX1 - CX0)
    H = 18 + rh * len(rows)
    o = [f'<svg viewBox="0 0 {CW} {H}" role="img" aria-label="{aria}">',
         f'<text class="tk" x="{CX0}" y="12">{lo:.0f}%</text><text class="tk" x="{CX1}" y="12" text-anchor="end">{hi:.0f}%</text>']
    for i, (lab, st, ns) in enumerate(rows):
        y = 18 + rh * i + rh / 2
        o.append(f'<text class="nm" x="4" y="{y + 4:.1f}">{lab}</text>')
        o.append(f'<line class="trk" x1="{CX0}" x2="{CX1}" y1="{y:.1f}" y2="{y:.1f}"/>')
        if ns:
            o.append(f'<line class="nat" x1="{sx(ns[0]):.1f}" x2="{sx(ns[0]):.1f}" y1="{y - 8:.1f}" y2="{y + 8:.1f}"/>')
        if st is None or st[3] < 100:
            o.append(f'<text class="vs" x="{CVX}" y="{y + 4:.1f}" text-anchor="end">分母不足</text>')
            continue
        o.append(f'<line class="ci on" x1="{sx(st[1]):.1f}" x2="{sx(st[2]):.1f}" y1="{y:.1f}" y2="{y:.1f}"/>')
        o.append(f'<circle class="dot on" cx="{sx(st[0]):.1f}" cy="{y:.1f}" r="5"/>')
        d = st[0] - ns[0]
        o.append(f'<text class="vl" x="{CVX}" y="{y:.1f}" text-anchor="end">{st[0]:.1f}%</text>')
        o.append(f'<text class="vs" x="{CVX}" y="{y + 12:.1f}" text-anchor="end">全国比 {d:+.1f}・{st[3]:,}艇</text>')
    o.append('</svg>')
    return "\n".join(o)


def nat_cells(block, keys):
    return {k: stat([sum(block[v][k][0] for v in VS), sum(block[v][k][1] for v in VS)], "率") for k in keys}


GK = ["A1", "A2", "B1", "B2"]
SHORT = D["区切り"] == "四半期"
SEASON_NOTE = "この試作の期間では冬が1回分しかありません。" if SHORT else ""
TAIL_NOTE = "<br>この試作は直近16か月ぶんです。本番は10年ぶんにして、右端の線を年ごとにし、風向きと強さ別を加えます。" if SHORT else ""
gnat = nat_cells(D["級別"]["場"], GK)
snat = nat_cells(D["季節"]["場"], ["冬", "夏"])


_all = [stat(D["級別"]["場"][v][g], "率") for v in VS for g in GK] + [stat(D["季節"]["場"][v][s], "率") for v in VS for s in ("冬", "夏")]
if D.get("風"):
    _all += [stat(D["風"]["場"][v][b], "率") for v in VS for b in D["風"]["区分"]]
_all = [x for x in _all if x and x[3] >= 100]
MLO = math.floor(min(x[1] for x in _all) / 10) * 10
MHI = math.ceil(max(x[2] for x in _all) / 10) * 10


WB = D["風"]["区分"] if D.get("風") else []
wnat = nat_cells(D["風"]["場"], WB) if WB else {}


def wind_block(v):
    if not WB:
        return '<p class="wait">10年分の集計が届いたら表示します。直近16か月だけでは、向かい風5m以上のレースが場によって0件です。</p>'
    rows = [(b, stat(D["風"]["場"][v][b], "率"), wnat[b]) for b in WB]
    return mini(rows, MLO, MHI, NAMES[v] + "の風向きと強さ別の1コース1着率") + '<p class="cap">縦の線が全国の同じ風。弱は2m以下か無風。追い風・向かい風は水面の向き（2マークから1マーク）との角度で分けています。</p>'


def card(v):
    chips = []
    for key, label, unit, _ in METRICS:
        r, x, n = RANKS[(key, v)]
        chips.append(f'<li><span class="cl">{label}</span><span class="cr"><b>{r}位</b>／24・{f1(x, unit)}</span></li>')
    grows = [(g, stat(D["級別"]["場"][v][g], "率"), gnat[g]) for g in GK]
    srows = [(s, stat(D["季節"]["場"][v][s], "率"), snat[s]) for s in ("冬", "夏")]
    gp = D["級別"]["期間"]
    return f'''<div class="karte" data-v="{v}" hidden>
<h2>{NAMES[v]}のカルテ</h2>
<ul class="chips">{"".join(chips)}</ul>
<h3>1コースの1着率を、1コースの選手の級別で分ける</h3>
{mini(grows, MLO, MHI, NAMES[v] + "の級別ごとの1コース1着率")}
<p class="cap">縦の線が全国の同じ級別。級別をそろえても全国との差が残るなら、選手の顔ぶれでは説明できない差です。期間 {gp[0][:4]}年{int(gp[0][4:6])}月から（級別の記録がある日だけ）。</p>
<h3>冬と夏の1コース1着率</h3>
{mini(srows, MLO, MHI, NAMES[v] + "の冬と夏の1コース1着率")}
<p class="cap">冬は12から2月、夏は6から8月。{SEASON_NOTE}</p>
<h3>風向きと強さ別の1コース1着率</h3>
{wind_block(v)}
</div>'''


tabs, panels = [], []
for i, (key, label, unit, defi) in enumerate(METRICS):
    svg, na = rank_svg(key, label, unit)
    tabs.append(f'<button class="tab" role="tab" data-k="{key}" aria-selected="{"true" if i == 0 else "false"}">{label}</button>')
    uname = "艇" if key in ("c1", "c4") else "レース"
    panels.append(f'''<section class="panel" data-k="{key}"{"" if i == 0 else " hidden"}>
{svg}
<details class="deep"><summary>数え方と分母</summary>
<p>{html.escape(defi)}。全国の分母 {na[3]:,}{uname}。</p>
<p>点の左右の細い線は、たまたまの振れを見込んだ幅（95%）。隣の場と線が重なっていれば、順位の差は偶然の範囲かもしれません。</p>
<p>右端の線は{D["区切り"]}ごとの値で、全場同じ目盛り（分母30未満の期は描きません）。</p>
</details>
</section>''')

kartes = "\n".join(card(v) for v in VS)
opts = "".join(f'<option value="{v}">{n}</option>' for v, n in NAMES.items())
p0, p1 = D["期間"]
period = f"{p0[:4]}年{int(p0[4:6])}月{int(p0[6:])}日から{p1[:4]}年{int(p1[4:6])}月{int(p1[6:])}日"

page = f'''<!-- データ攻め by 阿部 https://abeken1026395.github.io/pallas-mercato-7k9/ -->
<!DOCTYPE html>
<html lang="ja">
<head>
<meta name="robots" content="noindex, nofollow">
<meta charset="UTF-8">
<meta name="author" content="阿部（データ攻め）">
<link rel="canonical" href="https://abeken1026395.github.io/pallas-mercato-7k9/next/venueRank.html">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>24場を数字で並べる 試作 | データ攻め</title>
<style>
:root {{ --bg:#0b1219; --card:#121c28; --line:#1f2b3a; --fg:#e0e6ed; --sub:#8a94a3; --acc:#ffd166; --dot:#6b7a8c; }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:var(--bg); color:var(--fg); font-family:'Helvetica Neue',Arial,'Hiragino Kaku Gothic ProN',Meiryo,sans-serif; -webkit-text-size-adjust:100%; padding-bottom:48px; }}
.wrap {{ max-width:560px; margin:0 auto; padding:18px 16px; }}
.crumb {{ font-size:12px; color:var(--sub); margin-bottom:10px; }}
.crumb a {{ color:var(--acc); text-decoration:none; display:inline-flex; align-items:center; min-height:44px; }}
h1 {{ font-size:22px; line-height:1.4; text-align:center; }}
.lead {{ font-size:13px; color:var(--sub); text-align:center; margin-top:6px; line-height:1.7; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:12px 10px; margin-top:16px; }}
.pick {{ font-size:13px; color:var(--sub); display:flex; align-items:center; gap:8px; }}
.pick select {{ min-height:44px; font-size:16px; background:var(--bg); color:var(--fg); border:1px solid var(--line); border-radius:8px; padding:4px 8px; }}
.hint {{ font-size:12px; color:var(--sub); margin-top:8px; line-height:1.7; }}
.karte h2 {{ font-size:17px; margin-top:12px; }}
.karte h3 {{ font-size:13px; margin-top:16px; line-height:1.5; }}
.chips {{ list-style:none; display:grid; grid-template-columns:1fr 1fr; gap:6px; margin-top:8px; }}
.chips li {{ border:1px solid var(--line); border-radius:8px; padding:6px 8px; font-size:12px; line-height:1.5; }}
.cl {{ display:block; color:var(--sub); }}
.cr {{ font-variant-numeric:tabular-nums; }}
.cr b {{ color:var(--acc); font-size:15px; }}
.cap, .wait {{ font-size:12px; color:var(--sub); line-height:1.7; margin-top:4px; }}
.wait {{ border:1px dashed var(--line); border-radius:8px; padding:10px; margin-top:8px; }}
.tabs {{ display:flex; flex-wrap:wrap; gap:6px; }}
.tab {{ min-height:44px; padding:6px 12px; border-radius:22px; border:1px solid var(--line); background:none; color:var(--sub); font-size:13px; cursor:pointer; }}
.tab[aria-selected="true"] {{ border-color:var(--fg); color:var(--fg); }}
svg {{ display:block; width:100%; height:auto; margin-top:8px; }}
.tk, .avgt, .vs {{ fill:var(--sub); font-size:11px; font-variant-numeric:tabular-nums; }}
.nm {{ fill:var(--fg); font-size:12px; font-variant-numeric:tabular-nums; white-space:pre; }}
.vl {{ fill:var(--fg); font-size:12px; font-variant-numeric:tabular-nums; }}
.trk {{ stroke:var(--line); stroke-width:1; }}
.avg {{ stroke:var(--sub); stroke-width:1; stroke-dasharray:3 3; }}
.nat {{ stroke:var(--fg); stroke-width:1.5; }}
.ci {{ stroke:var(--dot); stroke-width:2; opacity:.6; }}
.dot {{ fill:var(--dot); }}
.ci.on {{ stroke:var(--acc); opacity:.8; }}
.dot.on {{ fill:var(--acc); }}
.spk {{ fill:none; stroke:var(--dot); stroke-width:1.2; }}
.hit {{ fill:transparent; cursor:pointer; }}
.row.on .dot {{ fill:var(--acc); }}
.row.on .ci {{ stroke:var(--acc); opacity:.8; }}
.row.on .spk {{ stroke:var(--acc); stroke-width:2; }}
.row.on .nm, .row.on .vl {{ fill:var(--acc); font-weight:bold; }}
.deep {{ margin-top:8px; font-size:12px; color:var(--sub); line-height:1.8; }}
.deep summary {{ min-height:44px; display:flex; align-items:center; cursor:pointer; color:var(--fg); }}
.deep p {{ margin-top:4px; }}
.note {{ font-size:12px; color:var(--sub); line-height:1.8; margin-top:18px; }}
</style>
</head>
<body>
<div class="wrap">
<div class="crumb"><a href="./">実験場</a> ／ 24場を数字で並べる</div>
<h1>24場を数字で並べる</h1>
<p class="lead">場を選ぶとカルテが開きます。<br>下の表は指標ごとに高い順で、縦の点線が全国の値です。</p>
<div class="card">
<label class="pick">場を選ぶ <select id="pick"><option value="">選ばない</option>{opts}</select></label>
<p class="hint" id="hint">表の行をタップしても選べます。</p>
{kartes}
</div>
<div class="card">
<div class="tabs" role="tablist">{"".join(tabs)}</div>
{"".join(panels)}
</div>
<p class="note">集計 {period}・{D["レース数"]:,}レース（公式の競走成績）。欠場艇を除いて数えています。{TAIL_NOTE}</p>
</div>
<script>
(function(){{
  var tabs=document.querySelectorAll('.tab'), panels=document.querySelectorAll('.panel'), pick=document.getElementById('pick'), hint=document.getElementById('hint');
  tabs.forEach(function(t){{ t.addEventListener('click', function(){{
    tabs.forEach(function(x){{ x.setAttribute('aria-selected', x===t?'true':'false'); }});
    panels.forEach(function(p){{ p.hidden = p.dataset.k!==t.dataset.k; }});
  }}); }});
  function mark(v){{
    document.querySelectorAll('.row').forEach(function(r){{ r.classList.toggle('on', !!v && r.dataset.v===v); }});
    document.querySelectorAll('.karte').forEach(function(k){{ k.hidden = k.dataset.v!==v; }});
    hint.hidden = !!v;
  }}
  pick.addEventListener('change', function(){{ mark(pick.value); }});
  document.querySelectorAll('.row').forEach(function(r){{ r.addEventListener('click', function(){{
    var v = pick.value===r.dataset.v ? '' : r.dataset.v; pick.value=v; mark(v);
    if (v) pick.scrollIntoView({{block:'start', behavior:'smooth'}});
  }}); }});
}})();
</script>
<script src="../assets/guard.js" defer></script>
<!-- Cloudflare Web Analytics --><script type='module' src='https://static.cloudflareinsights.com/beacon.min.js' data-cf-beacon='{{"token": "173925d64f4a495bac679b00505ea517"}}'></script><!-- End Cloudflare Web Analytics --><script src=/assets/raihou.js defer></script>
</body>
</html>
'''
open(OUT, "w", encoding="utf-8", newline="\n").write(page)
print("書き出し", OUT, len(page.encode()), "バイト")
