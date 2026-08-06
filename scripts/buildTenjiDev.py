#!/usr/bin/env python3
"""tenjiDev1（展示タイム偏差）の効果検証。

目的変数は「①（1号艇）が着外＝4着以下か」。
素材は kdata/entriesFull.csv（mbrace Kファイル由来・250722〜260721・328,176行）。

このスクリプトは分析専用。docs/ 配下には一切書き込まない。
標準出力に結果を出すだけで、ファイルは作らない。

再現手順:
    python3 scripts/buildTenjiDev.py

出力は analysis/tenjiDev/result.md の数値と一致する。
"""
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

REPO = Path(__file__).resolve().parents[1]
ENTRIES = REPO / "kdata" / "entriesFull.csv"
CORE = REPO / "docs" / "data" / "racerStatsCore.json"

PLACED = {"01", "02", "03", "04", "05", "06"}
TOP3 = {"01", "02", "03"}
ABSENT = {"K0", "K1", "00"}
RACED_NOPLACE = {"F", "S0", "S1", "S2", "L0", "L1"}

T_MIN, T_MAX = 5.0, 9.0
MOTOR_MIN_RUN = 10

BASE = ["cWin1", "motor1", "cWin1_na", "motor1_na"]
FULL = BASE + ["tenjiDev1"]

SPLITS = [
    ("250722", "260501", "260722"),
    ("250722", "260401", "260722"),
    ("260101", "260601", "260722"),
]


def load_cwin():
    """1コース1着率（fan2604・期首固定）。登番→率。"""
    core = json.loads(CORE.read_text(encoding="utf-8"))
    out = {}
    for p in core["players"]:
        c1 = p.get("c1") or []
        if c1 and c1[0] is not None:
            out[str(p["no"])] = float(c1[0])
    return out


def parse_tenji(raw):
    try:
        v = float(raw.strip())
    except ValueError:
        return None
    return v if T_MIN < v < T_MAX else None


def build():
    """レース単位のデータセットを作る。

    motor1 は「そのレース開始時点までの累積」だけで計算する。
    docs/data/motorUsage.json は現時点までの累積＝未来を含むため使わない。
    """
    cwin = load_cwin()

    races = defaultdict(list)
    with ENTRIES.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            races[(row["hd"], row["jcd"], row["rno"])].append(row)

    motor_run = defaultdict(int)
    motor_top2 = defaultdict(int)

    recs = []
    drop = {"absent": 0, "no_boat1": 0, "tenji1_missing": 0, "few_others": 0}

    for key in sorted(races.keys()):
        hd, jcd, rno = key
        boats = races[key]

        mk1 = None
        for b in boats:
            if b["waku"] == "1":
                mk1 = jcd + "_" + b["motorNo"]
        run1 = motor_run[mk1] if mk1 else 0
        motor1 = (motor_top2[mk1] / run1 * 100.0) if run1 >= MOTOR_MIN_RUN else None

        for b in boats:
            mk = jcd + "_" + b["motorNo"]
            if b["chaku"] in PLACED:
                motor_run[mk] += 1
                if b["chaku"] in ("01", "02"):
                    motor_top2[mk] += 1

        b1 = next((b for b in boats if b["waku"] == "1"), None)
        if b1 is None:
            drop["no_boat1"] += 1
            continue
        if b1["chaku"] in ABSENT or (
            b1["chaku"] not in PLACED and b1["chaku"] not in RACED_NOPLACE
        ):
            drop["absent"] += 1
            continue

        t1 = parse_tenji(b1["tenjiT"])
        if t1 is None:
            drop["tenji1_missing"] += 1
            continue

        others = [parse_tenji(b["tenjiT"]) for b in boats if b["waku"] != "1"]
        others = [v for v in others if v is not None]
        if len(others) < 2:
            drop["few_others"] += 1
            continue

        recs.append(
            {
                "hd": hd,
                "jcd": jcd,
                "rno": rno,
                "y": 0 if b1["chaku"] in TOP3 else 1,
                "cWin1": cwin.get(b1["toban"]),
                "motor1": motor1,
                "tenjiDev1": t1 - sum(others) / len(others),
            }
        )

    return pd.DataFrame(recs), set(races.keys()), drop


def fit_predict(train, test, cols):
    model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))
    model.fit(train[cols], train["y"])
    return model, model.predict_proba(test[cols])[:, 1]


