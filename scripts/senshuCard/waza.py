"""選手カード：技（tg）の計算。決まりは Project の claude/senshuCardLaunch.md（2026-10-04）。

tg[キー] = [率%, 回数, 分母, 上位%, 段]（段 1=得意技 2=持ち味 3=それ以外）
- 順位：ベータ二項の経験ベイズ（事前 (a,b) は最尤推定）で平均に寄せた率の高い順
- 段1：採用の基準（前半上位20%の7割以上が後半も上位20%）を満たす技（まくり・前づけ・チルトダッシュ）で、最低回数以上かつ上位20%以内
- 段2：上位20%以内で段2の最低回数以上
- 段3：回数1以上（画面では、さらに全選手平均以上・分母20以上・回数3以上のときだけ技名を出す）
- コース（co1〜co6、2026-10-05 けん裁定）：順位ではなく、その選手の中でいちばん全国平均を上回るコースを1つだけ【持ち味】にする。
  1コースは1着率、2〜6コースは3着内率。走数の少ないコースは全国平均に寄せてから差（ポイント）で比べ、差がプラスのときだけ出す。
  最低出走はそのコースで10走（半年5走・2025年7月以降12走）。逃げ・4コース・大外の粘りはこの1枠にまとめた
"""
import collections
import json
import glob
import math
import os

import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln

SC = {'y1': 1.0, 'h1': 0.5, 'all': 1.25}   # 最低回数の倍率（1年窓が基準）
T1 = dict(makuri=26, maezuke=8, tiltDash=10)   # 逃げは採用の基準に届かず段1にしない（2026-10-04）
T2 = dict(makuri=13, maezuke=4, tiltDash=5, sashi=14, nuki=5, p23=60)
KEYS = ['makuri', 'maezuke', 'sashi', 'nuki', 'p23', 'geko', 'zst', 'fut', 'kanso']
CO_MIN = 10   # コースの最低出走（1年窓。SC 倍）
TAGS = [
    ['makuri', 'まくり一撃', '3〜6コースから、まくりかまくり差しで1着', T1['makuri']],
    ['maezuke', '前づけ', '枠の順番より2つ以上内の1〜3コースに入る', T1['maezuke']],
    ['tiltDash', 'チルトダッシュ', 'チルト+1.0度以上でダッシュ（4〜6コース）進入', T1['tiltDash']],
    ['sashi', '差し', '2〜6コースから差して1着', T2['sashi']],
    ['nuki', '道中の抜き', '1マークの後に抜いて1着', T2['nuki']],
    ['p23', '2・3着の多さ', '2着か3着に入る', T2['p23']],
    ['geko', '着順上げ', '2〜6コースから、進入したコースより上の着順でゴール', 0],
    ['zst', '好スタート', 'スタートタイミング0.09以下（ゼロ台）', 0],
    ['fut', '枠を守る', '枠番より外のコースに出ずに進入', 0],
    ['kanso', '完走', '事故なく6着以内でゴール', 0],
    ['co1', '1コース', '1コースで1着', CO_MIN],
    ['co2', '2コース', '2コースから3着以内', CO_MIN],
    ['co3', '3コース', '3コースから3着以内', CO_MIN],
    ['co4', '4コース', '4コースから3着以内', CO_MIN],
    ['co5', '5コース', '5コースから3着以内', CO_MIN],
    ['co6', '6コース', '6コースから3着以内', CO_MIN],
]


def betabinFit(k, n):
    k = np.asarray(k, float)
    n = np.asarray(n, float)
    m = n > 0
    k, n = k[m], n[m]

    def nll(p):
        a, b = np.exp(p)
        return -np.sum(gammaln(n + 1) - gammaln(k + 1) - gammaln(n - k + 1) + gammaln(k + a) + gammaln(n - k + b)
                       - gammaln(n + a + b) - gammaln(a) - gammaln(b) + gammaln(a + b))
    mu = max(k.sum() / n.sum(), 1e-4)
    best = None
    for s in (3, 20, 80):
        r = minimize(nll, np.log([mu * s, (1 - mu) * s]), method='Nelder-Mead', options=dict(xatol=1e-6, fatol=1e-6, maxiter=2000))
        if best is None or r.fun < best.fun:
            best = r
    return tuple(float(x) for x in np.exp(best.x))


