"""選手カード：優勝戦の一覧（2017-01-01〜）と、優勝・優出の集計。

優勝戦の決め方（2026-10-03 PR #677 の規則）
- 公式番組の副題に「優勝」「決勝」「決定」「ファイナル」のいずれかを含み、「準」「順位」「セミ」を含まず、
  「ファイナル選抜」「初優勝ドリーム」「地区ファイナル」でないレース
- 優勝＝そのレースの着1（1人）。2025-07-14 以前は BoatraceOpenAPI の結果、以降は results（無ければ Kファイル）。着1がいない＝中止（優勝も優出も数えない）
- 優出＝番組の出走表の6人
- グレード＝番組のグレード番号（1 SG〜5 一般）。同じ日・同じ場に優勝戦が2つあり番号が1か2の開催の11R はタイトルで付け直す：
  「レディースCC」→G2、「グランプリ」→シリーズ、「クイーンズクライマックス」→「G3QCシリーズ」を含めばG3、含まなければシリーズ
- 集計の並び：[計, SG, G1, G2, G3, 一般, シリーズ]
"""
import collections
import datetime as dt
import gzip
import json
import os

KEEP = ("優勝", "決勝", "決定", "ファイナル")
DROP = ("準", "順位", "セミ")
NOT = ("ファイナル選抜", "初優勝ドリーム", "地区ファイナル")
RS_LAST = "20250714"   # これ以前の着は BoatraceOpenAPI の結果から


def isFinal(sub):
    s = sub or ""
    return any(k in s for k in KEEP) and not any(k in s for k in DROP) and not any(k in s for k in NOT)


def days(a, b):
    d0 = dt.date(int(a[:4]), int(a[4:6]), int(a[6:]))
    d1 = dt.date(int(b[:4]), int(b[4:6]), int(b[6:]))
    return [(d0 + dt.timedelta(n)).strftime("%Y%m%d") for n in range((d1 - d0).days + 1)]


def collect(rawDir, rows, last, first="20170101"):
    """優勝戦の一覧 [{d,v,r,g,t,s,fin,win}] と、番組が空の場日の数を返す。rows は officialRaces.load の行"""
    win1 = collections.defaultdict(list)   # (d, v, r) -> 着1の登番（results / K）
    for x in rows:
        if x['chaku'] == 1:
            win1[(x['date'], int(x['jo']), x['rno'])].append(str(x['toban']))
    F = []
    empty = 0
    for d in days(first, last):
        p = os.path.join(rawDir, d + ".json.gz")
        if not os.path.exists(p):
            raise SystemExit(f"番組が無い日 {d}（fetchPrograms.py で取る）")
        j = json.load(gzip.open(p))
        rs = {}
        if d <= RS_LAST:
            for v, r, bs in j.get("rs") or []:
                rs[(v, r)] = [str(t) for t, ch, co in bs if ch == 1 and t]
        byVenue = collections.defaultdict(list)
        for v, r, g, t, s, bs in j.get("pg") or []:
            byVenue[v].append((r, g, t, s, bs))
        for v, L in byVenue.items():
            if all(all(not b[1] for b in bs) for r, g, t, s, bs in L):
                empty += 1
                continue
            fins = [(r, g, t, s, bs) for r, g, t, s, bs in L if isFinal(s)]
            for r, g, t, s, bs in fins:
                gg = g
                if len(fins) == 2 and g in (1, 2) and r == 11:
                    tt = t or ""
                    if "レディースCC" in tt:
                        gg = 3
                    elif "グランプリ" in tt:
                        gg = 6
                    elif "クイーンズクライマックス" in tt:
                        gg = 4 if "G3QCシリーズ" in tt else 6
                w = rs.get((v, r), []) if d <= RS_LAST else win1.get((d, v, r), [])
                F.append({"d": d, "v": v, "r": r, "g": gg, "t": t, "s": s,
                          "fin": [str(b[1]) for b in bs if b[1]], "win": w[0] if len(w) == 1 else None})
    return F, empty


def collectAll(rawDir, rows, last, histPath):
    """履歴（data/senshuCard/finalsHistory.json）にある日はそれを使い、その後の日だけ番組から拾う。
    履歴が無ければ 2017-01-01 から番組で拾う。戻り値は collect と同じ"""
    if histPath and os.path.exists(histPath):
        H = json.load(open(histPath, encoding='utf-8'))
        F = [f for f in H["finals"] if f["d"] <= min(H["to"], last)]
        empty = H["emptyByDay"]
        e = sum(n for d, n in empty.items() if d <= last)
        if last > H["to"]:
            nxt = (dt.date(int(H["to"][:4]), int(H["to"][4:6]), int(H["to"][6:])) + dt.timedelta(1)).strftime("%Y%m%d")
            F2, e2 = collect(rawDir, rows, last, first=nxt)
            F += F2
            e += e2
        return F, e
    return collect(rawDir, rows, last)


def saveHistory(rawDir, rows, last, histPath):
    """番組から 2017-01-01〜last の優勝戦を拾い直して履歴に書く（空の場日は日ごとに数える）"""
    F, _ = collect(rawDir, rows, last)
    emptyByDay = {}
    for d in days("20170101", last):
        j = json.load(gzip.open(os.path.join(rawDir, d + ".json.gz")))
        byVenue = collections.defaultdict(list)
        for v, r, g, t, s, bs in j.get("pg") or []:
            byVenue[v].append(bs)
        n = sum(1 for L in byVenue.values() if all(all(not b[1] for b in bs) for bs in L))
        if n:
            emptyByDay[d] = n
    json.dump({"to": last, "emptyByDay": emptyByDay, "finals": F}, open(histPath, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    return F


def tally(F, d0, d1):
    """期間内の 優勝[計,SG,G1,G2,G3,一般,シリーズ]・優出 を選手ごとに"""
    yu = collections.defaultdict(lambda: [0] * 7)
    yo = collections.defaultdict(lambda: [0] * 7)
    for f in F:
        if not (d0 <= f["d"] <= d1) or not f["win"]:
            continue
        gi = f["g"] if f["g"] in (1, 2, 3, 4, 5, 6) else 5
        yu[f["win"]][0] += 1
        yu[f["win"]][gi] += 1
        for t in f["fin"]:
            yo[t][0] += 1
            yo[t][gi] += 1
    return yu, yo
