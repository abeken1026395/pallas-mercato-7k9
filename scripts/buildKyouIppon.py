#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
buildKyouIppon.py
トップの「今日の1本」の材料を作る（選手版・2026-11-19 けん「A」）。

今日の出走選手のうち、当地の直近365日で「2コースから6コースで1着になった割合」が高い選手を1人出す。
1コースの1着は外す（1コースで勝つのは当たり前で、枠の運が強く出るため）。
当地で2コースから6コースを20走以上した選手だけを比べる。
走った回数の少ない選手ほど率がたまたま高く出やすいので、率そのものではなく
ウィルソンの下限（95%）で並べる（少ない回数の率を割り引く）。
偏りや予想の判定ではなく、分母つきの事実として出す。

入力（すべて公開済み）:
  docs/data/todayTop.json       今日の開催日と場名
  docs/racers/entryIndex.json   今日の出走（場_R → 締切・登録番号・名前）
  results/YYYYMMDD.json         レース結果（今日より前の直近365日分）
出力:
  docs/data/kyouIppon.json

入力が欠けても落とさない。比べられる選手が2人未満なら「1本」を null にする。中身が同じなら書かない。
"""

import glob
import json
import math
import os
import sys

TT = "docs/data/todayTop.json"
ENT = "docs/racers/entryIndex.json"
RES = "results"
OUT = "docs/data/kyouIppon.json"
DAYS = 365
MIN_N = 20      # 当地の2コースから6コースの出走がこれ未満の選手は比べない
TOP = 5         # 深い層に並べる人数
Z = 1.96
JO = {"01": "桐生", "02": "戸田", "03": "江戸川", "04": "平和島", "05": "多摩川", "06": "浜名湖", "07": "蒲郡", "08": "常滑",
      "09": "津", "10": "三国", "11": "びわこ", "12": "住之江", "13": "尼崎", "14": "鳴門", "15": "丸亀", "16": "児島",
      "17": "宮島", "18": "徳山", "19": "下関", "20": "若松", "21": "芦屋", "22": "福岡", "23": "唐津", "24": "大村"}


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return None


def wilson(k, n):
    if n <= 0:
        return 0.0
    p = k / n
    d = 1 + Z * Z / n
    c = p + Z * Z / (2 * n)
    r = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n))
    return (c - r) / d


def tally(files):
    S = {}
    for f in files:
        d = load(f) or {}
        for r in d.get("結果") or []:
            jj = str(r.get("場コード") or "")
            for b in r.get("艇") or []:
                t = b.get("登番")
                if not isinstance(t, int):
                    continue
                s = S.setdefault((jj, t), [0, 0, 0, 0])  # 全体の出走・1着・2から6コースの出走・1着
                s[0] += 1
                w = b.get("着") == 1
                s[1] += 1 if w else 0
                if b.get("コース") in (2, 3, 4, 5, 6):
                    s[2] += 1
                    s[3] += 1 if w else 0
    return S


def main():
    tt = load(TT) or {}
    day = str(tt.get("開催日") or "")
    ent = load(ENT) or {}
    races = ((ent.get("days") or {}).get(day)) if day else None
    out = {"開催日": day, "1本": None}
    if day and isinstance(races, dict) and races:
        names = dict(JO)
        for r in tt.get("レース") or []:
            c = str(r.get("場コード") or "")
            if c and r.get("場名"):
                names[c] = r["場名"]
        files = sorted(f for f in glob.glob(os.path.join(RES, "2*.json")) if os.path.basename(f)[:8] < day)[-DAYS:]
        S = tally(files) if files else {}
        cand = {}
        for key, v in races.items():
            if not isinstance(v, list) or len(v) < 4:
                continue
            jj, _, rn = str(key).partition("_")
            if jj not in JO or not rn.isdigit():
                continue
            tms, tbs, nms = v[0], v[1], v[3]
            for i, t in enumerate(tbs if isinstance(tbs, list) else []):
                try:
                    t = int(t)
                except (TypeError, ValueError):
                    continue
                s = S.get((jj, t))
                if not s or s[2] < MIN_N:
                    continue
                nm = str(nms[i] if isinstance(nms, list) and i < len(nms) else "").replace("　", "").replace(" ", "")[:12]
                row = {"登番": t, "氏名": nm, "場コード": jj, "場名": names.get(jj, jj), "分子": s[3], "分母": s[2],
                       "率": round(100.0 * s[3] / s[2], 1), "全体分子": s[1], "全体分母": s[0],
                       "R": int(rn), "締切": str(tms or ""), "_w": wilson(s[3], s[2])}
                old = cand.get((jj, t))
                if not old or row["締切"] < old["締切"]:
                    cand[(jj, t)] = row  # 同じ日に2回乗るなら早いレースを出す
        rows = sorted(cand.values(), key=lambda x: (-x["_w"], -x["分子"], x["登番"]))
        if len(rows) >= 2:
            for x in rows:
                x.pop("_w", None)
            frm, to = os.path.basename(files[0])[:8], os.path.basename(files[-1])[:8]
            ak = sum(s[3] for s in S.values()); an = sum(s[2] for s in S.values())
            base = {"分子": ak, "分母": an, "率": round(100.0 * ak / an, 1) if an else None}
            out["1本"] = {"種類": "senshu", "期間": [frm, to], "日数": len(files), "比べた人数": len(rows), "全選手": base, "選手": rows[:TOP]}

    body = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    try:
        with open(OUT, encoding="utf-8") as f:
            if f.read() == body:
                print("変化なし")
                return 0
    except FileNotFoundError:
        pass
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(body)
    one = out["1本"]
    print(f"書き出し: {OUT} {len(body.encode('utf-8'))}バイト 開催日={day} 比べた人数={one and one['比べた人数']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
