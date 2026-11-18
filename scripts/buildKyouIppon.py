#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
buildKyouIppon.py
トップの「今日の1本」の材料を作る。

今日の開催場どうしを、当地の直近365日の実績で比べた事実を1本だけ出す。
切り口は日ごとに順番に替える（1コースの1着・万舟・進入・決まり手）。
偏りを見つけたとは言わない。1日分や1節分の数字は使わない
（直近29日の実測で、1日分の偏りは比べた数を考えると1本も残らなかった・2026-11-18）。

入力（すべて公開済み）:
  docs/data/todayTop.json   今日の開催日と開催場（場コード・場名）
  results/YYYYMMDD.json     レース結果（今日より前の直近365日分）
出力:
  docs/data/kyouIppon.json

予想・確率・買い目は入れない。率には必ず分母を付ける。
入力が欠けても落とさない。開催場が2場未満か、結果が無いときは「1本」を null にする。
中身が同じなら書かない。
"""

import datetime
import glob
import json
import os
import sys

TT = "docs/data/todayTop.json"
RES = "results"
OUT = "docs/data/kyouIppon.json"
DAYS = 365
MIN_N = 300  # 当地のレース数がこれ未満の場は比べない

# 切り口：(鍵, 見出しの言葉, 多い/少ない, 分子, 分母)
CUTS = [
    ("c1Low", "1コースの1着", "少ない", "c1", "nc"),
    ("man", "3連単の万舟（1万円以上）", "多い", "man", "np"),
    ("shift", "枠番どおりのコースに入らない艇", "多い", "sh", "nb"),
    ("makuri", "決まり手「まくり」", "多い", "k_まくり", "nk"),
    ("c1High", "1コースの1着", "多い", "c1", "nc"),
    ("sashi", "決まり手「差し」", "多い", "k_差し", "nk"),
]
BASE = datetime.date(2026, 1, 1)


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return None


def tally(files):
    V = {}
    for f in files:
        d = load(f) or {}
        for r in d.get("結果") or []:
            boats = r.get("艇") or []
            if len(boats) != 6:
                continue
            v = V.setdefault(str(r.get("場コード")), {})
            add = lambda k, x=1: v.__setitem__(k, v.get(k, 0) + x)
            w = [b for b in boats if b.get("着") == 1]
            if w and w[0].get("コース") in (1, 2, 3, 4, 5, 6):
                add("nc")
                add("c%d" % w[0]["コース"])
            cs = [b for b in boats if b.get("コース") in (1, 2, 3, 4, 5, 6) and b.get("枠") in (1, 2, 3, 4, 5, 6)]
            add("nb", len(cs))
            add("sh", sum(1 for b in cs if b["コース"] != b["枠"]))
            p = r.get("三連単配当")
            if isinstance(p, int) and p > 0:
                add("np")
                if p >= 10000:
                    add("man")
            k = r.get("決まり手")
            if k:
                add("nk")
                add("k_" + k)
    return V


def main():
    tt = load(TT)
    if not tt or not tt.get("開催日"):
        print("todayTop.json が無いため何もしない")
        return 0
    day = str(tt["開催日"])
    names = {}
    for r in tt.get("レース") or []:
        c = str(r.get("場コード") or "")
        if c and r.get("場名"):
            names[c] = r["場名"]

    files = sorted(f for f in glob.glob(os.path.join(RES, "2*.json")) if os.path.basename(f)[:8] < day)[-DAYS:]
    out = {"開催日": day, "1本": None}
    if files and len(names) >= 2:
        V = tally(files)
        frm, to = os.path.basename(files[0])[:8], os.path.basename(files[-1])[:8]
        try:
            idx = (datetime.date(int(day[:4]), int(day[4:6]), int(day[6:])) - BASE).days % len(CUTS)
        except ValueError:
            idx = 0
        key, word, way, num, den = CUTS[idx]
        rows = []
        for c, nm in names.items():
            v = V.get(c) or {}
            n = v.get(den, 0)
            if v.get("nc", 0) < MIN_N or n <= 0:
                continue
            k = v.get(num, 0)
            rows.append({"場コード": c, "場名": nm, "分子": k, "分母": n, "率": round(100.0 * k / n, 1)})
        if len(rows) >= 2:
            rows.sort(key=lambda x: (x["率"], x["分子"]), reverse=(way == "多い"))
            allk = sum((v.get(num, 0)) for v in V.values())
            alln = sum((v.get(den, 0)) for v in V.values())
            out["1本"] = {
                "切り口": key,
                "言葉": word,
                "向き": way,
                "単位": "艇" if den == "nb" else "レース",
                "期間": [frm, to],
                "日数": len(files),
                "全国": {"分子": allk, "分母": alln, "率": round(100.0 * allk / alln, 1) if alln else None},
                "場": rows,
            }

    body = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    old = None
    try:
        with open(OUT, encoding="utf-8") as f:
            old = f.read()
    except FileNotFoundError:
        pass
    if old == body:
        print("変化なし")
        return 0
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(body)
    one = out["1本"]
    print(f"書き出し: {OUT} {len(body.encode('utf-8'))}バイト 開催日={day} 切り口={one and one['切り口']} 場={one and len(one['場'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
