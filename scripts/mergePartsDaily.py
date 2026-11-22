# -*- coding: utf-8 -*-
# mergePartsDaily.py  （GitHub Actions の updateBeforeinfo.yml で動かす）
# PC が置いた data/partsDaily/<開催日>.json を、data/motorParts.json の末尾へ取り込む。
#   - motorParts.json に既にある開催日は取り込まない（何度動いても同じ結果になる）
#   - 1日分のファイルの中身を検査し、1つでも落ちたらその日は取り込まずに知らせる（ほかの日は続ける）
#   - 既存行は1行も変えない。取り込んだ日があったときだけ updated を今の時刻にする
# 公式（boatrace.jp）には一切アクセスしない。
import os
import sys
import json
import glob
import datetime

MP = os.path.join("data", "motorParts.json")
DAILY = os.path.join("data", "partsDaily")
JST = datetime.timezone(datetime.timedelta(hours=9))
KEYS = ["jcd", "場名", "開催日", "rno", "枠", "登番", "氏名", "モーターNo", "節名",
        "部品交換", "展示タイム", "チルト", "プロペラ", "体重", "tenjiST",
        "tenjiCourse", "anteiban", "出典URL", "取得日時"]


def main():
    data = json.load(open(MP, encoding="utf-8"))
    records = data["records"]
    have = set(str(r.get("開催日")) for r in records)
    before = len(records)
    added_days = []
    bad = 0
    for p in sorted(glob.glob(os.path.join(DAILY, "*.json"))):
        hd = os.path.splitext(os.path.basename(p))[0]
        if hd in have:
            continue
        try:
            d = json.load(open(p, encoding="utf-8"))
            recs = d["records"]
            ok = (d.get("hd") == hd and recs
                  and all(r.get("開催日") == hd and list(r.keys()) == KEYS for r in recs)
                  and len(set((r["jcd"], str(r["rno"]), str(r["枠"])) for r in recs)) == len(recs))
        except (ValueError, KeyError, TypeError):
            ok = False
        if not ok:
            print("::error::{} の検査に落ちた。取り込まない".format(p))
            bad += 1
            continue
        records.extend(recs)
        have.add(hd)
        added_days.append((hd, len(recs)))
    if added_days:
        data["updated"] = datetime.datetime.now(JST).strftime("%Y-%m-%d %H:%M")
        with open(MP, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    print("取り込み: {} / {}行 → {}行".format(added_days or "なし", before, len(records)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
