# -*- coding: utf-8 -*-
# backtestHaran2025h2.py
# data/haranModel.json の morning7（7特徴）を 2025-07-15〜2025-12-31 に当て、
# 係数が期間をまたいで保たれているかを見る。引数なしで実行する。
#
# ★これは walk-forward ではない。2026年で引いた係数を2025年に当てる＝時系列的に逆走。
#   リークではないが性能の証明にはならない。言えるのは「係数の向きと大きさが
#   期間をまたいで保たれているか」まで。
#
# 素材:
#   results/*.json            着順・ST・コース・登番（リポジトリ直下・全期間）
#   data/haranModel.json      係数・平均・標準偏差・欠損代替値（読むだけ。手打ちしない）
#   docs/data/rankHistory.json 級別の履歴（読むだけ）。results/ に級別が無いため。
#
# 特徴量は scripts/buildRacerFormIndex.py と同じ定義。ただし全期間の累積ではなく
# 「前日終了時点まで」で積み直す（本番の build_highlights.py が朝に見る状態と同じ）。
# 出力は標準出力だけ。ファイルは一切書かない。
import os
import json
import glob
import statistics
from collections import deque, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = os.path.join(ROOT, "data", "haranModel.json")
RANKH = os.path.join(ROOT, "docs", "data", "rankHistory.json")
RESDIR = os.path.join(ROOT, "results")
PREDIR = os.path.join(ROOT, "predictions")

LAST_N, C1_N = 20, 10
MIN_LAST, MIN_C1, MIN_ST, MIN_VEN = 10, 5, 20, 200
LV = {"A1": 4, "A2": 3, "B1": 2, "B2": 1}

WIN_A = ("2025-07-15", "2025-12-31")   # 本題
WIN_B = ("2026-02-01", "2026-08-22")   # 公表値と同じ範囲。配管が正しいかの確認用


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


def auc(pairs):
    """Mann-Whitney。同値は平均順位。pairs = [(スコア, y)]"""
    xs = sorted(pairs, key=lambda t: t[0])
    n = len(xs)
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and xs[j + 1][0] == xs[i][0]:
            j += 1
        r = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[k] = r
        i = j + 1
    n1 = sum(1 for _, y in xs if y == 1)
    n0 = n - n1
    if n1 == 0 or n0 == 0:
        return None
    s1 = sum(ranks[k] for k in range(n) if xs[k][1] == 1)
    return (s1 - n1 * (n1 + 1) / 2.0) / (n1 * n0)


def build_rank_lookup():
    """級別履歴（公式Bファイル由来）を「その日時点の級別」で引けるようにする。"""
    src = json.load(open(RANKH, encoding="utf-8"))
    hist = {str(t): sorted((d, r) for d, r in h) for t, h in src["選手"].items()}

    def rank_on(toban, ymd):
        h = hist.get(str(toban))
        if not h:
            return None
        cur = None
        for d, r in h:
            if d > ymd:
                break
            cur = r
        return cur
    return rank_on


