# -*- coding: utf-8 -*-
# buildRacerFormIndex.py
# 選手の「直近の走り」と場の「①着外率」を results/*.json（リポジトリ直下・全期間）から集計する。
#
# 用途: 見どころの並び替え指標の材料。買い目・確率・予想には使わない。
# 出力: data/racerFormIndex.json（リポジトリ直下）
#   ★docs/ 配下に置かない。build_highlights.py がサーバ側で open() して読むだけで、
#     フロントは fetch していない（値は highlights.json に焼き込まれて配られる）。
#     docs/ に置くと更新のたびに Pages デプロイが起動し、日次更新ができなくなる。
#
# 母数ガード（未達は値を null にし、分母は必ず出す）:
#   last20    直近20走の平均着        10走以上
#   c1last10  1コース直近10走の平均着  5走以上
#   avgSt     過去平均ST              20走以上
#   out1Rate  場の①着外率(%)          200レース以上
#
# 「着」は着順ではなくコードを含む（7=妨害 8=エンスト 9=転覆 10=落水 11=沈没
#  12=不完走 13=失格 14=F 15=L 16=欠場）。平均着では 7〜15 を6に丸め、
#  16（欠場）は分母から除く。生の int() で平均に入れると転覆が9着になり指標が壊れる。
import os
import json
import glob
import datetime
from collections import deque

JST = datetime.timezone(datetime.timedelta(hours=9))
DATA_DIR = "results"
OUT = os.path.join("data", "racerFormIndex.json")

LAST_N = 20
C1_N = 10
MIN_LAST = 10
MIN_C1 = 5
MIN_ST = 20
MIN_VEN = 200

SRC = "データ攻め（YouTube あべけん）"


def norm_chaku(v):
    """着コードを平均着に使える値へ。7〜15は6、16(欠場)と不正値は None。"""
    try:
        n = int(v)
    except Exception:
        return None
    if 1 <= n <= 6:
        return n
    if 7 <= n <= 15:
        return 6
    return None


def main():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.json")))
    last = {}    # 登番 -> deque(直近LAST_N着)
    c1 = {}      # 登番 -> deque(1コース直近C1_N着)
    st = {}      # 登番 -> [本数, ST合計]
    ven = {}     # 場コード -> [レース数, ①着外数]
    scanned = skipped = 0
    days = []

    for p in files:
        try:
            with open(p, "r", encoding="utf-8") as fp:
                day = json.load(fp)
        except Exception as e:
            skipped += 1
            print("  [skip] {}: {}".format(os.path.basename(p), str(e)[:50]))
            continue
        scanned += 1
        hd = str(day.get("開催日") or "").strip()
        if hd:
            days.append(hd)
        for race in day.get("結果", []) or []:
            boats = race.get("艇", []) or []
            # 場の①着外率：枠1の艇が3着以内に入らなければ①着外
            jcd = str(race.get("場コード") or "").strip()
            b1 = None
            for b in boats:
                if b.get("枠") == 1:
                    b1 = b
                    break
            if jcd and b1 is not None:
                c = norm_chaku(b1.get("着"))
                if c is not None:
                    v = ven.setdefault(jcd, [0, 0])
                    v[0] += 1
                    if c not in (1, 2, 3):
                        v[1] += 1
            for b in boats:
                toban = str(b.get("登番") or "").strip()
                if not toban:
                    continue
                c = norm_chaku(b.get("着"))
                if c is not None:
                    last.setdefault(toban, deque(maxlen=LAST_N)).append(c)
                    if str(b.get("コース")) == "1":
                        c1.setdefault(toban, deque(maxlen=C1_N)).append(c)
                s = b.get("ST")
                if s is not None:
                    try:
                        f = float(s)
                    except Exception:
                        continue
                    rec = st.setdefault(toban, [0, 0.0])
                    rec[0] += 1
                    rec[1] += f

    racers = {}
    for toban in sorted(set(list(last.keys()) + list(st.keys()))):
        L = list(last.get(toban) or [])
        C = list(c1.get(toban) or [])
        S = st.get(toban) or [0, 0.0]
        racers[toban] = {
            "last20": (round(sum(L) / len(L), 3) if len(L) >= MIN_LAST else None),
            "last20N": len(L),
            "c1last10": (round(sum(C) / len(C), 3) if len(C) >= MIN_C1 else None),
            "c1last10N": len(C),
            "avgSt": (round(S[1] / S[0], 4) if S[0] >= MIN_ST else None),
            "avgStN": S[0],
        }

    venues = {}
    for jcd in sorted(ven.keys()):
        n, o = ven[jcd]
        venues[jcd] = {
            "out1Rate": (round(o / n * 100, 2) if n >= MIN_VEN else None),
            "out1N": n,
        }

    days.sort()
    out = {
        "updated": datetime.datetime.now(JST).strftime("%Y-%m-%d"),
        "集計期間": {"最古": (days[0] if days else ""), "最新": (days[-1] if days else ""),
                 "日数": len(days)},
        "母数ガード": {"last20": MIN_LAST, "c1last10": MIN_C1,
                  "avgSt": MIN_ST, "out1Rate": MIN_VEN},
        "出典": SRC,
        "racers": racers,
        "venues": venues,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=1)

    rl = sum(1 for v in racers.values() if v["last20"] is not None)
    rc = sum(1 for v in racers.values() if v["c1last10"] is not None)
    rs = sum(1 for v in racers.values() if v["avgSt"] is not None)
    rv = sum(1 for v in venues.values() if v["out1Rate"] is not None)
    print("走査 {}ファイル / スキップ {}".format(scanned, skipped))
    print("選手数 {} / last20 {} / c1last10 {} / avgSt {}".format(
        len(racers), rl, rc, rs))
    print("場数 {} / out1Rate {}".format(len(venues), rv))
    print("保存: {}".format(OUT))


if __name__ == "__main__":
    main()
