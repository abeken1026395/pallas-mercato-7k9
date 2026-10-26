#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 実験場「部品交換のつづき」（docs/next/buhinTsuzuki.html）を作る。
# 今日の出走表のうち、同じ節で前の日までに部品を替えている選手を、場ごと・レース順に並べる。
#   入力：docs/racers/racers_today.csv（今日の出走表）と docs/data/motorKarte.json（直前情報の部品交換・展示タイム・着の記録）。読むだけ
#   出力：docs/next/buhinTsuzuki.html（実験場。noindex）
# updateBeforeinfo.yml が、部品交換の取り込みと motorKarte.json の作り直しのあとに呼ぶ（2026-10-27 けん裁定 A）。
# 同じ入力からは同じ出力になる（作成時刻ではなく motorKarte.json の updated を載せる）。
# 使い方：python3 scripts/buildBuhinTsuzuki.py
import sys, json, csv, re, datetime, html, os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
OUT = os.path.join(ROOT, 'docs', 'next', 'buhinTsuzuki.html')
karte = json.load(open(os.path.join(ROOT, 'docs', 'data', 'motorKarte.json'), encoding='utf-8'))
rows = list(csv.DictReader(open(os.path.join(ROOT, 'docs', 'racers', 'racers_today.csv'), encoding='utf-8-sig')))
if not rows or not karte.get('records'):
    sys.exit('入力が空（racers_today.csv か motorKarte.json）。ページは作り直さない')
today = rows[0]['開催日']
ymd = lambda s: datetime.date(int(s[:4]), int(s[4:6]), int(s[6:]))
T = ymd(today)
nm = lambda s: re.sub(r'[\s　]', '', s or '')
zen = str.maketrans('０１２３４５６７８９', '0123456789')
md = lambda d: '%d/%d' % (int(d[4:6]), int(d[6:]))
E = html.escape
u = karte.get('updated', '')
built = ('%d月%d日 %s' % (int(u[5:7]), int(u[8:10]), u[11:16])) if len(u) >= 16 else '不明'


def group(parts):
    p = (parts or '').translate(zen)
    if any(w in p for w in ('ピストン', 'シリンダ', 'シャフト')):
        return 3
    if any(w in p for w in ('電気', 'キャブ', 'ギヤ', 'キャリボ')):
        return 2
    if 'リング' in p:
        return 1
    return 0


# 検証11の10年分（2016-11から2026-10、延べ329万1,261艇）を、この一覧と同じ数え方（群＝それまでに替えた一番大きい部品、
# 日数＝その部品を最初に替えた日から）で数え直した、3着以内の揃えた差（100回あたり、四捨五入）。k11st13.py の PAGE
SA = {(3, 1): 6, (3, 2): 5, (3, 3): 4, (2, 1): 5, (2, 2): 4, (2, 3): 3, (1, 1): 3, (1, 2): 2, (1, 3): 1}
GN = {3: '大物', 2: '電気・キャブ・下回り', 1: 'リングだけ'}
GS = {3: '大物', 2: '電気', 1: 'リング'}
DN = {1: '翌日', 2: '3日目', 3: '4日目より後'}

# 記録の最新日は場ごとに取る（1場だけ取得が欠けても分かるように）
jcds = sorted({r['場コード'] for r in rows})
latestBy = {}
times = {}
for key, v in karte['records'].items():
    j = key.split('_')[0]
    if j not in jcds:
        continue
    for x in v:
        latestBy[j] = max(latestBy.get(j, ''), x[0])
        try:
            times.setdefault((j, x[0], int(x[1])), []).append(float(x[7]))
        except (TypeError, ValueError):
            pass
latest = max(latestBy.values())


def exRank(j, d, rno, t):
    try:
        t = float(t)
    except (TypeError, ValueError):
        return None
    return 1 + sum(1 for u in times.get((j, d, rno), []) if u < t)


DC = ['%d日目成績' % i for i in range(1, 7)]
vday, dname = {}, {}
for r in rows:
    filled = max([i + 1 for i, c in enumerate(DC) if (r.get(c) or '').strip()] or [0])
    vday[r['場コード']] = max(vday.get(r['場コード'], 1), filled + 1)
    dname[r['場コード']] = r['日目']

