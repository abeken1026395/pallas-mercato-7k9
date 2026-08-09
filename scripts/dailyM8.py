# -*- coding: utf-8 -*-
# dailyM8.py
# M8（①＝1号艇が着外＝4着以下 になる確率）の影運用。朝と夜の2本立て。
#
#   MODE=am（朝・既定）
#     1. 学習（拡張窓：TRAIN_FIRST〜前日の全レース）
#     2. 当日の全レースを推論し predictions/m8/YYYYMMDD.json に書く（上位3件だけ high=true）
#     3. 前日ぶんの答え合わせを m8VerifyLog.csv に追記する（am・pm の両方を照合する）
#   MODE=pm（夜）
#     その時点で出ている展示タイムを込みで全レースを推論し直し、
#     predictions/m8/YYYYMMDD_pm.json に書く。照合はしない（朝の回が翌日まとめてやる）。
#
# なぜ2本記録するのか:
#   展示タイム（tenjiDev1 の素材）は各レースの直前にしか出ない。朝に走らせると
#   ほぼ全欠測になり、検証時（展示あり）とは別物の精度になる。実測では
#   日次3件の precision が 展示あり 58.0% → 展示なし 53.8%。
#   どちらが実運用の値かを机上で決めず、両方を同じ土俵で記録して実データで比べる。
#   朝版は「朝の時点で言えること」、夜版は「展示まで込みで言えること」。用途が違う。
#
# 影運用とは: 記録だけして読者の画面は一切変えないこと。
#   ・docs/ には何も書かない。公開ページ・highlights・verify_log には一切触れない。
#   ・出力は predictions/m8/ と m8VerifyLog.csv の2箇所だけ。
#
# 書き込みの掟:
#   ・predictions/m8/YYYYMMDD.json（朝）と YYYYMMDD_pm.json（夜）はどちらも write-once。
#     既にあれば上書きせずスキップしてログに出す。ファイル単位で独立に判定する。
#     既存 predictions/ と同じ掟（後から作り直せると検証ループが成立しなくなる）。
#   ・m8VerifyLog.csv は追記のみ。同じ (date, model) の行が既にあれば何もしない。
#
# pv2/ の当日ぶんだけは取り直す:
#   展示タイムはレース直前に埋まっていくので、朝に保存したスナップショットのままだと
#   夜の回も展示ゼロのままになる。対象日が「JST当日」のときに限り取り直す。
#   過去日のファイルには絶対に触れない。
#
# モデル構成（Phase3.6 で確定。ここは動かさない）:
#   特徴量22列 = scripts/buildM8Features.py の M8_FEATURES
#   LogisticRegression（中央値補完＋欠測フラグ＋標準化）と
#   HistGradientBoosting（max_leaf_nodes=7 / learning_rate=0.03 / min_samples_leaf=50 /
#                         max_iter=200 / l2_regularization=1.0）の確率加重平均
#   重み LR 0.3 : HGB 0.7 ＋ isotonic 校正（学習窓の末尾30日を内側ホールドアウトにして当てる）
#   walk-forward 2026-01〜08 実測: AUC 0.7232 / 日次3件 precision 56.67%
#   ※isotonic は単調変換なので順位は変えない。high の3件は校正の有無に依らず同じ。
#
# 展示タイムについて（重要）:
#   tenjiDev1（展示タイム偏差）は直前情報なので、朝の時点ではまだ出ていない。
#   朝に走らせると tenjiDev1 はほぼ全欠測になる。モデルは欠測を扱えるので推論は通るが、
#   検証時（展示あり）とは別物の精度になる。出力JSONに「展示タイム有効数」を必ず残し、
#   後から「展示あり／なし」で切り分けられるようにしてある。
#
# 使い方:
#   python scripts/dailyM8.py               … JST当日・MODEは時刻から自動判定
#   MODE=am python scripts/dailyM8.py       … 朝版
#   MODE=pm python scripts/dailyM8.py       … 夜版
#   HD=20260808 python scripts/dailyM8.py   … 対象日を指定（試運転用）
#   M8_VERIFY_ONLY=1 …… 推論せず前日照合だけ行う（MODE=am のときだけ意味がある）
import io
import os
import csv
import gzip
import sys
import json
import time
import datetime

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.isotonic import IsotonicRegression

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import buildM8Features as F   # noqa: E402

