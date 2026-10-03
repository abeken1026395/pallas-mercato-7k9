"""技名サンプル用（2段）：得意技（基準を満たす）と持ち味（上位20%だが年で入れ替わりやすい）を card2D.json に書く。
tg[キー] = [率%, 回数, 分母, 上位%, 段]  段 1=得意技 2=持ち味
"""
import json, sys
import pandas as pd, numpy as np
sys.path.insert(0, '/tmp/claude-0/-home-claude/94cc7118-f7b4-5f44-94a8-f2c262b6ac1a/scratchpad/waza')
from lib import load, eb
REPO = '/home/claude/abeken1026395/pallas-mercato-7k9/'
C = json.load(open(REPO + 'docs/next/senshuCard/card2.json'))
WIN = {'y1': ('20251003', '20261002'), 'h1': ('20260404', '20261002'), 'all': ('20250715', '20261002')}
SC = {'y1': 1.0, 'h1': 0.5, 'all': 1.25}   # 最低回数の倍率（1年窓が基準）
# キー: (段, 1年窓の最低回数)
T1 = dict(nige=10, makuri=26, maezuke=8, tiltDash=10)
T2 = dict(nige=5, makuri=13, maezuke=4, tiltDash=5, sashi=14, outKeep=20, nuki=5, c4=15, p23=60)
df = load()
df['rid'] = df.date + '_' + df.jo + '_' + df.race
df['wrank'] = df.groupby('rid').waku.rank(method='first').astype(int)
ok = df.chaku.between(1, 15)
D = {
 'nige': (df.course == 1, (df.course == 1) & (df.chaku == 1) & (df.kim == '逃げ')),
 'makuri': (df.course.between(3, 6), (df.chaku == 1) & df.course.between(3, 6) & df.kim.isin(['まくり', 'まくり差し'])),
 'maezuke': (df.wrank >= 4, (df.wrank >= 4) & (df.course <= 3) & (df.wrank - df.course >= 2)),
 'sashi': (df.course.between(2, 6), (df.chaku == 1) & df.course.between(2, 6) & (df.kim == '差し')),
 'outKeep': (df.course.between(5, 6), df.course.between(5, 6) & df.chaku.between(1, 3)),
 'nuki': (ok, (df.chaku == 1) & (df.kim == '抜き')),
 'c4': (df.course == 4, (df.course == 4) & df.chaku.between(1, 3)),
 'p23': (ok, df.chaku.between(2, 3)),
 'geko': (ok & df.course.between(2, 6), ok & df.course.between(2, 6) & (df.chaku < df.course)),
 'zst': (df.st.notna() & (df.st >= 0), df.st.notna() & (df.st >= 0) & (df.st < 0.10)),
 'fut': (df.course.between(1, 6), df.course.between(1, 6) & (df.course <= df.waku)),
 'kanso': (df.chaku.between(1, 16), df.chaku.between(1, 6)),
}
for k, (o, h) in D.items():
    df[k + '_o'] = o.astype(int); df[k + '_h'] = h.astype(int)
stat = {}
for W, (a, b) in WIN.items():
    e = df[(df.date >= a) & (df.date <= b)]
    g = e.groupby('toban')
    R = {}
    for k in D:
        r = eb(g[k + '_h'].sum(), g[k + '_o'].sum()); R[k] = r
    win = C['win'][W]; pri = win.get('tagPrior', {})
    newPri = {k: pri[k] for k in ('tiltDash',) if k in pri}
    for k in D: newPri[k] = [round(float(x), 4) for x in R[k].attrs['prior']]
    win['tagPrior'] = newPri
    cnt = {}
    for t, p in C['players'].items():
        w = p['w'].get(W)
        if not w: continue
        old = w.get('tg') or {}; tg = {}
        m1 = {k: max(1, round(v * SC[W])) for k, v in T1.items()}
        m2 = {k: max(1, round(v * SC[W])) for k, v in T2.items()}
        mn = 1   # 段3は回数1以上なら出す（何もない選手を作らない）
        v = old.get('tiltDash')
        if v:
            tier = 1 if (v[1] >= m1['tiltDash'] and v[3] <= 20) else 2 if (v[1] >= m2['tiltDash'] and v[3] <= 20) else (3 if v[1] >= 1 and v[2] >= mn else 0)
            if tier: tg['tiltDash'] = v[:4] + [tier]
        for k in D:
            r = R[k]
            if int(t) not in r.index: continue
            row = r.loc[int(t)]; pct = max(1, int(round(row.pct)))
            val = [round(float(row.raw) * 100, 1), int(row.k), int(row.n), pct]
            if k in m1 and row.k >= m1[k] and pct <= 20: tg[k] = val + [1]
            elif k in m2 and row.k >= m2[k] and pct <= 20: tg[k] = val + [2]
            elif row.k >= 1 and row.n >= mn: tg[k] = val + [3]
        w['tg'] = tg
        for k, v in tg.items():
            cnt[f'{k}{v[4]}'] = cnt.get(f'{k}{v[4]}', 0) + 1
    stat[W] = cnt
C['tags'] = [
 ['nige', 'イン逃げ', '1コースで逃げて1着', T1['nige']],
 ['makuri', 'まくり一撃', '3〜6コースから、まくりかまくり差しで1着', T1['makuri']],
 ['maezuke', '前づけ', '枠の順番より2つ以上内の1〜3コースに入る', T1['maezuke']],
 ['tiltDash', 'チルトダッシュ', 'チルト+1.0度以上でダッシュ（4〜6コース）進入', T1['tiltDash']],
 ['sashi', '差し', '2〜6コースから差して1着', T2['sashi']],
 ['outKeep', '大外の粘り', '5・6コースから3着以内', T2['outKeep']],
 ['nuki', '道中の抜き', '1マークの後に抜いて1着', T2['nuki']],
 ['c4', '4コース', '4コースから3着以内', T2['c4']],
 ['p23', '2・3着の多さ', '2着か3着に入る', T2['p23']],
 ['geko', '着順上げ', '2〜6コースから、進入したコースより上の着順でゴール', 0],
 ['zst', '好スタート', 'スタートタイミング0.09以下（ゼロ台）', 0],
 ['fut', '枠を守る', '枠番より外のコースに出ずに進入', 0],
 ['kanso', '完走', '事故なく6着以内でゴール', 0],
]
json.dump(C, open(REPO + 'docs/next/senshuCard/card2D.json', 'w'), ensure_ascii=False, separators=(',', ':'))
print(json.dumps(stat, ensure_ascii=False))
for t in ['4238', '4320', '4571', '4205', '3946', '4444', '4885', '4071']:
    w = C['players'][t]['w']['y1']
    top=sorted(w['tg'].items(),key=lambda kv:(kv[1][4]==3,kv[1][3]))[:4]
    print(t, C['players'][t]['name'], [(k,v[1],v[2],v[3],v[4]) for k,v in top])
import collections
n4=collections.Counter(min(4,len((p['w'].get('y1') or {}).get('tg',{}))) for p in C['players'].values() if p['w'].get('y1'))
print('y1で技の数（最大4）ごとの人数',dict(n4))
