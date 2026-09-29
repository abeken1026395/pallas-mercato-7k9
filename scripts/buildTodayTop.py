#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
buildTodayTop.py
トップページ「今日の開催」欄の材料を、小さな公開JSONにまとめる。

入力（すべて公開済み）:
  docs/highlights/highlights.json   当日の全レース（場・レース・締切・企画名・日目・出走選手）
  docs/data/gradeSchedule.json      場ごとの区分（SG/G1/G2/G3）とレディースの印
  docs/data/racerStatsCore.json     選手の female 印（女子戦の判定に使う）
出力:
  docs/data/todayTop.json

トップは約890KBの highlights.json を読まず、このファイル（20KB前後）だけを読む。
予想・確率・判定は入れない。事実（開催・格・企画名・女子の人数）だけを入れる。
入力が欠けても落とさない。highlights.json が無いときだけ何も書かずに終わる。
"""

import json
import os
import sys

HL = "docs/highlights/highlights.json"
GS = "docs/data/gradeSchedule.json"
RS = "docs/data/racerStatsCore.json"
OUT = "docs/data/todayTop.json"
GRADES = ("SG", "PG1", "G1", "G2", "G3")


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"読めない: {path} ({e})")
        return None


def main():
    hl = load(HL)
    if not hl or not hl.get("レース"):
        print("highlights.json が無いか空のため何もしない")
        return 0
    day = str(hl.get("開催日") or "")

    gs = load(GS) or {}
    gday = (gs.get("days") or {}).get(day) or {}
    grade = {c: v.get("区分") for c, v in gday.items() if v.get("区分") in GRADES}
    lady = sorted(c for c, v in gday.items() if v.get("レディース"))

    rs = load(RS) or {}
    female = {str(p.get("no")) for p in (rs.get("players") or []) if p.get("female")}

    races = []
    for r in hl["レース"]:
        boats = r.get("艇") or []
        races.append({
            "場コード": r.get("場コード"),
            "場名": r.get("場名"),
            "レース": r.get("レース"),
            "締切時刻": r.get("締切時刻"),
            "企画名": r.get("企画名") or "",
            "日目": r.get("日目") or "",
            "女子": sum(1 for b in boats if str(b.get("登録番号")) in female),
        })

    out = {
        "開催日": day,
        "生成元": {"highlights": hl.get("生成時刻"), "gradeSchedule": gs.get("updated")},
        "格": grade,
        "レディース": lady,
        "レース": races,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    body = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    try:
        with open(OUT, encoding="utf-8") as f:
            if f.read() == body:
                print("変化なし")
                return 0
    except FileNotFoundError:
        pass
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(body)
    print(f"書き出し: {OUT} {len(body.encode('utf-8'))}バイト 開催日={day} レース={len(races)} 格={grade} レディース={lady}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