def scan():
    """results/ を日付順に走り、各レースの「前日終了時点」の7特徴とスコアを作る。"""
    feats = [(f["キー"], f["係数"], f["欠損代替値"], f["平均"], f["標準偏差"])
             for f in json.load(open(MODEL, encoding="utf-8"))["モデル"]["morning7"]["特徴量"]]
    rank_on = build_rank_lookup()

    last, c1 = {}, {}
    st = defaultdict(lambda: [0, 0.0])
    ven = defaultdict(lambda: [0, 0])

    def f_last20(t):
        L = last.get(t)
        return (sum(L) / len(L)) if L and len(L) >= MIN_LAST else None

    def f_c1(t):
        C = c1.get(t)
        return (sum(C) / len(C)) if C and len(C) >= MIN_C1 else None

    def f_st(t):
        n, s = st[t]
        return (s / n) if n >= MIN_ST else None

    def f_ven(j):
        n, o = ven[j]
        return (o / n * 100.0) if n >= MIN_VEN else None

    rows = []
    rank_seen = rank_miss = 0
    files = sorted(glob.glob(os.path.join(RESDIR, "*.json")))
    for p in files:
        day = json.load(open(p, encoding="utf-8"))
        hd = str(day.get("開催日") or "").strip()
        ymd = "{}-{}-{}".format(hd[:4], hd[4:6], hd[6:8])
        pend = []
        for race in day.get("結果", []) or []:
            boats = race.get("艇", []) or []
            jcd = str(race.get("場コード") or "").strip()
            bw = {}
            for b in boats:
                try:
                    bw[int(b.get("枠"))] = b
                except Exception:
                    pass
            b1 = bw.get(1)
            y_c = norm_chaku(b1.get("着")) if b1 is not None else None
            # 枠1が欠場・不明のレースは分母から除く（buildRacerFormIndex と同じ扱い）
            if jcd and b1 is not None and y_c is not None:
                t1 = str(b1.get("登番") or "").strip()
                r1 = rank_on(t1, ymd)
                rank_seen += 1
                if r1 is None:
                    rank_miss += 1
                mid = [v for v in (f_last20(str((bw.get(2) or {}).get("登番") or "").strip()),
                                   f_last20(str((bw.get(3) or {}).get("登番") or "").strip()))
                       if v is not None]
                rkout = 0
                for w in (4, 5, 6):
                    b = bw.get(w)
                    if b is None:
                        continue
                    # 級別が引けない選手は B1=2 で埋める（build_highlights.py と同じ既定）
                    rkout += LV.get(rank_on(str(b.get("登番") or "").strip(), ymd), 2)
                vals = {
                    "rk1": LV.get(r1) if r1 else None,
                    "last20": f_last20(t1),
                    "rkout": rkout if len(bw) >= 4 else None,
                    "venOut": f_ven(jcd),
                    "c1last10": f_c1(t1),
                    "avgSt": f_st(t1),
                    "midLastBest": (min(mid) if mid else None),
                }
                z = 0.0
                miss = 0
                for k, co, med, mu, sd in feats:
                    v = vals.get(k)
                    if v is None:
                        v = med
                        miss += 1
                    z += co * ((float(v) - mu) / sd)
                rows.append({"ymd": ymd, "jcd": jcd, "rno": str(race.get("レース") or ""),
                             "s": z, "y": (1 if y_c not in (1, 2, 3) else 0), "miss": miss,
                             "v": [vals[k[0]] for k in feats]})
            pend.append((jcd, bw, boats))

        # 当日の結果は翌日以降の特徴へ反映する（当日の結果を当日の特徴に混ぜない）
        for jcd, bw, boats in pend:
            b1 = bw.get(1)
            if jcd and b1 is not None:
                c = norm_chaku(b1.get("着"))
                if c is not None:
                    v = ven[jcd]
                    v[0] += 1
                    if c not in (1, 2, 3):
                        v[1] += 1
            for b in boats:
                t = str(b.get("登番") or "").strip()
                if not t:
                    continue
                c = norm_chaku(b.get("着"))
                if c is not None:
                    last.setdefault(t, deque(maxlen=LAST_N)).append(c)
                    if str(b.get("コース")) == "1":
                        c1.setdefault(t, deque(maxlen=C1_N)).append(c)
                s = b.get("ST")
                if s is not None:
                    try:
                        fv = float(s)
                    except Exception:
                        continue
                    rec = st[t]
                    rec[0] += 1
                    rec[1] += fv
    return feats, rows, len(files), rank_seen, rank_miss


def win(rows, lo, hi, miss0=False):
    return [r for r in rows if lo <= r["ymd"] <= hi and (not miss0 or r["miss"] == 0)]


def tail(rows, frac, top):
    srt = sorted(rows, key=lambda r: r["s"], reverse=top)
    return srt[:int(round(len(srt) * frac))]


