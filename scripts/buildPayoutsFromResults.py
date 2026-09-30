# -*- coding: utf-8 -*-
"""
24場の3連単払戻CSVを results/*.json から作る（外部取得なし）

これまでは場ごとに24本のWF（update<場>Payouts.yml）が、同じ外部の成績JSONを1場ずつ取り直していた。
同じ払戻は results/*.json（updateResultsLive.yml が当日分を随時取り込む）に全式別で入っている。
2026-10-01 実測：両方にある 66,505 レースで3連単の組番・配当の食い違い 0 件。

やること:
  - 各場の既存CSV（docs/payouts/<場>Payouts.csv・列 hd, rno, combo, payout）を全行そのまま残す
  - results/*.json にあって CSV に無い (開催日, R) だけを足す（既存行は書き換えない・消さない）
  - 3連単が不成立（中止・返還など）のレースは足さない。同着で複数あるときは先頭（従来と同じ）
  - 当日の途中までのレースも、確定して払戻が入っていれば足す（各レースのあとに反映させるため）
  - 書き込みは lib.csv_guard.guarded_write_csv（行数減少・0件・列不一致なら書かずに非0終了）

終了コード: 0＝正常（足す行が無い場合も0）／3＝ガードNG（既存ファイルは無傷）
"""
import csv
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib.csv_guard import guarded_write_csv  # noqa: E402

RESULTS_GLOB = os.environ.get("PAYOUTS_RESULTS_GLOB", os.path.join("results", "2*.json"))
OUT_DIR = os.environ.get("PAYOUTS_OUT_DIR", os.path.join("docs", "payouts"))
HEADER = ["hd", "rno", "combo", "payout"]

# 場コード（2桁）→ CSV の名前。scripts/scrape<場>PayoutsApi.py の JCD と OUT から写したもの
VENUES = {
    "01": "kiryu", "02": "toda", "03": "edogawa", "04": "heiwajima", "05": "tamagawa",
    "06": "hamanako", "07": "gamagori", "08": "tokoname", "09": "tsu", "10": "mikuni",
    "11": "biwako", "12": "suminoe", "13": "amagasaki", "14": "naruto", "15": "marugame",
    "16": "kojima", "17": "miyajima", "18": "tokuyama", "19": "shimonoseki", "20": "wakamatsu",
    "21": "ashiya", "22": "fukuoka", "23": "karatsu", "24": "omura",
}


def load_results():
    """場コード → {(hd, rno文字列): (combo, payout)}。"""
    got = {c: {} for c in VENUES}
    files = sorted(glob.glob(RESULTS_GLOB))
    if not files:
        raise SystemExit("results が1件も見つからない: " + RESULTS_GLOB)
    for p in files:
        with open(p, encoding="utf-8") as f:
            doc = json.load(f)
        hd = str(doc.get("開催日") or os.path.basename(p)[:8])
        for r in doc.get("結果") or []:
            jcd = str(r.get("場コード") or "").zfill(2)
            if jcd not in got:
                continue
            tri = (r.get("払戻") or {}).get("3連単") or []
            if not tri:
                continue
            t = tri[0]
            combo, pay = t.get("組番"), t.get("配当")
            rno = str(r.get("レース") or "").rstrip("R")
            if not combo or pay is None or not rno.isdigit():
                continue
            got[jcd][(hd, str(int(rno)))] = (combo, int(pay))
    return got


def load_csv(path):
    rows, done = [], set()
    if os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as f:
            r = csv.reader(f)
            next(r, None)
            for row in r:
                if len(row) >= 4:
                    rows.append(row)
                    done.add((row[0], str(int(row[1]))))
    return rows, done


def main():
    got = load_results()
    total_new = 0
    for jcd, name in sorted(VENUES.items()):
        path = os.path.join(OUT_DIR, name + "Payouts.csv")
        rows, done = load_csv(path)
        add = [[hd, rno, combo, str(pay)] for (hd, rno), (combo, pay) in got[jcd].items() if (hd, rno) not in done]
        if not add:
            print(f"{name}: 追加なし（既存 {len(rows)} 行）")
            continue
        rows.extend(add)
        rows.sort(key=lambda x: (x[0], int(x[1])))  # 安定ソート：同じ (hd, R) の既存重複行は順序を保つ
        guarded_write_csv(path, HEADER, rows)
        total_new += len(add)
        print(f"{name}: +{len(add)} 行（計 {len(rows)} 行・最終 {rows[-1][0]}）")
    print("done. 追加合計:", total_new)


if __name__ == "__main__":
    main()
