# -*- coding: utf-8 -*-
# stage0.py 年 … 検証04 宿題（場×レース番号）の分母づくり
#
# payrank\json を1日ずつ読み、場×開催日×レース番号の的中数と分母を数える。
# 除外の判定は aggNinki.py / aggNinkiDeep.py と同じ（design.md）:
#   ・組番の "-" が2個でない行（中止・不成立・同着）
#   ・人気が数字でない行（返）
# 除外の内訳は組番の "-" の数ごとにも数える（本文の 6,866・227・209・79 と突き合わせるため）。
#
# 出力は作業フォルダ（リポジトリの外）に年ごとの JSON。1年ずつ実行し、落ちた年だけやり直せる。
import io
import os
import re
import sys
import json
import collections

JSONDIR = r"C:\Users\USER\payrank\json"
PARTS = r"C:\Users\USER\kensho04parts"

K_EMPTY = "\u7a7a\u8868"
K_ROWS = "\u6255\u623b"
K_JCD = "\u5834\u30b3\u30fc\u30c9"
K_RACE = "\u30ec\u30fc\u30b9"
K_NINKI = "\u4eba\u6c17"
K_KUMI = "\u7d44\u756a"

RE_INT = re.compile(r"^[0-9]+$")          # \d は全角数字に一致するので使わない
RE_RNO = re.compile(r"^([0-9]+)R$")


def main(year):
    files = sorted(f for f in os.listdir(JSONDIR)
                   if f.endswith(".json") and f.startswith(year))
    units = {}                 # "YYYYMMDD|jcd" -> [[hit, n] * 13]（添字 1..12）
    rows = 0
    excl_kumi = collections.Counter()   # "-" の数ごと
    excl_ninki = collections.Counter()  # 人気の表示ごと
    bad_rno = 0
    days = empty = 0
    for fn in files:
        hd = fn[:-5]
        with io.open(os.path.join(JSONDIR, fn), encoding="utf-8") as f:
            doc = json.load(f)
        if doc.get(K_EMPTY):
            empty += 1
            continue
        days += 1
        for r in doc.get(K_ROWS, []):
            rows += 1
            kumi = (r.get(K_KUMI) or "").strip()
            if kumi.count("-") != 2:
                # レース中止は "-" が0個の行の中で別に数える（本文の 6,866）
                excl_kumi["stop" if kumi == "レース中止" else kumi.count("-")] += 1
                continue
            nk = (r.get(K_NINKI) or "").strip()
            if not RE_INT.match(nk):
                excl_ninki[nk] += 1
                continue
            m = RE_RNO.match((r.get(K_RACE) or "").strip())
            rno = int(m.group(1)) if m else 0
            if not 1 <= rno <= 12:
                bad_rno += 1
                continue
            key = hd + "|" + r.get(K_JCD, "")
            u = units.get(key)
            if u is None:
                u = units[key] = [[0, 0] for _ in range(13)]
            u[rno][1] += 1
            if int(nk) == 1:
                u[rno][0] += 1
    out = {"year": year, "files": len(files), "days": days, "empty": empty,
           "rows": rows, "badRno": bad_rno,
           "exclKumiDash": {str(k): v for k, v in sorted(excl_kumi.items(), key=lambda x: str(x[0]))},
           "exclNinki": dict(excl_ninki), "units": units}
    with io.open(os.path.join(PARTS, "stage0_%s.json" % year), "w", encoding="utf-8") as f:
        f.write(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    print("%s files=%d days=%d rows=%d units=%d badRno=%d"
          % (year, len(files), days, rows, len(units), bad_rno))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