MODEL_BASE = "m8-v1"
MODES = ("am", "pm")
AM_UNTIL_HOUR = 15         # schedule 起動で MODE 未指定のとき、JSTこの時刻より前なら am
SEED = 42
HGB_PARAMS = dict(max_leaf_nodes=7, learning_rate=0.03, min_samples_leaf=50,
                  max_iter=200, l2_regularization=1.0,
                  early_stopping=False, random_state=SEED)
W_LR = 0.3                 # LR の重み（残りが HGB）
CALIB_DAYS = 30            # isotonic 用の内側ホールドアウト日数
HIGH_N = 3                 # 「高」として記録する件数

PRED_DIR = os.environ.get("M8_PRED_DIR", os.path.join("predictions", "m8"))
VERIFY_CSV = os.environ.get("M8_VERIFY_CSV", "m8VerifyLog.csv")
VERIFY_COLS = ["date", "model", "jcd", "rno", "p", "high", "y", "hit"]


def resolve_mode():
    """MODE を決める。未指定なら JST の時刻で判定する（schedule 起動用）。"""
    m = (os.environ.get("MODE") or "").strip().lower()
    if m in MODES:
        return m
    if m:
        raise SystemExit("ERROR: MODE は am / pm のいずれか（渡された値: %r）" % m)
    hour = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).hour
    m = "am" if hour < AM_UNTIL_HOUR else "pm"
    print("MODE 未指定 → JST %d時なので %s と判定" % (hour, m))
    return m


def model_id(mode):
    return "%s-%s" % (MODEL_BASE, mode)


def pred_path(hd, mode):
    """朝は YYYYMMDD.json、夜は YYYYMMDD_pm.json。
    朝のファイル名を変えないのは、既に出してしまった記録と地続きにするため。"""
    return os.path.join(PRED_DIR, "%s.json" % hd if mode == "am" else "%s_pm.json" % hd)


