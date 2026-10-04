"""選手カード：積み上げた事実（ayumi.json）。

ayumi[登番] = {"b": [デビュー日, 養成期, 最後の昇級[日,前,後] or null, デビュー後はじめての1着の日 or null],
               窓: [いちばん多く走った場, その走数, 1着回数, 本番ST最速, その日, その場]}
- デビュー日：docs/data/rankHistory.json の最初の日（1996-07-31 以前は記録の始まりなので不明＝null）
- 養成期：docs/data/racerStats.json の yousei
- はじめての1着：デビューが2025-07-15以降の選手だけ（結果データの始まりより後なので通算の初1着と言える）
- 窓の数字は公式の出走（officialRaces）で数える。本番ST最速は ST 0以上の出走から
"""
import json
import os

JO = dict(zip([f'{i:02d}' for i in range(1, 25)],
              "桐生 戸田 江戸川 平和島 多摩川 浜名湖 蒲郡 常滑 津 三国 びわこ 住之江 尼崎 鳴門 丸亀 児島 宮島 徳山 下関 若松 芦屋 福岡 唐津 大村".split()))
ORDER = {'B2': 0, 'B1': 1, 'A2': 2, 'A1': 3}
DATA_START = '2025-07-15'


def build(root, rows, wins, players):
    RH = json.load(open(os.path.join(root, 'docs/data/rankHistory.json'), encoding='utf-8'))['選手']
    RS = {p['no']: p for p in json.load(open(os.path.join(root, 'docs/data/racerStats.json'), encoding='utf-8'))['players']}
    off = sorted((x for x in rows if x['off']), key=lambda x: x['date'])
    first = {}
    for x in off:
        if x['chaku'] == 1:
            first.setdefault(str(x['toban']), x['date'])
    A = {}
    per = {}
    for W, (d0, d1) in wins.items():
        cnt, wins1, best = {}, {}, {}
        for x in off:
            if not (d0 <= x['date'] <= d1):
                continue
            t = str(x['toban'])
            c = cnt.setdefault(t, {})
            c[x['jo']] = c.get(x['jo'], 0) + 1
            if x['chaku'] == 1:
                wins1[t] = wins1.get(t, 0) + 1
            st = x['st']
            if isinstance(st, (int, float)) and st >= 0:
                k = (st, x['date'])
                if t not in best or k < best[t][0]:
                    best[t] = (k, x['jo'])
        per[W] = (cnt, wins1, best)
    for t in players:
        rh = RH.get(t)
        deb = rh[0][0] if rh else None
        if deb and deb <= '1996-07-31':
            deb = None
        up = None
        if rh:
            for (d0, r0), (d1, r1) in zip(rh, rh[1:]):
                if ORDER.get(r1, 0) > ORDER.get(r0, 0):
                    up = [d1, r0, r1]
        fw = first.get(t) if deb and deb >= DATA_START else None
        o = {'b': [deb, RS.get(t, {}).get('yousei'), up, fw]}
        for W in wins:
            cnt, wins1, best = per[W]
            c = cnt.get(t)
            if not c:
                continue
            jo = sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[0]
            r = [JO[jo[0]], jo[1], wins1.get(t, 0)]
            if t in best:
                (st, d), j = best[t]
                r += [round(float(st), 2), d, JO[j]]
            o[W] = r
        A[t] = o
    return A