def ebMin(K, N):
    """K,N: {登番: 回数/分母}（分母>0）。順位は同点を最小順位で、上位% = 順位/人数*100（lib.eb と同じ）"""
    ids = [t for t in N if N[t] > 0]
    a, b = betabinFit([K.get(t, 0) for t in ids], [N[t] for t in ids])
    pm = {t: (K.get(t, 0) + a) / (N[t] + a + b) for t in ids}
    vals = sorted(pm.values(), reverse=True)
    first = {}
    for i, v in enumerate(vals):
        first.setdefault(v, i + 1)
    L = len(ids)
    return {t: first[pm[t]] / L * 100 for t in ids}, (a, b)


def ebSpec(K, N):
    """チルトダッシュ用（PR #677 の特色と同じ）：事後平均を12桁で丸めて同点判定、上位% = max(1, floor((上の人数+同点/2)/人数*100+0.5))"""
    ids = [t for t in N if N[t] > 0]
    a, b = betabinFit([K.get(t, 0) for t in ids], [N[t] for t in ids])
    pm = {t: round((K.get(t, 0) + a) / (N[t] + a + b), 12) for t in ids}
    xs = sorted(pm.values())
    import bisect
    Nn = len(xs)
    out = {}
    for t in ids:
        lo = bisect.bisect_left(xs, pm[t])
        hi = bisect.bisect_right(xs, pm[t])
        out[t] = max(1, math.floor((Nn - hi + (hi - lo) / 2) / Nn * 100 + 0.5))
    return out, (a, b)


def tiltRows(root, rows, last):
    """直前情報（preview/）のチルトを公式の出走の行に付ける。キー（日, 場, R, 枠）"""
    tilt = {}
    for f in sorted(glob.glob(os.path.join(root, 'preview', '*.json'))):
        d = os.path.basename(f)[:8]
        if last and d > last:
            continue
        for r in json.load(open(f, encoding='utf-8')).get('直前情報', []):
            for b in r.get('racers', []):
                t = b.get('tilt_adjustment')
                if t is not None and b.get('entry_number'):
                    tilt[(d, int(r['場コード']), int(str(r['レース']).replace('R', '')), int(b['entry_number']))] = t
    return tilt


