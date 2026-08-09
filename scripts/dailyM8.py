# -*- coding: utf-8 -*-
# dailyM8.py
# M8（①＝1号艇が着外＝4着以下 になる確率）の影運用。朝夜2本立て。
#
#   MODE=am（既定・JST 9時台）
#     1. 前日ぶんの v2 previews を確定版に差し替える（後述）
#     2. 学習（拡張窓：TRAIN_FIRST〜前日の全レース）
#     3. 当日の全レースを推論し predictions/m8/YYYYMMDD.json に書く（上位3件だけ high=true）
#     4. 前日ぶんの答え合わせを m8VerifyLog.csv に追記する（am版・pm版の両方を照合）
#
#   MODE=pm（JST 21時台）
#     1. 自前 preview/YYYYMMDD.json（v1）の展示を重ねた素材で全レースを再推論
#     2. predictions/m8/YYYYMMDD_pm.json に書く
#     3. 照合はしない（照合は翌朝の am 実行がまとめてやる）
#
# なぜ2本記録するのか:
#   朝は展示タイムがまだ出ていない（tenjiDev1 がほぼ全欠測）。夜は展示が揃っている。
#   同じ日を「展示なし」「展示あり」の2通りで記録しておけば、
#   展示タイムが精度にどれだけ効くのかを後から実測で切り分けられる。
#
# 展示の素材がどこから来るか（実測にもとづく。ここを間違えると pm が朝と同じものになる）:
#   ・上流 v2（pv2/previews）は当日のうちは更新されない。JST 0時でも埋まらず、
#     翌日になって確定版（全枠ぶん）が配信される。
#   ・当日の夜に展示が入っているのは自前の preview/YYYYMMDD.json（v1・毎時更新）だけ。
#   よって pm は v1 を読んで v2 の形に直し、pv2/ には書かずにその場の素材として使う。
#   一方、翌朝の am は前日ぶんの v2 を取り直して確定版に差し替える（学習素材を痩せさせないため）。
#
# 影運用とは: 記録だけして読者の画面は一切変えないこと。
#   ・docs/ には何も書かない。公開ページ・highlights・verify_log には一切触れない。
#   ・出力は predictions/m8/ と m8VerifyLog.csv の2箇所だけ。
#
# 書き込みの掟:
#   ・predictions/m8/YYYYMMDD.json（am）と YYYYMMDD_pm.json（pm）は
#     それぞれ write-once。既にあれば上書きせずスキップしてログに出す。
#     既存 predictions/ と同じ掟（後から作り直せると検証ループが成立しなくなる）。
#   ・m8VerifyLog.csv は追記のみ。同じ (日付, model) の行が既にあれば何もしない。
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
#   python scripts/dailyM8.py                 … JST当日を am で処理
#   MODE=pm python scripts/dailyM8.py         … JST当日を pm（展示込み）で処理
#   HD=20260808 python scripts/dailyM8.py     … 対象日を指定（試運転用）
#   M8_VERIFY_ONLY=1 …… 推論せず前日照合だけ行う（am のみ。pm では照合しないので何もしない）
import io
import os
import csv
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
SEED = 42
HGB_PARAMS = dict(max_leaf_nodes=7, learning_rate=0.03, min_samples_leaf=50,
                  max_iter=200, l2_regularization=1.0,
                  early_stopping=False, random_state=SEED)
W_LR = 0.3                 # LR の重み（残りが HGB）
CALIB_DAYS = 30            # isotonic 用の内側ホールドアウト日数
HIGH_N = 3                 # 「高」として記録する件数

PRED_DIR = os.environ.get("M8_PRED_DIR", os.path.join("predictions", "m8"))
V1_PREVIEW_DIR = os.environ.get("M8_V1_PREVIEW", "preview")   # 自前の直前情報（v1・毎時更新）
VERIFY_CSV = os.environ.get("M8_VERIFY_CSV", "m8VerifyLog.csv")
VERIFY_COLS = ["date", "model", "jcd", "rno", "p", "high", "y", "hit"]


def model_id(mode):
    return "%s-%s" % (MODEL_BASE, mode)