def report_drop_rate(df, all_keys):
    kept = set(zip(df["hd"], df["jcd"], df["rno"]))
    by_month = defaultdict(lambda: [0, 0])
    by_venue = defaultdict(lambda: [0, 0])
    for key in all_keys:
        hd, jcd, _ = key
        month = "20" + hd[:4]
        by_month[month][0] += 1
        by_venue[jcd][0] += 1
        if key not in kept:
            by_month[month][1] += 1
            by_venue[jcd][1] += 1
    print("")
    print("--- drop rate by month ---")
    for m in sorted(by_month):
        total, dropped = by_month[m]
        print(m, total, dropped, round(dropped / total * 100, 2))
    print("")
    print("--- drop rate by venue ---")
    for v in sorted(by_venue):
        total, dropped = by_venue[v]
        print(v, total, dropped, round(dropped / total * 100, 2))


def main():
    df, all_keys, drop = build()
    n_races = len(all_keys)
    print("races_total", n_races)
    print("kept", len(df), "drop", drop,
          "drop_rate%", round((n_races - len(df)) / n_races * 100, 2))
    print("y_rate%", round(df["y"].mean() * 100, 2))
    print("cWin1_missing", int(df["cWin1"].isna().sum()),
          "motor1_missing", int(df["motor1"].isna().sum()))
    print("tenjiDev1 mean", round(df["tenjiDev1"].mean(), 4),
          "sd", round(df["tenjiDev1"].std(), 4))

    for c in ("cWin1", "motor1"):
        df[c + "_na"] = df[c].isna().astype(int)
        df[c] = df[c].fillna(df[c].median())

    print("")
    print("--- splits ---")
    for lo, cut, hi in SPLITS:
        train = df[(df["hd"] >= lo) & (df["hd"] < cut)]
        test = df[(df["hd"] >= cut) & (df["hd"] < hi)]
        _, p_base = fit_predict(train, test, BASE)
        model, p_full = fit_predict(train, test, FULL)
        auc_base = roc_auc_score(test["y"], p_base)
        auc_full = roc_auc_score(test["y"], p_full)
        print("train", lo, "-", cut, "n=", len(train),
              "| test", cut, "-", hi, "n=", len(test))
        print("   base", round(auc_base, 4),
              "full", round(auc_full, 4),
              "diff", round(auc_full - auc_base, 4),
              "coef_tenjiDev1", round(float(model[-1].coef_[0][4]), 4))
        if auc_full > 0.85:
            print("   STOP: AUC>0.85 leakage suspected")
            return

    train = df[df["hd"] < "260501"]
    test = df[df["hd"] >= "260501"]
    _, p_base = fit_predict(train, test, BASE)
    _, p_full = fit_predict(train, test, FULL)
    y = test["y"].values
    rng = np.random.default_rng(0)
    diffs = []
    for _ in range(500):
        idx = rng.integers(0, len(y), len(y))
        if 0 < y[idx].sum() < len(y):
            diffs.append(roc_auc_score(y[idx], p_full[idx])
                         - roc_auc_score(y[idx], p_base[idx]))
    diffs = np.array(diffs)
    print("")
    print("bootstrap diff mean", round(float(diffs.mean()), 4),
          "95%CI", round(float(np.percentile(diffs, 2.5)), 4),
          round(float(np.percentile(diffs, 97.5)), 4),
          "p(diff<=0)", round(float((diffs <= 0).mean()), 4))

    _, p_only = fit_predict(train, test, ["tenjiDev1"])
    # 小数第4位は scikit-learn の版で動くため第3位まで
    print("tenjiDev1 alone AUC", round(roc_auc_score(test["y"], p_only), 3))

    print("")
    print("--- decile ---")
    # pd.qcut は使わない。tenjiDev1 は展示タイム由来の離散値で同値率が98.4%あり、
    # 同値を分割できないため境界の寄り方が pandas の版で変わる（各群のnが数十件動く）。
    # さらに round(6) を挟む。偏差は引き算と割り算で作るため最下位ビット（1e-16）に
    # 環境差が出て、生値では unique が857あるが実体は358しかない（499は誤差由来の
    # 疑似ユニーク）。丸めないと同値判定が揺れて rank の順序が環境で変わる。
    df["dec"] = (df["tenjiDev1"].round(6).rank(method="first")
                 * 10 // (len(df) + 1)).astype(int)
    g = df.groupby("dec").agg(n=("y", "size"), out_rate=("y", "mean"),
                              dev=("tenjiDev1", "mean"))
    g["out_rate"] = (g["out_rate"] * 100).round(1)
    g["dev"] = g["dev"].round(3)
    print(g.to_string())

    print("")
    print("--- venue coef ---")
    coefs = []
    for jcd, grp in df.groupby("jcd"):
        tr = grp[grp["hd"] < "260501"]
        model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))
        model.fit(tr[FULL], tr["y"])
        coefs.append((jcd, round(float(model[-1].coef_[0][4]), 3)))
    coefs.sort(key=lambda x: x[1])
    print(coefs)
    print("coef<=0 count", sum(1 for _, c in coefs if c <= 0))

    report_drop_rate(df, all_keys)


if __name__ == "__main__":
    main()
