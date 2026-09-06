#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""正本 data/racerSchedule.json から配布物 docs/data/racerSchedule.json を作る。

正本は公式サイトから取った全節をそのまま持つ（920KB）。配布物は選手図鑑が
遅延読込するものなので、読者がカードで下す判断（次にどこで見られるか）に
寄与する分だけに絞る。

  ・先頭2節だけを残す（3節目以降は判断を変えない）
  ・終わった節を落とす
  ・場名は落とす（場コードから引ける）
  ・グレードと時間帯を、class 名から表示ラベルへ確定変換する

ラベルの出典
  グレード … 公式CSS main.css の .heading1.is-XXX:before が指す画像の連番
             icon_state3_1=SG / 2=G1 / 3=G2 / 4=G3 / 5=一般（a・b は色違い）
  時間帯・シリーズ … 選手ページ末尾の ul.state1 凡例の文言

未知の class が来たら停止する。黙って「一般」に丸めると誤表示が読者に出る。
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

SRC = os.path.join("data", "racerSchedule.json")
DST = os.path.join("docs", "data", "racerSchedule.json")
KEEP = 2
JST = timezone(timedelta(hours=9))

GRADE = {
    "SGa": "SG", "SGb": "SG",
    "G1a": "G1", "G1b": "G1",
    "G2a": "G2", "G2b": "G2",
    "G3a": "G3", "G3b": "G3",
    "ippan": "一般",
}
SERIES = {
    "venus": "ヴィーナスシリーズ",
    "lady": "オールレディース",
    "rookie__3rdadd": "ルーキーシリーズ",
}
TIMEBAND = {
    "morning": "モーニング",
    "summer": "サマータイム",
    "nighter": "ナイター",
    "midnight": "ミッドナイト",
}


def tokens(value):
    return [t[3:] for t in value.split() if t.startswith("is-")]


def convert(entry, unknown):
    grade = ""
    series = []
    for token in tokens(entry.get("grade", "")):
        if token in GRADE:
            grade = GRADE[token]
        elif token in SERIES:
            series.append(SERIES[token])
        else:
            unknown.add("grade:" + token)
    band = ""
    for token in tokens(entry.get("time", "")):
        if token in TIMEBAND:
            band = TIMEBAND[token]
        else:
            unknown.add("time:" + token)
    out = {"f": entry["from"], "t": entry["to"], "j": entry["jcd"], "n": entry["title"]}
    if grade:
        out["g"] = grade
    if band:
        out["h"] = band
    if series:
        out["s"] = series
    return out


def main():
    with open(SRC, encoding="utf-8") as handle:
        src = json.load(handle)
    today = datetime.now(JST).strftime("%Y%m%d")
    unknown = set()
    venues = {}
    racers = {}
    counts = {"収録": 0, "予定あり": 0, "予定なし": 0, "取得不可": 0, "落とした節": 0}

    for toban, rec in src["racers"].items():
        status = rec.get("status")
        if status == "missing":
            counts["取得不可"] += 1
            continue
        alive = [e for e in rec.get("entries", []) if e["to"] >= today]
        counts["落とした節"] += len(rec.get("entries", [])) - len(alive)
        alive.sort(key=lambda e: e["from"])
        for entry in alive:
            if entry.get("jcd") and entry.get("venue"):
                venues[str(entry["jcd"])] = entry["venue"]
        racers[toban] = [convert(e, unknown) for e in alive[:KEEP]]
        counts["収録"] += 1
        if racers[toban]:
            counts["予定あり"] += 1
        else:
            counts["予定なし"] += 1

    if unknown:
        print("未知の class があるので停止する: " + " ".join(sorted(unknown)))
        sys.exit(1)

    rows = []
    for key in sorted(racers, key=int):
        rows.append(
            '  "{}": {}'.format(
                key, json.dumps(racers[key], ensure_ascii=False, separators=(",", ":"))
            )
        )
    head = {
        "schema": "racerSchedule-2",
        "出典": src.get("出典", ""),
        "取得時刻": src.get("generated", ""),
        "生成時刻": datetime.now(JST).strftime("%Y-%m-%d %H:%M JST"),
        "掲載上限": KEEP,
        "件数": counts,
        "注記": "公式サイトの選手ページに載っている出場予定のうち、開催が終わっていない先頭2節。取得できなかった選手はキー自体を持たない。",
        "場": {k: venues[k] for k in sorted(venues, key=int)},
    }
    text = "{\n"
    for key, value in head.items():
        text += '  "{}": {},\n'.format(key, json.dumps(value, ensure_ascii=False, separators=(",", ":")))
    text += '  "racers": {\n' + ",\n".join(rows) + "\n  }\n}\n"

    tmp = DST + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    os.replace(tmp, DST)

    print("収録 {} 名（予定あり {} / 予定なし {}） 取得不可 {} 名".format(
        counts["収録"], counts["予定あり"], counts["予定なし"], counts["取得不可"]))
    print("終わった節を落とした数 {}".format(counts["落とした節"]))
    print("場 {} 件 ／ 出力 {} バイト".format(len(venues), len(text.encode("utf-8"))))


main()