def line(name, rows):
    n = len(rows)
    if not n:
        print("  {:<26} 該当なし".format(name))
        return
    hi, lo = tail(rows, 0.10, True), tail(rows, 0.10, False)
    print("  {:<26} n={:6d} 母集団{:5.1f}% AUC {:.4f} 上位10%{:5.1f}% 下位10%{:5.1f}% 場数{:3d}".format(
        name, n, sum(r["y"] for r in rows) / n * 100,
        auc([(r["s"], r["y"]) for r in rows]),
        sum(r["y"] for r in hi) / len(hi) * 100,
        sum(r["y"] for r in lo) / len(lo) * 100,
        len(set(r["jcd"] for r in hi))))


def block(name, rows):
    n = len(rows)
    hi, lo = tail(rows, 0.10, True), tail(rows, 0.10, False)
    bym = defaultdict(list)
    for r in rows:
        bym[r["ymd"][:7]].append(r)
    print("■ {}".format(name))
    print("  日数 {} / レース {} / 母集団の①着外率 {:.1f}%".format(
        len(set(r["ymd"] for r in rows)), n, sum(r["y"] for r in rows) / n * 100))
    print("  AUC {:.4f}".format(auc([(r["s"], r["y"]) for r in rows])))
    print("  上位10%の①着外率 {:.1f}%（n={}） / 下位10%の①着外率 {:.1f}%（n={}）".format(
        sum(r["y"] for r in hi) / len(hi) * 100, len(hi),
        sum(r["y"] for r in lo) / len(lo) * 100, len(lo)))
    print("  上位10%が散る場数 {}".format(len(set(r["jcd"] for r in hi))))
    print("  7特徴が全部そろった行 {:.1f}% / 1レース平均の欠損特徴数 {:.2f}".format(
        sum(1 for r in rows if r["miss"] == 0) / n * 100,
        sum(r["miss"] for r in rows) / n))
    mon = []
    for m in sorted(bym):
        mr = bym[m]
        mh = tail(mr, 0.10, True)
        mon.append((m, len(mr), sum(x["y"] for x in mr) / len(mr) * 100,
                    sum(x["y"] for x in mh) / len(mh) * 100,
                    auc([(x["s"], x["y"]) for x in mr])))
    print("  月ごと（各月の中で上位10%を切る）:")
    for m, c, b, h, a in mon:
        print("    {} n={:5d} 母集団{:5.1f}% 上位10%{:5.1f}% AUC {:.4f}".format(m, c, b, h, a))
    hs = [x[3] for x in mon]
    au = [x[4] for x in mon]
    print("  月ごとのブレ: 上位10% {:.1f}〜{:.1f}%（幅 {:.1f}pt） / AUC {:.4f}〜{:.4f}".format(
        min(hs), max(hs), max(hs) - min(hs), min(au), max(au)))
    print()


def deciles(name, rows):
    s = sorted(rows, key=lambda r: r["s"], reverse=True)
    n = len(s)
    out = []
    for i in range(10):
        seg = s[int(n * i / 10):int(n * (i + 1) / 10)]
        out.append(sum(x["y"] for x in seg) / len(seg) * 100)
    print("  {:<12}".format(name) + " ".join("{:5.1f}".format(v) for v in out))


