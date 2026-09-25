# -*- coding: utf-8 -*-
# aggNinki_k04.py
# payrank\aggNinki.py の複製。入力の payrank\json は読むだけで、出力先だけを作業フォルダに変えた。
# fetchPayRank.py が json/ に貯めた払戻データから、
# 「3連単の1番人気がそのまま入ったレース」の割合を場別に集計する。
#
# 人気の定義:
#   公式払戻金一覧の「人気」列。確定オッズに基づく順位。
#   1 なら、そのレースは1番人気が的中したということ。
#   odds/ の締切前スナップショットとは定義が違うので混ぜない。
#
# 分母から外すもの:
#   ・空表の日(開催なし)
#   ・人気が数字でない行(不成立・特払など)。除外件数は必ず報告する。
#     分母の見えない率を出さないため、除外した数を隠さない。
#
# 出力:
#   ・標準出力に場別の表(的中率の降順)
#   ・ninkiTally.json に日別×場別の的中数と分母。
#     これがリポジトリに上げる唯一のファイルになる想定。生HTMLは上げない。
#     日別で持つのは、あとから期間を切り直した集計ができるようにするため。
import io
import os
import re
import sys
import json
import collections

ROOT = r"C:\Users\USER\payrank"
JSONDIR = os.path.join(ROOT, "json")
OUT = r"C:\Users\USER\kensho04parts\ninkiTally.json"

VENUE = {
    "01": "\u6850\u751f", "02": "\u6238\u7530", "03": "\u6c5f\u6238\u5ddd",
    "04": "\u5e73\u548c\u5cf6", "05": "\u591a\u6469\u5ddd", "06": "\u6d5c\u540d\u6e56",
    "07": "\u84b2\u90e1", "08": "\u5e38\u6ed1", "09": "\u6d25",
    "10": "\u4e09\u56fd", "11": "\u3073\u308f\u3053", "12": "\u4f4f\u4e4b\u6c5f",
    "13": "\u5c3c\u5d0e", "14": "\u9cf4\u9580", "15": "\u4e38\u4e80",
    "16": "\u5150\u5cf6", "17": "\u5bae\u5cf6", "18": "\u5fb3\u5c71",
    "19": "\u4e0b\u95a2", "20": "\u82e5\u677e", "21": "\u82a6\u5c4b",
    "22": "\u798f\u5ca1", "23": "\u5510\u6d25", "24": "\u5927\u6751",
}

K_HD = "\u958b\u50ac\u65e5"
K_EMPTY = "\u7a7a\u8868"
K_ROWS = "\u6255\u623b"
K_JCD = "\u5834\u30b3\u30fc\u30c9"
K_RACE = "\u30ec\u30fc\u30b9"
K_NINKI = "\u4eba\u6c17"
K_PAY = "\u6255\u623b"
K_KUMI = "\u7d44\u756a"

RE_INT = re.compile(r"^\d+$")
RE_YEN = re.compile(r"[^\d]")


def main():
    if not os.path.isdir(JSONDIR):
        print("no json dir: %s" % JSONDIR)
        return 2

    files = sorted(f for f in os.listdir(JSONDIR) if f.endswith(".json"))
    if not files:
        print("no json files")
        return 2

    hit = collections.Counter()
    tot = collections.Counter()
    paysum = collections.Counter()
    rankdist = collections.Counter()
    tally = {}

    n_day = n_empty = 0
    n_drop = 0
    n_kumi = 0
    dropvals = collections.Counter()
    first = last = None

    for fn in files:
        hd = fn[:-5]
        with io.open(os.path.join(JSONDIR, fn), encoding="utf-8") as f:
            doc = json.load(f)
        if doc.get(K_EMPTY):
            n_empty += 1
            continue
        n_day += 1
        if first is None or hd < first:
            first = hd
        if last is None or hd > last:
            last = hd

        day = {}
        for r in doc.get(K_ROWS, []):
            jcd = r.get(K_JCD, "")
            # 組番が3艇でない行は分母に入れない。
            # "-" が5個の行は同着で確定組番が2組あり、人気も2つの順位が
            # 連結されている(例 "12" は1番人気と2番人気)。桁の切り方が
            # 一意に決まらないため分離できない。121以下の値は数字として
            # 自然に見えてしまい、検算では検出できない汚染になる。
            # "-" が0個や1個の行はレース中止・3連単不成立。
            kumi = (r.get(K_KUMI) or "").strip()
            if kumi.count("-") != 2:
                n_kumi += 1
                continue
            nk = (r.get(K_NINKI) or "").strip()
            if not RE_INT.match(nk):
                n_drop += 1
                dropvals[nk] += 1
                continue
            rank = int(nk)
            tot[jcd] += 1
            rankdist[min(rank, 121)] += 1
            d = day.setdefault(jcd, [0, 0])
            d[1] += 1
            if rank == 1:
                hit[jcd] += 1
                d[0] += 1
                yen = RE_YEN.sub("", r.get(K_PAY) or "")
                if yen:
                    paysum[jcd] += int(yen)
        tally[hd] = day

    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write(json.dumps(
            {"\u671f\u9593": [first, last],
             "\u96c6\u8a08\u65e5\u6570": n_day,
             "\u65e5\u5225": tally},
            ensure_ascii=False, separators=(",", ":")))

    N = sum(tot.values())
    H = sum(hit.values())
    print("period %s - %s / days=%d (empty=%d)" % (first, last, n_day, n_empty))
    print("races=%d  hit=%d  rate=%.2f%%  per12R=%.2f"
          % (N, H, 100.0 * H / max(1, N), 12.0 * H / max(1, N)))
    print("excluded (kumi not 3 boats)=%d" % n_kumi)
    print("dropped (ninki not numeric)=%d  (%.2f%% of all rows)"
          % (n_drop, 100.0 * n_drop / max(1, N + n_drop)))
    for v, c in dropvals.most_common():
        print("  dropvalue %r : %d" % (v, c))
    print("")
    print("venue\tcode\thit\ttotal\trate%\tper12R\tavgPay")
    rows = []
    for jcd in tot:
        n = tot[jcd]
        h = hit[jcd]
        rows.append((VENUE.get(jcd, jcd), jcd, h, n,
                     100.0 * h / n, 12.0 * h / n,
                     (paysum[jcd] / h) if h else 0))
    rows.sort(key=lambda x: -x[4])
    for r in rows:
        print("%s\t%s\t%d\t%d\t%.2f\t%.2f\t%.0f"
              % (r[0], r[1], r[2], r[3], r[4], r[5], r[6]))

    print("")
    print("rank distribution (top 10)")
    for rank, c in sorted(rankdist.items())[:10]:
        print("  %3d\u756a\u4eba\u6c17: %6d  %.2f%%" % (rank, c, 100.0 * c / max(1, N)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
