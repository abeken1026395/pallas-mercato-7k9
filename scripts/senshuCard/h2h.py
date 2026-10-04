"""選手カード：直接対決（手合わせ）の集計。

同じレースで2人とも公式の出走に数える組ごとに [同じレースの回数, 自分が先着, 相手が先着]。
先着は2人とも着1〜6で着が小さい方。同着はどちらにも数えない。回数2以上の組だけ。
ファイル番号＝登番 % 64、キーはカードにいる選手。
"""
import collections
import json
import os


def build(rows, players, d0, d1, outDir):
    races = collections.defaultdict(list)
    allRaces = set()
    for x in rows:
        if not (d0 <= x['date'] <= d1):
            continue
        allRaces.add(x['rk'])
        if x['off']:
            races[x['rk']].append((str(x['toban']), x['chaku']))
    H = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0, 0]))
    for L in races.values():
        for i, (a, ca) in enumerate(L):
            for b, cb in L[i + 1:]:
                if a == b:
                    continue
                h, g = H[a][b], H[b][a]
                h[0] += 1
                g[0] += 1
                if 1 <= ca <= 6 and 1 <= cb <= 6 and ca != cb:
                    if ca < cb:
                        h[1] += 1
                        g[2] += 1
                    else:
                        h[2] += 1
                        g[1] += 1
    files = collections.defaultdict(dict)
    for a, m in H.items():
        if a not in players:
            continue
        sub = {b: v for b, v in m.items() if v[0] >= 2}
        if sub:
            files[int(a) % 64][a] = sub
    os.makedirs(outDir, exist_ok=True)
    for k in range(64):
        json.dump(files.get(k, {}), open(os.path.join(outDir, f"{k}.json"), "w"), ensure_ascii=False, separators=(",", ":"))
    json.dump({"from": d0, "to": d1, "races": len(allRaces)}, open(os.path.join(outDir, "meta.json"), "w"), ensure_ascii=False, separators=(",", ":"))