def build(root, rows, wins, players, last):
    """rows：officialRaces.load の行（off 以外も含む）。wins：{窓: (from, to)}。players：card の players（tg を書き込む）"""
    # 進入した艇の中の枠順（責任外の失格艇も含める）
    byRace = collections.defaultdict(list)
    for x in rows:
        if isinstance(x['course'], int):
            byRace[x['rk']].append(x)
    for L in byRace.values():
        for i, x in enumerate(sorted(L, key=lambda y: (y['waku'] if isinstance(y['waku'], int) else 99))):
            x['wrank'] = i + 1
    tilt = tiltRows(root, rows, last)
    priors = {}
    for W, (d0, d1) in wins.items():
        K = {k: collections.Counter() for k in KEYS + ['tiltDash']}
        N = {k: collections.Counter() for k in KEYS + ['tiltDash']}
        for x in rows:
            if not (d0 <= x['date'] <= d1) or not x['off']:
                continue
            t = str(x['toban'])
            co, ch, kim, wr = x['course'], x['chaku'], x['kim'], x.get('wrank', 0)
            c = co if isinstance(co, int) else None

            def add(k, opp, hit):
                if opp:
                    N[k][t] += 1
                    if hit:
                        K[k][t] += 1
            add('makuri', c is not None and 3 <= c <= 6, ch == 1 and kim in ('まくり', 'まくり差し'))
            add('maezuke', wr >= 4, c is not None and c <= 3 and wr - c >= 2)
            add('sashi', c is not None and 2 <= c <= 6, ch == 1 and kim == '差し')
            add('nuki', True, ch == 1 and kim == '抜き')
            add('p23', True, 2 <= ch <= 3)
            add('geko', c is not None and 2 <= c <= 6, ch < c if c else False)
            st = x['st']
            add('zst', isinstance(st, (int, float)) and st >= 0, isinstance(st, (int, float)) and 0 <= st < 0.10)
            w = x['waku']
            add('fut', c is not None, c is not None and isinstance(w, int) and c <= w)
            add('kanso', True, 1 <= ch <= 6)
            tv = tilt.get((x['date'], int(x['jo']), x['rno'], w)) if isinstance(w, int) else None
            add('tiltDash', tv is not None and c is not None, tv is not None and c is not None and tv >= 1.0 and c >= 4)
        pr = {}
        res = {}
        for k in KEYS:
            pct, ab = ebMin(K[k], N[k])
            pr[k] = [round(ab[0], 4), round(ab[1], 4)]
            res[k] = pct
        tdPct, ab = ebSpec(K['tiltDash'], N['tiltDash'])
        pr['tiltDash'] = [round(ab[0], 4), round(ab[1], 4)]
        priors[W] = pr
        m1 = {k: max(1, round(v * SC[W])) for k, v in T1.items()}
        m2 = {k: max(1, round(v * SC[W])) for k, v in T2.items()}
        for t, P in players.items():
            w = P['w'].get(W)
            if not w:
                continue
            tg = {}
            # チルトダッシュ：回数5以上だけ（PR #677 の特色の最低回数のまま）
            if N['tiltDash'][t] and K['tiltDash'][t] >= 5:
                v = [round(K['tiltDash'][t] / N['tiltDash'][t] * 100, 1), K['tiltDash'][t], N['tiltDash'][t], tdPct[t]]
                tier = 1 if (v[1] >= m1['tiltDash'] and v[3] <= 20) else 2 if (v[1] >= m2['tiltDash'] and v[3] <= 20) else (3 if v[1] >= 1 and v[2] >= 1 else 0)
                if tier:
                    tg['tiltDash'] = v + [tier]
            for k in KEYS:
                if not N[k][t]:
                    continue
                kk, nn = K[k][t], N[k][t]
                pct = max(1, int(round(res[k][t])))
                val = [round(kk / nn * 100, 1), kk, nn, pct]
                if k in m1 and kk >= m1[k] and pct <= 20:
                    tg[k] = val + [1]
                elif k in m2 and kk >= m2[k] and pct <= 20:
                    tg[k] = val + [2]
                elif kk >= 1 and nn >= 1:
                    tg[k] = val + [3]
            w['tg'] = tg
    return priors


def course(out):
    """コースの持ち味（co1〜co6）を players の tg に足す。out：build 途中の card（win[窓]['base'] と players[..]['w'][窓]['co'] を使う）。
    tagPrior に入れる [全国の回数, 全国の外れ] は全国平均（全レースの合計）で、寄せの強さではない（寄せの強さはここで毎回求める）"""
    priors = {}
    for W, win in out['win'].items():
        base = win['base']
        hit = lambda r, c: r[1] if c == 0 else r[1] + r[2] + r[3]
        nat = [hit(base[c], c) / base[c][0] for c in range(6)]
        priors[W] = {f'co{c + 1}': [hit(base[c], c), base[c][0] - hit(base[c], c)] for c in range(6)}
        rows = {t: P['w'][W]['co'] for t, P in out['players'].items() if P['w'].get(W)}
        s = []
        for c in range(6):
            a, b = betabinFit([hit(r[c], c) for r in rows.values()], [r[c][0] for r in rows.values()])
            s.append(a + b)
        mn = max(1, round(CO_MIN * SC[W]))
        for t, co in rows.items():
            best = None
            for c in range(6):
                n, k = co[c][0], hit(co[c], c)
                if n < mn:
                    continue
                d = (k + s[c] * nat[c]) / (n + s[c]) - nat[c]
                if d > 1e-12 and (best is None or (d, n, -c) > best[0]):
                    best = ((d, n, -c), c, k, n)
            if best:
                _, c, k, n = best
                out['players'][t]['w'][W].setdefault('tg', {})[f'co{c + 1}'] = [round(k / n * 100, 1), k, n, 100, 2]
    return priors