def validate(rows):
    """本番が predictions/*.json に残した 波乱指数 と突き合わせる（配管の答え合わせ）。"""
    mine = {(r["ymd"].replace("-", ""), r["jcd"], r["rno"]): r["s"] for r in rows}
    pairs = []
    have = 0
    for p in sorted(glob.glob(os.path.join(PREDIR, "*.json"))):
        d = json.load(open(p, encoding="utf-8"))
        hd = str(d.get("開催日") or "")
        for e in d.get("予測", []) or []:
            hv = e.get("波乱指数")
            if hv is None:
                continue
            have += 1
            k = (hd, e.get("場コード"), e.get("レース"))
            if k in mine:
                pairs.append((hv, mine[k]))
    print("■ 本番の 波乱指数 との突き合わせ（配管の答え合わせ）")
    if not pairs:
        print("  突き合わせ対象なし（predictions/ に 波乱指数 が無い）")
        print()
        return
    n = len(pairs)
    xa = [a for a, _ in pairs]
    xb = [b for _, b in pairs]
    ma, mb = statistics.mean(xa), statistics.mean(xb)
    sa, sb = statistics.pstdev(xa), statistics.pstdev(xb)
    cov = sum((a - ma) * (b - mb) for a, b in pairs) / n
    er = sorted(abs(a - b) for a, b in pairs)
    print("  照合 {}件（本番に 波乱指数 がある {}件のうち結果が出ているぶん）".format(n, have))
    print("  相関 r={:.5f} / 差の絶対値 中央値 {:.4f}・平均 {:.4f}・最大 {:.4f}".format(
        cov / (sa * sb), er[n // 2], sum(er) / n, er[-1]))
    print("  ※完全一致にはならない。本番は data/racerFormIndex.json を毎日は引き直して")
    print("    いないため、本番が見た値はこちらの再構築より少し古い。")
    print()


def main():
    feats, rows, nfile, rseen, rmiss = scan()
    A = win(rows, *WIN_A)
    B = win(rows, *WIN_B)
    A2 = win(rows, "2025-09-01", WIN_A[1])
    print("走査 {}ファイル / 有効レース {} / ①の級別を引けなかった {}件（{:.2f}%）".format(
        nfile, len(rows), rmiss, rmiss / rseen * 100))
    print()
    block("2025年後半（本題）{}〜{}".format(*WIN_A), A)
    block("助走を除いた再掲 2025-09-01〜{}".format(WIN_A[1]), A2)
    block("2026-02〜2026-08-22（公表値と同じ範囲・配管の確認）", B)

    print("■ 特徴量ごとの単独AUC（欠損行は除く。係数の向きに合わせてある＝0.5超なら向きが保たれている）")
    print("  {:<12} {:>9} {:>9} {:>10} {:>9}".format("キー", "係数", "2025後半", "2025/09-12", "2026年"))
    for i, (k, co, med, mu, sd) in enumerate(feats):
        vs = []
        for W in (A, A2, B):
            a = auc([(r["v"][i], r["y"]) for r in W if r["v"][i] is not None])
            vs.append(a if co > 0 else 1 - a)
        print("  {:<12} {:>+9.5f} {:>9.4f} {:>10.4f} {:>9.4f}".format(k, co, *vs))
    print()

    print("■ 特徴量の分布（欠損を除いた実測。JSONの標準化定数がその期間に合っているか）")
    print("  {:<12} {:>8} {:>8} | {:>8} {:>8} | {:>8} {:>8} | {:>7} {:>7}".format(
        "キー", "JSON平均", "JSON sd", "25後半平均", "25後半sd", "26年平均", "26年sd", "25欠損%", "26欠損%"))
    for i, (k, co, med, mu, sd) in enumerate(feats):
        va = [r["v"][i] for r in A if r["v"][i] is not None]
        vb = [r["v"][i] for r in B if r["v"][i] is not None]
        print("  {:<12} {:>8.4f} {:>8.4f} | {:>8.4f} {:>8.4f} | {:>8.4f} {:>8.4f} | {:>7.1f} {:>7.1f}".format(
            k, mu, sd, statistics.mean(va), statistics.pstdev(va),
            statistics.mean(vb), statistics.pstdev(vb),
            (1 - len(va) / len(A)) * 100, (1 - len(vb) / len(B)) * 100))
    print()

    print("■ スコア10分位ごとの①着外率（%）")
    print("  {:<12}".format("分位") + " ".join("{:>5}".format(x) for x in
                                              ["上位1", "2", "3", "4", "5", "6", "7", "8", "9", "下位10"]))
    deciles("2025後半", A)
    deciles("2025/09-12", A2)
    deciles("2026年", B)
    print()

    print("■ 7特徴が全部そろった行だけに絞った比較（欠損代替の影響を落とす）")
    line("2025後半 全行", A)
    line("2025後半 欠損ゼロ", win(rows, *WIN_A, miss0=True))
    line("2026年 全行", B)
    line("2026年 欠損ゼロ", win(rows, *WIN_B, miss0=True))
    print()
    validate(rows)


if __name__ == "__main__":
    main()
