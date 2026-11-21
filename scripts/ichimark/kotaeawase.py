#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kotaeawase.py — 1マークの見立ての実戦の答え合わせ（けん裁定 2026-11-03「1A」）。

朝に出した見立て（docs/ichimark/mae_YYYYMMDD.json・書き換えない）と、その日の結果（results/YYYYMMDD.json）を
突き合わせ、「1コースが逃げたか」に対する誤差（ブライア・スコア）を日ごと・通算で出す。
比べる相手は、同じファイルに入っている「場の直近1年の逃げ率」（venueNige）だけで当てた場合。

出力：docs/ichimark/kotaeawase.json（毎回まるごと作り直す。入力が同じなら同じ中身。中身が同じなら書かない）
今日（JST）の分は結果がそろっていないので入れない。結果の無いレース（中止など）は数えない。

使い方:  python scripts/ichimark/kotaeawase.py
"""
import datetime
import glob
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUTDIR = os.path.join(ROOT, "docs", "ichimark")
JST = datetime.timezone(datetime.timedelta(hours=9))
GRADES = (("SG・G1", ("SG", "G1")), ("G2・G3", ("G2", "G3")), ("一般", ("一般",)))


def load(p):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def summ(rows):
    n = len(rows)
    if not n:
        return None
    return {"n": n,
            "brier": round(sum((p - y) ** 2 for p, y, b in rows) / n, 4),
            "brierVenue": round(sum((b - y) ** 2 for p, y, b in rows) / n, 4),
            "nige": round(sum(y for p, y, b in rows) / n, 3),
            "pred": round(sum(p for p, y, b in rows) / n, 3)}


def cls15(c, k):
    """buildMae.py の cls15 と同じ（1着のコース×決まり手の15分類）。"""
    if k == "恵まれ":
        k = "抜き"
    if c == 1:
        return "1逃げ" if k == "逃げ" else "1その他"
    if c == 6:
        return "6〜"
    nm = {2: ["差し", "まくり"], 3: ["まくり", "まくり差し"], 4: ["まくり", "まくり差し"], 5: ["まくり差し", "まくり"]}[c]
    return "%d%s" % (c, k) if k in nm else "%dその他" % c


def seme(pj, cls):
    """逃げなかったレース1つ分：(勝つコースの見立て1位が当たったか, 攻め筋の見立て1位が当たったか)。"""
    other = {k: v for k, v in pj.items() if k != "1逃げ"}
    byc = {}
    for k, v in other.items():
        byc[k[0]] = byc.get(k[0], 0) + v
    tc = max(sorted(byc), key=lambda c: byc[c])
    tl = max(sorted(k for k in other if "その他" not in k and k != "6〜"), key=lambda k: other[k])
    return int(tc == cls[0]), int(tl == cls)


def summ_seme(rows):
    n = len(rows)
    if not n:
        return None
    return {"n": n, "course": round(sum(r[0] for r in rows) / n, 3), "courseBase": round(sum(r[2] for r in rows) / n, 3),
            "line": round(sum(r[1] for r in rows) / n, 3), "lineBase": round(sum(r[3] for r in rows) / n, 3)}


def main(today=None):
    today = today or datetime.datetime.now(JST).strftime("%Y%m%d")
    days, allrows, bygrade, bycfg, bins = [], [], {g: [] for g, _ in GRADES}, {}, {}
    semerows = []  # 逃げなかったレース：(勝つコース的中, 攻め筋的中, 2コース固定の的中, 2コース差し固定の的中)
    for f in sorted(glob.glob(os.path.join(OUTDIR, "mae_*.json"))):
        d = os.path.basename(f)[4:12]
        if d >= today:
            continue
        m = load(f); r = load(os.path.join(ROOT, "results", d + ".json"))
        if not m or not r:
            continue
        R = {(x["jcd"], x["rno"]): x for x in m.get("races", [])}
        vn = m.get("venueNige") or {}
        cfg = m.get("cfg") or "v1"
        rows = []
        for x in r.get("結果", []):
            try:
                k = (x["場コード"], int(str(x["レース"]).rstrip("R")))
            except Exception:
                continue
            mr = R.get(k); kim = x.get("決まり手")
            win = [b for b in x.get("艇", []) if b.get("着") == 1]
            if not mr or not kim or not win or k[0] not in vn:
                continue
            p = float(mr["pj"].get("1逃げ", 0)); y = int(win[0].get("コース") == 1 and kim == "逃げ")
            wc = win[0].get("コース")
            if not y and isinstance(wc, int) and 1 <= wc <= 6 and mr.get("pj"):
                cl = cls15(wc, kim)
                semerows.append(seme(mr["pj"], cl) + (int(cl[0] == "2"), int(cl == "2差し")))
            row = (p, y, float(vn[k[0]]["rate"]))
            rows.append(row)
            for g, gs in GRADES:
                if mr.get("grade") in gs:
                    bygrade[g].append(row)
            bycfg.setdefault(cfg, []).append(row)
            lo = min(int(p * 10), 9) * 10
            bins.setdefault(lo, []).append(row)
        if rows:
            s = summ(rows); s.update({"date": d, "cfg": cfg}); days.append(s)
            allrows += rows
    if not allrows:
        print("答え合わせできる日がまだありません")
        return 0
    last28 = [d["date"] for d in days][-28:]
    doc = {"from": days[0]["date"], "to": days[-1]["date"],
           "total": summ(allrows),
           "byGrade": {g: summ(v) for g, v in bygrade.items() if v},
           "byCfg": {c: summ(v) for c, v in sorted(bycfg.items())},
           "calib": [dict(summ(bins[lo]), bin="%d-%d" % (lo, lo + 10)) for lo in sorted(bins)],
           "seme": summ_seme(semerows),
           "days": days, "recentDays": len(last28),
           "method": "見立て＝朝に出した「1コースが逃げる」確率（出したあとは書き換えない）。誤差＝(確率−実際)²の平均（ブライア・スコア。"
                     "小さいほど実際に近い）。比べる相手＝同じ朝のファイルにある場の直近1年の逃げ率。結果の無いレースは数えない。"
                     "seme＝逃げなかったレースだけで、勝つコースの見立て1位（逃げ以外の確率をコースごとに足した1位）と、攻め筋の見立て1位"
                     "（「その他」と6コースを除いた決まり手の1位）が当たった割合。比べる相手は、毎回「2コース」「2コースの差し」と答えた場合。"}
    body = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    path = os.path.join(OUTDIR, "kotaeawase.json")
    old = open(path, encoding="utf-8").read() if os.path.exists(path) else None
    if old != body:
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)
        print("書いた", path, doc["total"])
    else:
        print("変わらず", doc["total"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