def pred_path(hd, mode):
    """am は従来どおり YYYYMMDD.json、pm は YYYYMMDD_pm.json。
    ファイル名を分けることで write-once をファイル単位のまま維持する。"""
    return os.path.join(PRED_DIR, "%s.json" % hd if mode == "am" else "%s_pm.json" % hd)


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
        "実行モード": mode,
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
    print("wrote %s model=%s races=%d high=%d（%s）展示 %d/%d 学習 %d件（〜%s）"
          % (out, model_id(mode), len(races), len(hi),
             " ".join("%s-%dR p=%.3f" % (r["jcd"], r["rno"], r["p"]) for r in hi),
             tenji_filled, tenji_slots, len(train), train.hd.max()))
    return True


def verify(prev_hd):
    """前日の am版・pm版の見立てを results/ と突合して m8VerifyLog.csv に追記する。
    片方しか無い日（pm を回していない日など）は在るぶんだけ照合する。"""
    n = 0
    for mode in MODES:
        n += verify_one(prev_hd, mode)
    return n


def verify_one(prev_hd, mode):
    """前日の predictions/m8（指定モード）と results/ を突合して m8VerifyLog.csv に追記する。
    追記済みかどうかは (date, model) で見る。am と pm は別行として並ぶ。"""
    path = pred_path(prev_hd, mode)
    if not os.path.exists(path):
        print("照合[%s]: %s が無い（この日この時間帯の見立ては出していない）→ 何もしない" % (mode, path))
        return 0
    with io.open(path, encoding="utf-8") as f:
        pred = json.load(f)
    mid = pred.get("model") or model_id(mode)
    done = set()
    if os.path.exists(VERIFY_CSV):
        with io.open(VERIFY_CSV, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                done.add((row.get("date"), row.get("model")))
    if (prev_hd, mid) in done:
        print("照合[%s]: %s / %s は既に %s にある → 追記しない" % (mode, prev_hd, mid, VERIFY_CSV))
        return 0
    res = F.load_results(prev_hd)
    if not res:
        print("照合[%s]: results/%s.json が無い（結果未取得）→ 追記しない。次回に持ち越す" % (mode, prev_hd))
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
    print("照合[%s]: %s / %s を %s に %d行追記。high判定 %d/%d 的中（着外率不明 %d件）"
          % (mode, prev_hd, mid, VERIFY_CSV, len(rows), hits, judged, unknown))
    return len(rows)


def count_tenji(pv):
    """previews（v2形）の展示タイム枠数と有効数を数える。0は「まだ走っていない」なので有効に数えない。"""
    slots = filled = 0
    for r in (pv or {}).get("previews") or []:
        for b in F.boats(r):
            slots += 1
            if F.exhibition_time(b) is not None:
                filled += 1
    return filled, slots


def v1_race_to_v2(r):
    """自前 preview/YYYYMMDD.json（v1）のレース1件を v2 previews の形に直す。

    キー対応は v1・v2 の実物を突き合わせて確認した（2026-08-09 の両ファイル）。
      レース: stadium_number→race_stadium_number / race_number→race_number /
              date→race_date / wind_speed→race_wind /
              wind_direction_number→race_wind_direction_number / wave_height→race_wave /
              weather_number→race_weather_number / air_temperature→race_temperature /
              water_temperature→race_water_temperature
      艇:     entry_number→racer_boat_number / course_number→racer_course_number /
              start_timing→racer_start_timing / exhibition_time→racer_exhibition_time /
              weight→racer_weight / weight_adjustment→racer_weight_adjustment /
              tilt_adjustment→racer_tilt_adjustment
    ※ M8 が実際に使うのは race_stadium_number / race_number / racer_boat_number /
      racer_exhibition_time の4つだけ。残りは v2 形を保つために写しているだけで、
      特徴量には一切入らない（M8_FEATURES に他の直前情報は無い）。
    ※ 展示タイムは正の値だけ有効。v1 側の 0・null は「まだ走っていない」なので
      None にして渡す（v2 の 0 ガードと同じ扱い → F.exhibition_time の注記）。
    """
    out = {}
    for a, b in (("stadium_number", "race_stadium_number"), ("race_number", "race_number"),
                 ("date", "race_date"), ("wind_speed", "race_wind"),
                 ("wind_direction_number", "race_wind_direction_number"),
                 ("wave_height", "race_wave"), ("weather_number", "race_weather_number"),
                 ("air_temperature", "race_temperature"),
                 ("water_temperature", "race_water_temperature")):
        out[b] = r.get(a)
    bs = []
    for x in r.get("racers") or []:
        y = {}
        for a, b in (("entry_number", "racer_boat_number"), ("course_number", "racer_course_number"),
                     ("start_timing", "racer_start_timing"), ("exhibition_time", "racer_exhibition_time"),
                     ("weight", "racer_weight"), ("weight_adjustment", "racer_weight_adjustment"),
                     ("tilt_adjustment", "racer_tilt_adjustment")):
            y[b] = x.get(a)
        try:
            y["racer_exhibition_time"] = float(y["racer_exhibition_time"])
        except (TypeError, ValueError):
            y["racer_exhibition_time"] = None
        if y["racer_exhibition_time"] is not None and y["racer_exhibition_time"] <= 0:
            y["racer_exhibition_time"] = None
        bs.append(y)
    out["boats"] = bs
    return out


def synth_previews(hd, base):
    """当日の previews を「自前 v1 の展示込み」に合成して返す（pm 専用。pv2/ には書かない）。

    上流 v2 の previews は当日のうちは更新されない（実測: JST 0時でも 276/1008 のまま。
    翌日に 1008/1008 の確定版になる）。夜の展示が入っているのは自前の
    preview/YYYYMMDD.json（v1・毎時更新。実測 1007/1008）なので、pm はこちらを素材にする。

    合成は上書きではなく重ね合わせ: v2 を土台にして、v1 に展示がある枠だけ差し替える。
    v2 にしか無いレースは残り、v1 にしか無いレースは足される（取りこぼしを作らないため）。
    """
    p = os.path.join(V1_PREVIEW_DIR, "%s.json" % hd)
    if not os.path.exists(p):
        print("WARN: %s が無い。pm だが v2 のまま推論する（展示は朝と同じ）" % p)
        return base
    try:
        with io.open(p, encoding="utf-8") as f:
            v1 = json.load(f)
    except Exception as e:
        print("WARN: %s が読めない（%s）。v2 のまま推論する" % (p, e))
        return base
    races = list((base or {}).get("previews") or [])
    idx = {}
    for i, r in enumerate(races):
        try:
            idx[(int(r["race_stadium_number"]), int(r["race_number"]))] = i
        except (KeyError, TypeError, ValueError):
            continue
    added = merged = 0
    for r1 in v1.get("直前情報") or []:
        r2 = v1_race_to_v2(r1)
        try:
            k = (int(r2["race_stadium_number"]), int(r2["race_number"]))
        except (TypeError, ValueError):
            continue
        if k not in idx:
            idx[k] = len(races)
            races.append(r2)
            added += 1
            continue
        old = races[idx[k]]
        by_w = {}
        for b in F.boats(old):
            try:
                by_w[int(b["racer_boat_number"])] = dict(b)
            except (KeyError, TypeError, ValueError):
                continue
        for b in r2["boats"]:
            try:
                w = int(b["racer_boat_number"])
            except (KeyError, TypeError, ValueError):
                continue
            # v1 に展示があればそれを採る。無ければ v2 のぶんを残す（消さない）
            if b.get("racer_exhibition_time") is None and w in by_w:
                b = dict(b)
                b["racer_exhibition_time"] = by_w[w].get("racer_exhibition_time")
            by_w[w] = b
        new = dict(old)
        new["boats"] = [by_w[w] for w in sorted(by_w)]
        races[idx[k]] = new
        merged += 1
    obj = {"previews": races}
    bf, bs = count_tenji(base)
    nf, ns = count_tenji(obj)
    print("pm素材: v1 %s を合成（レース 差し替え%d件・追加%d件）展示 %d/%d → %d/%d（取得時刻 %s）"
          % (p, merged, added, bf, bs, nf, ns, v1.get("取得時刻") or "?"))
    return obj


def use_v1_previews(hd, base):
    """合成した previews を、pv2/ に書かずに F.build から見えるようにする。
    F.build は load_pv2 経由でしか素材を読まないので、対象日の previews だけ
    読み口を差し替える（他の日・programs は元のまま素通し）。"""
    obj = synth_previews(hd, base)
    if obj is base:
        return base
    orig = F.load_pv2

    def patched(kind, d):
        if kind == "previews" and d == hd:
            return obj
        return orig(kind, d)

    F.load_pv2 = patched
    return obj


def finalize_prev_previews(prev_hd):
    """前日の v2 previews を取り直し、展示の充填が増えていれば確定版で上書きする（am 専用）。

    上流 v2 は当日中は展示が埋まらず、翌日に確定版になる。pv2/ は write-once なので
    放っておくと「当日朝に取った未確定版」が永久に残り、以後の学習素材が痩せる。
    朝の照合のついでに前日ぶんだけ確定版へ差し替える。
    増えていない・取れないときは元のバイト列をそのまま書き戻す（＝差分ゼロ）。"""
    p = F.pv2_path("previews", prev_hd)
    old = None
    if os.path.exists(p):
        with io.open(p, "rb") as f:
            old = f.read()
    before = count_tenji(F.load_pv2("previews", prev_hd))
    if old is not None:
        os.remove(p)
    ok = F.fetch_pv2("previews", prev_hd)
    after = count_tenji(F.load_pv2("previews", prev_hd)) if ok and os.path.exists(p) else (-1, -1)
    if old is None:
        print("前日previews: %s（展示 %d/%d）"
              % ("新規取得" if ok else "取れなかった（未配信か通信断）", max(after[0], 0), max(after[1], 0)))
        return bool(ok)
    if after[0] > before[0]:
        print("前日previews確定版化: %d→%d（枠 %d）%s" % (before[0], after[0], after[1], p))
        return True
    if old is not None:
        with io.open(p, "wb") as f:
            f.write(old)
    if not ok:
        print("前日previews: 取り直せなかった（未配信か通信断）→ 触らない（展示 %d/%d のまま）"
              % before)
    else:
        print("前日previews: 充填が増えていない（%d/%d）→ 触らない" % before)
    return False


def main():
    mode = (os.environ.get("MODE") or "am").strip().lower() or "am"
    if mode not in MODES:
        raise SystemExit("ERROR: MODE は %s のいずれか（受け取った値: %r）" % ("/".join(MODES), mode))
    hd = (os.environ.get("HD") or "").strip() or F.jst_today().strftime("%Y%m%d")
    prev_hd = (datetime.datetime.strptime(hd, "%Y%m%d").date() - datetime.timedelta(days=1)).strftime("%Y%m%d")
    print("=== dailyM8 MODE=%s 対象日 %s（前日 %s） ===" % (mode, hd, prev_hd))

    # 1) 前日照合（推論より先にやる。推論が落ちても照合は残る）
    #    照合するのは am だけ。pm の時点では当日ぶんの結果が出揃っておらず、
    #    前日ぶんは朝に照合済みなので、二重に走らせる意味がない。
    t_verify = 0.0
    if mode == "am":
        t0 = time.time()
        finalize_prev_previews(prev_hd)
        verify(prev_hd)
        t_verify = time.time() - t0
    else:
        print("照合: MODE=pm では行わない（翌朝の am 実行が am/pm 両方をまとめて照合する）")

    if os.environ.get("M8_VERIFY_ONLY"):
        print("M8_VERIFY_ONLY=1 のため推論はしない")
        return

    out = pred_path(hd, mode)
    if os.path.exists(out):
        print("SKIP: %s は既にある。学習も推論もしない（write-once）" % out)
        return

    # 2) 素材と特徴量
    #    pm は上流 v2（当日は更新されない）ではなく自前 v1 の展示を重ねた素材で推論する。
    #    合成は F.build を呼ぶ前に済ませておく（pv2/ には何も書かない）。
    t0 = time.time()
    F.ensure_pv2(list(F.daterange(F.HIST_FIRST, hd)))
    pv = F.load_pv2("previews", hd) or {}
    if mode == "pm":
        pv = use_v1_previews(hd, pv)
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

    # 展示タイムがどれだけ出ているか（推論に使った素材そのもので数える。
    # 0は「まだ走っていない」の意味なので有効に数えない）
    filled, slots = count_tenji(pv)
    write_predictions(hd, mode, target, p, raw, filled, slots, train)
    print("所要: 照合 %.1fs / pv2取得 %.1fs / 特徴量 %.1fs / 学習+推論 %.1fs"
          % (t_verify, t_fetch, t_feat, t_model))


if __name__ == "__main__":
    main()