people = {}
for r in rows:
    j = r['場コード']
    day = vday[j]
    if day <= 1:
        continue
    start = (T - datetime.timedelta(days=day - 1)).strftime('%Y%m%d')
    key = '%s_%s' % (j, int(r['モーターNo']))
    pk = (j, r['登録番号'])
    if pk not in people:
        hist = sorted([x for x in karte['records'].get(key, []) if nm(x[3]) == nm(r['氏名']) and start <= x[0] < today], key=lambda x: (x[0], int(x[1])))
        ex = [x for x in hist if group(x[5])]
        if not ex:
            people[pk] = None
            continue
        g = max(group(x[5]) for x in ex)
        fd = min(x[0] for x in ex if group(x[5]) == g)
        k = min((T - ymd(fd)).days, 3)  # その部品を最初に替えた日を1日目として、今日が何日目か（1＝翌日、2＝3日目、3＝4日目より後）
        trail = []
        for x in hist:
            rk = exRank(j, x[0], int(x[1]), x[7])
            trail.append('<li><span class="td">%s %dR</span> %s・<b>%s</b>%s</li>' % (
                md(x[0]), int(x[1]), ('展示%d番手' % rk) if rk else '展示なし', E(str(x[8]) + ('着' if isinstance(x[8], int) else '')),
                ('<span class="px">「%s」</span>' % E(x[5])) if x[5] else ''))
        people[pk] = {'jcd': j, 'jo': r['場名'], 'name': nm(r['氏名']), 'cls': r['級別'], 'mno': r['モーターNo'],
                      'm2': r.get('モーター2連率', ''), 'g': g, 'k': k, 'trail': trail, 'races': []}
    if people[pk]:
        people[pk]['races'].append((int(re.sub(r'\D', '', r['レース'])), r['枠'], r['締切時刻']))

out = [p for p in people.values() if p]
cnt = {g: sum(1 for p in out if p['g'] == g) for g in (3, 2, 1)}


def chip(p, w):
    return ('<li class="g%d"><span class="w w%s">%s</span><span class="nm">%s</span><span class="bd b%d">%s</span>'
            '<span class="dy">%s</span><span class="sa">%d</span></li>' % (p['g'], E(w), E(w), E(p['name']), p['g'], GS[p['g']], DN[p['k']], SA[(p['g'], p['k'])]))


def card(p):
    rc = '・'.join('%dR %s号艇' % (no, E(w)) for no, w, sh in sorted(p['races']))
    m2 = ('（2連率%s%%）' % E(p['m2'])) if p['m2'] else ''
    return ('<article class="c g%d"><p class="ch"><b>%s</b> %s ／ %s ／ モーター%s号%s</p><ul class="tr">%s</ul></article>'
            % (p['g'], E(p['name']), E(p['cls']), rc, E(p['mno']), m2, ''.join(p['trail'])))


body = []
for j in jcds:
    ps = [p for p in out if p['jcd'] == j]
    if not ps:
        continue
    heavy = [p for p in ps if p['g'] >= 2]
    ring = [p for p in ps if p['g'] == 1]
    body.append('<section class="jo"><h2>%s<small>%s</small></h2>' % (E(ps[0]['jo']), E(dname[j])))
    races = {}
    for p in heavy:
        for no, w, sh in p['races']:
            races.setdefault(no, {'sh': sh, 'b': []})['b'].append((int(w), p, w))
    for no in sorted(races):
        rr = races[no]
        body.append('<div class="race"><p class="rh"><b>%dR</b><span>締切 %s</span><a href="https://www.boatrace.jp/owpc/pc/race/beforeinfo?rno=%d&amp;jcd=%s&amp;hd=%s">直前情報</a></p><ul>%s</ul></div>'
                    % (no, E(rr['sh']), no, j, today, ''.join(chip(p, w) for _, p, w in sorted(rr['b'], key=lambda t: t[0]))))
    if not heavy:
        body.append('<p class="none">大物・電気・キャブ・下回りを替えた選手はいません。</p>')
    if ring:
        rl = '、'.join('%s（%s）' % (E(p['name']), '・'.join('%dR%s号艇' % (no, E(w)) for no, w, _ in sorted(p['races']))) for p in ring)
        body.append('<p class="rg">リングだけ %d人：%s</p>' % (len(ring), rl))
    body.append('<details class="rec"><summary>この場の選手の、この節の記録（%d人）</summary>%s</details></section>' % (
        len(ps), ''.join(card(p) for p in sorted(ps, key=lambda p: (-p['g'], min(p['races']))))))