def merge_repo_preview(hd):
    """当日の展示タイムを、リポジトリの preview/YYYYMMDD.json から補う。

    ★配信元の実態（2026-08-09 実測）:
      v2 の previews（pv2/ の取得元）は当日のうちは更新されない。
      JST 20:53 に取り直しても朝と同じ 276/1008 のままだった。一方
      preview/YYYYMMDD.json（buildPreview.py が v1 から毎時作る）は同時刻で 971/1008。
      v2 は翌日以降にまとめて埋まる。夜の回で「展示込み」を名乗るには v1 側が要る。

    両者が同じ値であることは確認済み（2026-01-01〜08-08 の 205,992枠で不一致 0、
    v1 にだけある枠が 455）。キー名だけ v2 の形に直して pv2/previews/ に置く。
    置き換えるのは「対象日が JST当日」かつ「v1 側の展示が多いとき」だけ。過去日には触れない。
    """
    if hd != F.jst_today().strftime("%Y%m%d"):
        return 0
    src = os.path.join(os.environ.get("M8_PREVIEW_DIR", "preview"), "%s.json" % hd)
    if not os.path.exists(src):
        return 0
    try:
        with io.open(src, encoding="utf-8") as f:
            v1 = json.load(f)
    except Exception:
        return 0

    def filled(rows, key_boats, key_ex):
        n = 0
        for r in rows:
            for b in (r.get(key_boats) or []):
                v = b.get(key_ex)
                if v and float(v) > 0:
                    n += 1
        return n

    n_v1 = filled(v1.get("直前情報") or [], "racers", "exhibition_time")
    cur = F.load_pv2("previews", hd) or {}
    n_v2 = 0
    for r in cur.get("previews") or []:
        n_v2 += sum(1 for b in F.boats(r) if F.exhibition_time(b) is not None)
    if n_v1 <= n_v2:
        print("preview/ 取り込み: v1 %d枠 ≦ pv2 %d枠 → 置き換えない" % (n_v1, n_v2))
        return 0

    RACE = [("race_date", "date"), ("race_stadium_number", "stadium_number"),
            ("race_number", "race_number"), ("race_wind", "wind_speed"),
            ("race_wind_direction_number", "wind_direction_number"),
            ("race_wave", "wave_height"), ("race_weather_number", "weather_number"),
            ("race_temperature", "air_temperature"), ("race_water_temperature", "water_temperature")]
    BOAT = [("racer_boat_number", "entry_number"), ("racer_course_number", "course_number"),
            ("racer_start_timing", "start_timing"), ("racer_weight", "weight"),
            ("racer_weight_adjustment", "weight_adjustment"),
            ("racer_exhibition_time", "exhibition_time"),
            ("racer_tilt_adjustment", "tilt_adjustment")]
    rows = []
    for r in v1.get("直前情報") or []:
        o = dict((a, r.get(b)) for a, b in RACE)
        o["boats"] = [dict((a, b0.get(b)) for a, b in BOAT) for b0 in (r.get("racers") or [])]
        rows.append(o)
    obj = {"previews": rows,
           "_source": "preview/%s.json（v1由来）を v2 のキー名に直したもの。"
                      "当日の v2 previews が更新されないため夜の回で差し替えた" % hd,
           "_取得時刻": v1.get("取得時刻")}
    p = F.pv2_path("previews", hd)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with gzip.open(p, "wt", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    print("preview/ 取り込み: 展示 %d枠 → %d枠 に差し替えた（v1取得時刻 %s）"
          % (n_v2, n_v1, v1.get("取得時刻")))
    return n_v1


def refresh_today_pv2(hd):
    """対象日が JST当日 のときだけ pv2 を取り直す。展示タイムは時間とともに埋まるため。
    取得に失敗したら元のファイルに戻す（消しっぱなしにしない）。過去日には触れない。"""
    if hd != F.jst_today().strftime("%Y%m%d"):
        return 0
    n = 0
    for kind in ("programs", "previews"):
        p = F.pv2_path(kind, hd)
        bak = p + ".bak"
        if os.path.exists(p):
            os.replace(p, bak)
        if F.fetch_pv2(kind, hd):
            n += 1
            if os.path.exists(bak):
                os.remove(bak)
        elif os.path.exists(bak):
            os.replace(bak, p)
            print("pv2: %s の取り直しに失敗。既存のスナップショットを使う" % p)
    print("pv2: 当日ぶんを %d ファイル取り直した" % n)
    return n


def design(d, onehot):
    """特徴量行列を作る。onehot=True は LR 用（grade/class1/sub_cat をダミー化）。
    HGB は欠測をそのまま扱えるので生値で渡す。"""
    cols = []
    for f in F.M8_FEATURES:
        if onehot and f in F.M8_CATEGORICAL:
            for lv in F.M8_CATEGORICAL[f][1:]:
                cols.append((pd.to_numeric(d[f], errors="coerce").values == lv).astype(float))
        else:
            cols.append(pd.to_numeric(d[f], errors="coerce").values.astype(float))
    return np.column_stack(cols)


def _lr():
    return Pipeline([("imp", SimpleImputer(strategy="median", add_indicator=True)),
                     ("sc", StandardScaler()),
                     ("m", LogisticRegression(max_iter=3000, C=1.0))])


def predict_raw(dtr, dte):
    """LR と HGB を学習して確率加重平均を返す（校正前）。"""
    ph = HistGradientBoostingClassifier(**HGB_PARAMS)\
        .fit(design(dtr, False), dtr.y.values).predict_proba(design(dte, False))[:, 1]
    pl = _lr().fit(design(dtr, True), dtr.y.values).predict_proba(design(dte, True))[:, 1]
    return W_LR * pl + (1.0 - W_LR) * ph


def fit_and_predict(train, target):
    """拡張窓で学習し、target の確率（isotonic 校正後）を返す。"""
    days = sorted(train.hd.unique())
    if len(days) <= CALIB_DAYS:
        raise SystemExit("ERROR: 学習日数が足りない（%d日）。校正に%d日必要" % (len(days), CALIB_DAYS))
    cut = days[-CALIB_DAYS]
    inner_fit, inner_cal = train[train.hd < cut], train[train.hd >= cut]
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    iso.fit(predict_raw(inner_fit, inner_cal), inner_cal.y.values)
    raw = predict_raw(train, target)
    return iso.predict(raw), raw


def write_predictions(hd, mode, target, p, raw, tenji_filled, tenji_slots, train):
    """順位は「校正前の確率 raw」で付ける。校正後の p は isotonic の階段関数なので
    同値が大量に出て（実測: 168レース中 rank3位と4位が同値になる日がある）、
    上位3件が場コード順という無意味な基準で決まってしまうため。
    isotonic は単調変換なので raw の順位は p の順位と矛盾しない（同値を割るだけ）。
    記録する確率 p は校正後の値のまま。"""
    out = pred_path(hd, mode)
    if os.path.exists(out):
        print("SKIP: %s は既にある。上書きしない（write-once）" % out)
        return False
    order = np.argsort(-raw, kind="stable")
    rank = np.empty(len(p), dtype=int)
    rank[order] = np.arange(1, len(p) + 1)
    races = []
    for i in range(len(target)):
        races.append({
            "jcd": "%02d" % int(target.jcd.iat[i]),
            "rno": int(target.rno.iat[i]),
            "p": round(float(p[i]), 4),
            "rank": int(rank[i]),
            "high": bool(rank[i] <= HIGH_N),
        })
    races.sort(key=lambda r: r["rank"])
    obj = {
        "生成時刻": datetime.datetime.now().isoformat(timespec="seconds"),
        "model": model_id(mode),
        "開催日": hd,
        "レース数": len(races),
        "展示タイム有効数": int(tenji_filled),
        "展示タイム枠数": int(tenji_slots),
        "学習件数": int(len(train)),
        "学習最終日": str(train.hd.max()),
        "順位の付け方": "校正前の確率の降順（校正後pは同値が出るため）",
        "races": races,
    }
    os.makedirs(PRED_DIR, exist_ok=True)
    with io.open(out, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    hi = [r for r in races if r["high"]]
    print("wrote %s races=%d high=%d（%s）展示 %d/%d 学習 %d件（〜%s）"
          % (out, len(races), len(hi),
             " ".join("%s-%dR p=%.3f" % (r["jcd"], r["rno"], r["p"]) for r in hi),
             tenji_filled, tenji_slots, len(train), train.hd.max()))
    return True


def _logged_keys():
    """m8VerifyLog.csv に既にある (date, model) の組を返す。"""
    done = set()
    if os.path.exists(VERIFY_CSV):
        with io.open(VERIFY_CSV, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                done.add((row.get("date"), row.get("model")))
    return done


def verify_one(prev_hd, mode, res, done):
    """前日の1本（am または pm）を results/ と突合して m8VerifyLog.csv に追記する。"""
    path = pred_path(prev_hd, mode)
    if not os.path.exists(path):
        print("照合[%s]: %s が無い（この回の見立ては出していない）→ 何もしない" % (mode, path))
        return 0
    with io.open(path, encoding="utf-8") as f:
        pred = json.load(f)
    # model はファイルが名乗っているものを正とする（過去に別IDで出した記録もそのまま残す）
    mid = pred.get("model") or model_id(mode)
    if (prev_hd, mid) in done:
        print("照合[%s]: %s / %s は既に %s にある → 追記しない" % (mode, prev_hd, mid, VERIFY_CSV))
        return 0
    rows, judged, hits, unknown = [], 0, 0, 0
    for r in pred.get("races") or []:
        jcd, rno = int(r["jcd"]), int(r["rno"])
        boat1 = (res.get((jcd, rno)) or {}).get(1)
        y = ""
        pl = boat1[1] if boat1 else None
        if pl is not None and int(pl) < F.PLACE_ABSENT:
            y = 1 if int(pl) > 3 else 0
        else:
            unknown += 1
        hit = ""
        if r["high"] and y != "":
            hit = 1 if y == 1 else 0
            judged += 1
            hits += hit
        rows.append({"date": prev_hd, "model": mid, "jcd": r["jcd"], "rno": rno, "p": r["p"],
                     "high": "true" if r["high"] else "false", "y": y, "hit": hit})
    new = not os.path.exists(VERIFY_CSV)
    with io.open(VERIFY_CSV, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=VERIFY_COLS)
        if new:
            w.writeheader()
        for row in rows:
            w.writerow(row)
    done.add((prev_hd, mid))
    print("照合[%s]: %s / %s を %d行追記。high判定 %d/%d 的中（着外か不明 %d件）"
          % (mode, prev_hd, mid, len(rows), hits, judged, unknown))
    return len(rows)


def verify(prev_hd):
    """前日ぶんを am・pm の両方について照合する。片方しか無ければ有る方だけ。"""
    if not any(os.path.exists(pred_path(prev_hd, m)) for m in MODES):
        print("照合: %s の見立てが am/pm とも無い → 何もしない" % prev_hd)
        return 0
    res = F.load_results(prev_hd)
    if not res:
        print("照合: results/%s.json が無い（結果未取得）→ 追記しない。次回に持ち越す" % prev_hd)
        return 0
    done = _logged_keys()
    return sum(verify_one(prev_hd, m, res, done) for m in MODES)


def main():
    hd = (os.environ.get("HD") or "").strip() or F.jst_today().strftime("%Y%m%d")
    mode = resolve_mode()
    prev_hd = (datetime.datetime.strptime(hd, "%Y%m%d").date() - datetime.timedelta(days=1)).strftime("%Y%m%d")
    print("=== dailyM8 MODE=%s 対象日 %s（前日 %s） ===" % (mode, hd, prev_hd))

    # 1) 前日照合（推論より先にやる。推論が落ちても照合は残る）
    #    照合は朝の回だけ。夜の回にもやらせると、当日の pm を翌朝に照合する前に
    #    走ってしまい「結果が出そろう前の照合」になりかねない。
    t_verify = 0.0
    if mode == "am":
        t0 = time.time()
        verify(prev_hd)
        t_verify = time.time() - t0
    else:
        print("照合: MODE=pm では行わない（翌朝の am がまとめて照合する）")

    if os.environ.get("M8_VERIFY_ONLY"):
        print("M8_VERIFY_ONLY=1 のため推論はしない")
        return

    if os.path.exists(pred_path(hd, mode)):
        print("SKIP: %s は既にある。学習も推論もしない（write-once）" % pred_path(hd, mode))
        return

    # 2) 素材と特徴量
    t0 = time.time()
    F.ensure_pv2(list(F.daterange(F.HIST_FIRST, hd)))
    refresh_today_pv2(hd)
    merge_repo_preview(hd)
    t_fetch = time.time() - t0
    t0 = time.time()
    rows = F.build(hd)
    t_feat = time.time() - t0
    if not rows:
        print("ERROR: 特徴量が0行。pv2/ か results/ を確認すること")
        raise SystemExit(1)
    df = pd.DataFrame(rows)
    for c in F.M8_FEATURES + ["y"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["hd"] = df["hd"].astype(str)

    target = df[(df.hd == hd)].sort_values(["jcd", "rno"]).reset_index(drop=True)
    train = df[(df.hd >= F.TRAIN_FIRST) & (df.hd < hd) & df.y.notna()].reset_index(drop=True)
    if not len(target):
        print("対象日 %s のレースが0件（非開催か番組表未発表）→ 何も書かない" % hd)
        return
    print("学習 %d件（%s〜%s）/ 推論 %d件" % (len(train), train.hd.min(), train.hd.max(), len(target)))

    # 3) 学習＋推論
    t0 = time.time()
    p, raw = fit_and_predict(train, target)
    t_model = time.time() - t0

    # 展示タイムがどれだけ出ているか（0は「まだ走っていない」の意味なので有効に数えない）
    pv = F.load_pv2("previews", hd) or {}
    slots = filled = 0
    for r in pv.get("previews") or []:
        for b in F.boats(r):
            slots += 1
            if F.exhibition_time(b) is not None:
                filled += 1
    write_predictions(hd, mode, target, p, raw, filled, slots, train)
    print("所要: 照合 %.1fs / pv2取得 %.1fs / 特徴量 %.1fs / 学習+推論 %.1fs"
          % (t_verify, t_fetch, t_feat, t_model))


if __name__ == "__main__":
    main()
