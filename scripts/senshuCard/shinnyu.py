"""選手カード：進入実績帳（枠→本番の進入コースの回数表・場ごとの内訳・展示から本番への変化）。

すべて回数で持つ（率は表示側で計算する）。数えるのは公式の出走（rows の off）で、本番の進入コースが1〜6の走だけ。
- 枠は「進入した艇の中の枠順」（欠場があれば繰り上げる。waza.py の前づけと同じ wrank）
- wm：6×6。wm[枠順-1][コース-1]＝回数
- jo：場コード→[走数, 枠順より内のコースに入った回数]
- tk：展示の進入が記録にある走（preview/ は 2026-01-01 から）の [走数, 展示と同じ, 展示より内へ, 展示より外へ]
窓ごとの全選手の合計を common の win[窓].sn に置く（全選手の wm と tk の合計）。
"""
import collections
import glob
import json
import os


def wranks(rows):
    """rk ごとに、進入した艇（course が数）の枠順を x['wrank'] に入れる。waza.build と同じ決まり"""
    byRace = collections.defaultdict(list)
    for x in rows:
        if isinstance(x['course'], int):
            byRace[x['rk']].append(x)
    for L in byRace.values():
        for i, x in enumerate(sorted(L, key=lambda y: (y['waku'] if isinstance(y['waku'], int) else 99))):
            x['wrank'] = i + 1


def tenjiCourses(root, last):
    """preview/*.json から (日付8桁, 場コード2桁, レース番号, 枠) → 展示の進入コース。1〜6 以外は入れない"""
    out = {}
    for f in sorted(glob.glob(os.path.join(root, 'preview', '*.json'))):
        d = os.path.basename(f)[:8]
        if last and d > last:
            continue
        try:
            js = json.load(open(f, encoding='utf-8'))
        except ValueError:
            continue
        for r in js.get('直前情報') or []:
            jo = f"{int(r['stadium_number']):02d}"
            rno = int(r['race_number'])
            for b in r.get('racers') or []:
                c = b.get('course_number')
                w = b.get('entry_number')
                if isinstance(c, int) and 1 <= c <= 6 and isinstance(w, int):
                    out[(d, jo, rno, w)] = c
    return out


def empty():
    return {"wm": [[0] * 6 for _ in range(6)], "jo": {}, "tk": [0, 0, 0, 0]}


def build(root, rows, wins, players, last):
    """players（card の players）の各窓に sn を書き込み、窓ごとの全選手の合計を返す {窓: {"wm", "tk"}}"""
    wranks(rows)
    tc = tenjiCourses(root, last)
    tot = {}
    for W, (d0, d1) in wins.items():
        S = {}
        T = {"wm": [[0] * 6 for _ in range(6)], "tk": [0, 0, 0, 0]}
        for x in rows:
            if not (d0 <= x['date'] <= d1) or not x['off']:
                continue
            c, wr = x['course'], x.get('wrank')
            if not (isinstance(c, int) and 1 <= c <= 6 and isinstance(wr, int) and 1 <= wr <= 6):
                continue
            s = S.setdefault(str(x['toban']), empty())
            s["wm"][wr - 1][c - 1] += 1
            T["wm"][wr - 1][c - 1] += 1
            j = s["jo"].setdefault(x['jo'], [0, 0])
            j[0] += 1
            if c < wr:
                j[1] += 1
            tcv = tc.get((x['date'], x['jo'], x['rno'], x['waku'])) if isinstance(x['waku'], int) else None
            if tcv is not None:
                k = 1 if c == tcv else (2 if c < tcv else 3)
                for z in (s["tk"], T["tk"]):
                    z[0] += 1
                    z[k] += 1
        for no, P in players.items():
            if W in P["w"]:
                P["w"][W]["sn"] = S.get(no, empty())
        tot[W] = T
    return tot