if not out:
    body.append('<p class="none">今日の出走表に、この節で前の日までに部品を替えた選手はいません。</p>')

key = ''.join('<tr><th>%s</th>%s</tr>' % (GN[g], ''.join('<td>%d</td>' % SA[(g, k)] for k in (1, 2, 3))) for g in (3, 2, 1))
lagNote = '昨日（%s）の部品交換はまだ入っていないので、今日が「翌日」の選手は載っていません。' % md((T - datetime.timedelta(days=1)).strftime('%Y%m%d')) if latest < (T - datetime.timedelta(days=1)).strftime('%Y%m%d') else ''
behind = [j for j in jcds if j in vday and (T - datetime.timedelta(days=vday[j] - 1)).strftime('%Y%m%d') <= latest and latestBy.get(j, '') < latest]

page = '''<!-- データ攻め by あべけん https://abeken1026395.github.io/pallas-mercato-7k9/ -->
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="robots" content="noindex, nofollow">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>【実験場】部品交換のつづき</title>
<style>
:root{color-scheme:dark;--bg:#0b1219;--panel:#111c27;--line:#1e2d3c;--txt:#e6edf3;--sub:#9db0c2;--dim:#7f93a6;
--g3:#e0a070;--g2:#7fb2d9;--g1:#8a9bb0;--font:-apple-system,BlinkMacSystemFont,"Hiragino Sans","Yu Gothic",sans-serif}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--txt);font-family:var(--font);font-size:16px;line-height:1.7;-webkit-text-size-adjust:100%%}
.wrap{max-width:720px;margin:0 auto;padding:10px 16px 64px}
a{color:#8fd0ff}
.crumb{font-size:13px;color:var(--sub)}
h1{font-size:23px;font-weight:800;margin:10px 0 2px}
.date{color:var(--sub);font-size:14px}
.lead{margin:12px 0;padding:12px 14px;background:var(--panel);border:1px solid var(--line);border-radius:10px;font-size:15px}
.lead p+p{margin-top:6px}
.cnt{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0 2px}
.cnt span{font-size:14px;padding:2px 10px;border-radius:99px;border:1px solid var(--line)}
.key{width:100%%;border-collapse:collapse;margin-top:10px;font-size:14px}
.key th,.key td{border-bottom:1px solid var(--line);padding:3px 6px;text-align:left;font-weight:400}
.key td{text-align:center;font-weight:700}
.key thead th{color:var(--dim);font-size:13px;text-align:center}
.key thead th:first-child{text-align:left}
.key tbody th{color:var(--sub)}
.sm{font-size:13px;color:var(--dim)}
.jo h2{font-size:19px;margin:24px 0 6px;padding-bottom:4px;border-bottom:1px solid var(--line)}
.jo h2 small{font-size:13px;color:var(--dim);font-weight:400;margin-left:8px}
.race{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:8px 12px;margin:6px 0}
.rh{display:flex;gap:10px;align-items:baseline;font-size:14px;color:var(--sub)}
.rh b{font-size:17px;color:var(--txt)}.rh a{margin-left:auto;font-size:13px}
.race ul{list-style:none;margin-top:4px}
.race li{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:3px 0}
.race .nm{font-weight:700}
.w{display:inline-block;min-width:24px;text-align:center;border-radius:4px;font-weight:800;font-size:14px;color:#000}
.w1{background:#fff}.w2{background:#111;color:#fff;outline:1px solid #888}.w3{background:#e33;color:#fff}.w4{background:#36f;color:#fff}.w5{background:#fd0}.w6{background:#2a2}
.bd{font-size:13px;font-weight:800;padding:0 8px;border-radius:6px;color:#0b1219}
.b3{background:var(--g3)}.b2{background:var(--g2)}.b1{background:var(--g1)}
.dy{font-size:14px}
.sa{font-size:13px;color:var(--sub);margin-left:auto}
.sa:before{content:"100回で"}.sa:after{content:"回少ない群"}
.rg{font-size:14px;color:var(--dim);margin:6px 2px}
details.rec{margin:6px 0 0}
details.rec summary{cursor:pointer;color:var(--sub);font-size:14px}
.c{border-left:4px solid var(--g1);padding:6px 10px;margin:8px 0;background:var(--panel);border-radius:6px}
.c.g3{border-left-color:var(--g3)}.c.g2{border-left-color:var(--g2)}
.ch{font-size:14px;color:var(--sub)}.ch b{color:var(--txt);font-size:15px}
.tr{list-style:none;font-size:14px;margin-top:2px}
.td{color:var(--dim);display:inline-block;min-width:76px}
.px{color:var(--g3);margin-left:4px}
details.how{margin-top:28px;border-top:1px solid var(--line);padding-top:12px}
details.how summary{cursor:pointer;color:var(--sub)}
details.how li{font-size:14px;color:var(--sub);margin-top:6px}
details.how ul{padding-left:1.2em}
.none{color:var(--sub);margin:10px 0;font-size:14px}
</style>
</head>
<body>
<div class="wrap">
<nav class="crumb"><a href="../">実験場の一覧</a></nav>
<h1>部品交換のつづき</h1>
<p class="date">%(date)s の出走表から ／ 部品交換の記録の更新 %(built)s</p>
<div class="lead"><p>替えた次の日から、部品交換の欄は空きます。けれど10年分では、部品を替えた艇は翌日も3日目も、同じ条件の艇より3着以内を外していました（<a href="kensho11Buhin.html">検証11</a>）。今日走る選手のうち、この節で前の日までに部品を替えている選手を、場ごと・レース順に並べました。</p>
<p>%(lag)s</p>
<div class="cnt"><span>大物 %(c3)d人</span><span>電気・キャブ・下回り %(c2)d人</span><span>（リングだけ %(c1)d人は、場ごとに1行）</span></div>
<table class="key"><thead><tr><th>3着以内が100回で何回少ない群か</th><th>翌日</th><th>3日目</th><th>4日目より後</th></tr></thead><tbody>%(key)s</tbody></table>
<p class="sm">10年分を、この一覧と同じ数え方（群は、この節でそれまでに替えた一番大きい部品）で数え直した群の平均です。記事の数字は最初に替えた部品で群を決めているので、少し違います。その選手がそうなる、という意味ではありません。</p></div>
%(body)s
<details class="how">
<summary>この一覧の作り方</summary>
<ul>
<li>今日の出走表の各選手について、同じ場・同じモーター・同じ選手の、この節の前の日までの直前情報を見ています。節の初日の選手と、今日はじめて替えた選手は入りません（今日の欄は、各レースの直前情報で見られます）</li>
<li>群は、この節でそれまでに替えた一番大きい部品で決めています。ピストン・シリンダ・シャフトのどれかなら大物、電気・キャブ・ギヤ・キャリボのどれかなら電気・キャブ・下回り、リングしかなければリングだけです。何日目かは、その部品を最初に替えた日を1日目として暦の日で数えています（節の中は毎日走る前提。順延があるとずれます）</li>
<li>選手の記録の「展示○番手」は、同じレースの展示タイムの速い順です（同じタイムは同じ順位）</li>
<li>部品交換の記録は %(latest)s までです。%(behind)s</li>
<li>出典：公式サイトの直前情報と出走表。買い目や予想ではありません</li>
</ul>
</details>
</div>
<script src="../assets/guard.js" defer></script>
</body>
</html>
''' % {'date': '%d年%d月%d日' % (T.year, T.month, T.day), 'built': built, 'c3': cnt[3], 'c2': cnt[2], 'c1': cnt[1], 'key': key,
       'body': '\n'.join(body), 'lag': lagNote or '昨日までの部品交換が入っています。',
       'latest': '%d月%d日' % (int(latest[4:6]), int(latest[6:])),
       'behind': ('記録が遅れている場：' + '、'.join(E(next(r['場名'] for r in rows if r['場コード'] == j)) for j in behind)) if behind else ''}
open(OUT, 'w', encoding='utf-8', newline='\n').write(page)
print('today', today, 'latest', latest, 'behind', behind, 'people', len(out), cnt, 'bytes', len(page.encode()))
