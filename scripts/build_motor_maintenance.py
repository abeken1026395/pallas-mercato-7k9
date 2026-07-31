#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_motor_maintenance.py

モーター整備 一覧 の基底テーブルを作る。
仕様: motor_maintenance_spec.md（節 × 場 × 機番 × 登番 を1行）

HTMLは作らない。仕様§7「3の時点で立ち止まる」に従い、
基底テーブルと検証用の統計だけを出す。

入力: docs/data/motorParts.json, docs/data/motorHistory.json,
      docs/players/female.json
出力: --out（既定 localdata/motor_maintenance_base.json / .csv）

実行:
  py scripts/build_motor_maintenance.py
"""

import argparse
import csv
import json
import os
import random
import re
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta

# データ窓は motorParts の実データから毎回求める。固定値にすると、
# 日次収集で窓が伸びたときに「不完全節」の判定が静かに壊れる。
WINDOW_START = None         # データ窓の初日（motorParts の最小開催日）
WINDOW_END = None           # データ窓の最終日
LOST_DAYS = {"20260713", "20260714"}   # 公式から再取得不可の欠測日

REPORT = []


def say(*a):
    line = " ".join(str(x) for x in a)
    print(line)
    REPORT.append(line)


def head(t):
    say("\n" + "=" * 72)
    say(t)
    say("=" * 72)


def d2o(s):
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def daydiff(a, b):
    return (d2o(a) - d2o(b)).days


# --- §1 節名の補完 --------------------------------------------------------
def build_blocks(dates):
    """日付集合を「2日以上の空きで切る」ブロックに分ける。1日の空きは切らない。"""
    ds = sorted(dates)
    blocks, cur = [], [ds[0]]
    for prev, nxt in zip(ds, ds[1:]):
        if daydiff(nxt, prev) >= 3:      # 空き2日以上 = 間に2日以上の非開催日
            blocks.append(cur)
            cur = [nxt]
        else:
            cur.append(nxt)
    blocks.append(cur)
    return blocks


def assign_sessions(parts_days, sessions_by_venue):
    """
    (jcd, 開催日) -> (節キー, 節名, 出所) を返す。

    motorHistory.sessions の開催日は「節の最終日」（桐生 07/19・07/27 と
    motorParts のブロック 0715-0719・0723-0727 が一致することで確認）。
    よってブロック末日以降で最も近い節を当てる。
    """
    mapping = {}
    src_count = Counter()
    for jcd, days in parts_days.items():
        sess = sorted(sessions_by_venue.get(jcd, []))   # [(開催日, 節名, motors)]
        for blk in build_blocks(days):
            s, e = blk[0], blk[-1]
            cand = next(((d, n, m) for d, n, m in sess if d >= e), None)
            if cand is None:
                # 節名が引けない理由は2種類ある。一括りにしない。
                #  未完了: 窓の右端で節がまだ終わっていない。motorHistory は
                #          節完結時に記録するので、載っていないのが正常。
                #  不明  : 完結しているはずなのに突合できない。要調査。
                if (jcd, s, e) in ABORTED:
                    src = "中止"          # 節が異常終了。記録が無いのが正常
                elif e == WINDOW_END:
                    src = "未完了"
                else:
                    src = "不明"
                key, name = f"{jcd}@{s}", ""
            else:
                d, n, m = cand
                # 節末日が窓で切られている場合は節の最終日が窓の外に出る
                if s <= d <= e or (e == WINDOW_END and daydiff(d, e) <= 7):
                    key, name, src = f"{jcd}@{d}", n, "history"
                else:
                    key, name, src = f"{jcd}@{s}", "", "gap推定"
            src_count[src] += 1
            for day in blk:
                mapping[(jcd, day)] = (key, name, src, s, e, tuple(blk))
    return mapping, src_count


def setsu_day(blk, day):
    """節内何日目か（1始まり）。絶対日付は節をまたいで比較できないため併記する。

    窓の初日で左が切れている節は、実際の開始日が窓の外にあるので
    「何日目」が確定しない。その場合は None を返す（0 を入れない）。
    """
    if blk[0] == WINDOW_START:
        return None
    return blk.index(day) + 1


# 整備規模（derived）。実データの共起から機械的に決めた規則:
#   単独率が高く点数の小さい部品   … リング81.5% キャブ84.3% ギヤ81.0% 電気72.4%
#   束でしか出ず点数の大きい部品   … ピストン18.1% シリンダ15.0%
# ギヤ（ギヤケース）は部品としては大物だが、実データでは単独率81.0%・
# 平均点数1.37 で完全に軽微側の挙動。部品知識ではなくデータに従って軽微に置く。
# シャフト(n=12)・キャリボ(n=9)は件数が足りず、データからは判断できない。
# 束で出る側に寄せているが、これは部品知識に基づく判断であることを明記する。
HEAVY_PARTS = {"ピストン", "シリンダ", "シャフト", "キャリボ"}

# 中止・打ち切りで終わった節の手動フラグ。(jcd, ブロック開始日, ブロック終了日)。
# 自動判別するには「最終日にKファイル上の優勝戦があるか」を見る必要があり、
# ビルドにK依存を持ち込むことになるので採らない。確認できた分だけ手で持つ。
# 「不明」のまま出すと、次に見た人が調べれば分かるものと誤解する。
ABORTED = {
    ("09", "20260727", "20260728"):
        "07/28にR10で打ち切り、優勝戦が行われないまま開催終了（k260728.lzhで確認）",
}


# --- §2 展示タイムの正規化 ------------------------------------------------
def mean(xs):
    return sum(xs) / len(xs) if xs else None


def normalize(records):
    """正規化展示（場×日基準）と 正規化展示_race（同レース他5艇基準）を各行に付ける。

    主系は (場,日付)。副系のレース単位は列として持つが、検定には使わない。
    理由（場の水質による切り替えは根拠が無いので採らない）:

    1. 番組編成は節の中で系統的に変化する。初日は予選、最終日は準優・優勝戦。
       レース単位で正規化すると、この「節の進行に伴うメンバー構成の変化」を
       基準側に取り込む。短縮秒が測りたいのはまさに節の進行に沿った変化なので、
       測りたいものを基準に混ぜることになる。

    2. さらに悪いことに、これは選択効果として測定対象と同じ向きに効く。
       節が進むと足の上がった選手ほど準優・優勝戦に上がる。そこは他5艇も
       速いので、レース単位の基準は自動的に厳しくなる。つまり
       「改善した選手ほど改善が打ち消される」形の系統バイアスであって、
       ランダム誤差ではない。

    2方式の r=0.71〜0.78 という乖離は「一本化の根拠が薄い」のではなく、
    副系の側に既知の欠陥がある、と整理する。乖離が大きい場ほど番組編成の
    動きが大きい可能性がある。
    """
    by_day = defaultdict(list)
    by_race = defaultdict(list)
    bad = 0
    for r in records:
        try:
            r["_t"] = float(r["展示タイム"])
        except (ValueError, TypeError):
            r["_t"] = None
            bad += 1
            continue
        by_day[(r["jcd"], r["開催日"])].append(r["_t"])
        by_race[(r["jcd"], r["開催日"], r["rno"])].append(r["_t"])

    day_base = {k: mean(v) for k, v in by_day.items()}
    for r in records:
        if r["_t"] is None:
            r["_n_day"] = r["_n_race"] = None
            continue
        r["_n_day"] = day_base[(r["jcd"], r["開催日"])] - r["_t"]
        others = by_race[(r["jcd"], r["開催日"], r["rno"])]
        if len(others) >= 2:
            # 自分を除く平均。自分を含めると基準に1/6混入して差が縮む。
            r["_n_race"] = (sum(others) - r["_t"]) / (len(others) - 1) - r["_t"]
        else:
            r["_n_race"] = None
    return bad, day_base


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = mean(xs), mean(ys)
    sxy = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    sxx = sum((a - mx) ** 2 for a in xs)
    syy = sum((b - my) ** 2 for b in ys)
    if sxx <= 0 or syy <= 0:
        return None
    return sxy / (sxx * syy) ** 0.5


# --- §3 節内の推移 --------------------------------------------------------
def slope(idx, ys):
    n = len(idx)
    if n < 2:
        return None
    mi, my = mean(idx), mean(ys)
    den = sum((i - mi) ** 2 for i in idx)
    if den <= 0:
        return None
    return sum((i - mi) * (y - my) for i, y in zip(idx, ys)) / den


def early_late(daily):
    """daily: [(日付, 値)] 日付順。序盤=最初の2日平均 / 終盤=最後の2日平均。"""
    vals = [v for _, v in daily]
    return mean(vals[:2]), mean(vals[-2:])


# --- 部品交換のパース -----------------------------------------------------
MULT = {"１": 1, "２": 2, "３": 3, "４": 4, "５": 5, "６": 6}


def parse_parts(s):
    """'ピストン×２ リング×４ シリンダ' -> ([部品名...], 点数, [[名, 個数]...])"""
    names, pts, pairs = [], 0, []
    for tok in s.split():
        m = re.match(r"^(.+?)×([0-9０-９])$", tok)
        if m:
            nm = m.group(1)
            d = m.group(2)
            n = MULT.get(d, int(d) if d.isdigit() else 1)
        else:
            nm, n = tok, 1
        names.append(nm)
        pairs.append([nm, n])
        pts += n
    return names, pts, pairs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=r"C:\Users\USER\boatrace")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    D = os.path.join(args.repo, "docs")
    out = args.out or os.path.join(args.repo, "localdata", "motor_maintenance_base")

    mp = json.load(open(os.path.join(D, "data", "motorParts.json"), encoding="utf-8"))
    mh = json.load(open(os.path.join(D, "data", "motorHistory.json"), encoding="utf-8"))
    female = set(json.load(open(os.path.join(D, "players", "female.json"), encoding="utf-8")))

    global WINDOW_START, WINDOW_END
    all_recs = mp["records"]
    # 機番か登番が空の行は (場,機番,登番) に割り当てられない。捨てるが黙って捨てない。
    def usable(r):
        return bool(str(r["モーターNo"]).strip() and str(r["登番"]).strip())
    recs = [r for r in all_recs if usable(r)]
    dropped = [r for r in all_recs if not usable(r)]
    WINDOW_START = min(r["開催日"] for r in recs)
    WINDOW_END = max(r["開催日"] for r in recs)

    head("§0 入力")
    say(f"  motorParts.updated : {mp['updated']}")
    say(f"  レコード           : {len(all_recs):,}")
    if dropped:
        say(f"  機番/登番が空で除外: {len(dropped):,}")
        say(f"    日別: {dict(sorted(Counter(r['開催日'] for r in dropped).items()))}")
        say(f"    場別: {dict(sorted(Counter(r['場名'] for r in dropped).items()))}")
    say(f"  データ窓           : {WINDOW_START} - {WINDOW_END}"
        f"（{daydiff(WINDOW_END, WINDOW_START)+1}日）")

    # ---------------- §1 ----------------
    head("§1 節名の補完")
    sess_by_venue = defaultdict(list)
    sess_motors = {}
    for s in mh["sessions"]:
        sess_by_venue[s["jcd"]].append((s["開催日"], s["節名"], s["motors"]))
        sess_motors[f"{s['jcd']}@{s['開催日']}"] = s["motors"]

    parts_days = defaultdict(set)
    for r in recs:
        parts_days[r["jcd"]].add(r["開催日"])

    mapping, src_blocks = assign_sessions(parts_days, sess_by_venue)
    row_src = Counter(mapping[(r["jcd"], r["開催日"])][2] for r in recs)
    total = sum(row_src.values())
    say(f"  ブロック単位の出所: {dict(src_blocks)}")
    say(f"  行単位の出所 (n={total:,}):")
    for k, v in row_src.most_common():
        say(f"    {k:8s} {v:6,}  ({v/total*100:5.1f}%)")

    # ---------------- §2 ----------------
    head("§2 展示タイムの正規化")
    bad, day_base = normalize(recs)
    say(f"  展示タイムが数値化できない行: {bad:,} / {len(recs):,}")
    bases = sorted(day_base.values())
    say(f"  (場,日)基準値: {len(day_base)} 通り / 最小 {bases[0]:.3f} / "
        f"中央 {bases[len(bases)//2]:.3f} / 最大 {bases[-1]:.3f}")
    say(f"  → 日によって基準が {bases[-1]-bases[0]:.3f} 秒動く。正規化は必須。")

    ok = [r for r in recs if r.get("_n_day") is not None and r.get("_n_race") is not None]
    say(f"\n  2方式の相関（行単位, n={len(ok):,}）: r = {pearson([r['_n_day'] for r in ok], [r['_n_race'] for r in ok]):.4f}")
    say("  場別の相関（r 昇順・下位8場）:")
    per_v = defaultdict(list)
    for r in ok:
        per_v[(r["jcd"], r["場名"])].append(r)
    rows_v = []
    for (jcd, nm), rs in per_v.items():
        rr = pearson([x["_n_day"] for x in rs], [x["_n_race"] for x in rs])
        if rr is not None:
            rows_v.append((rr, jcd, nm, len(rs)))
    rows_v.sort()
    for rr, jcd, nm, n in rows_v[:8]:
        say(f"    {jcd} {nm:6s} r={rr:.4f}  n={n:,}")
    say(f"    （最高: {rows_v[-1][1]} {rows_v[-1][2]} r={rows_v[-1][0]:.4f}）")

    # ---------------- §3/§4 基底テーブル ----------------
    head("§3 節内の推移 → 基底テーブル")
    groups = defaultdict(list)
    for r in recs:
        m = mapping[(r["jcd"], r["開催日"])]
        groups[(m[0], r["jcd"], r["モーターNo"], r["登番"])].append((r,) + m[1:])

    # 節内日ごとの露出補正用カウンタ。
    # 生ヒストグラムは分母が日ごとに縮むのを無視している（6日目が少ないのは
    # 6日目に交換が少ないからではなく、6日目まで走っている機が少ないから）。
    # 分母は「日数>=N」ではなく「その日が実データに存在する (行,日) の数」。
    # 日数で代用すると、窓の左端で切れた節が再混入する。
    exp_denom = Counter()      # (行,日) の観測数
    exp_days = Counter()       # そのうち交換が1件以上あった (行,日) の数
    exp_events = Counter()     # 交換イベント件数（1日に複数種の交換があると >1）

    # 「準優前に手を入れる」を見るには節頭からの日数では駄目。準優・優勝戦は
    # 節の「末尾から」固定位置にあり、節の長さは4〜7日とばらつくので、
    # 節頭で揃えると信号が滲む。両端とも切れていない節だけで末尾から数える。
    end_denom = Counter()
    end_days = Counter()
    end_light = Counter()   # その日の交換が軽微のみ
    end_heavy = Counter()   # その日の交換に大掛かり部品を含む

    dup_parts = 0
    table = []
    for (skey, jcd, mno, toban), items in groups.items():
        rs = [i[0] for i in items]
        name, src, bs, be, blk = items[0][1], items[0][2], items[0][3], items[0][4], items[0][5]

        by_day = defaultdict(list)
        for r in rs:
            by_day[r["開催日"]].append(r)
        days = sorted(by_day)

        daily_day, daily_race = [], []
        for d in days:
            v = [r["_n_day"] for r in by_day[d] if r["_n_day"] is not None]
            w = [r["_n_race"] for r in by_day[d] if r["_n_race"] is not None]
            if v:
                daily_day.append((d, mean(v)))
            if w:
                daily_race.append((d, mean(w)))

        # 部品交換: 同一日の同一文字列が複数レースで重複するかを見る
        names_all, pts_all, events = [], 0, []
        seen_day = set()
        for r in sorted(rs, key=lambda x: (x["開催日"], x["rno"])):
            s = r["部品交換"].strip()
            if not s:
                continue
            if (r["開催日"], s) in seen_day:
                dup_parts += 1
                continue
            seen_day.add((r["開催日"], s))
            nm, pt, pairs = parse_parts(s)
            names_all += nm
            pts_all += pt
            events.append({"日付": r["開催日"], "節内日": setsu_day(blk, r["開催日"]),
                           "rno": r["rno"], "部品": pairs, "点数": pt})

        # プロペラ「新」はレース単位の別系統。点数には混ぜない。
        prop = []
        seen_p = set()
        for r in sorted(rs, key=lambda x: (x["開催日"], x["rno"])):
            if r["プロペラ"].strip() and r["開催日"] not in seen_p:
                seen_p.add(r["開催日"])
                prop.append({"日付": r["開催日"], "節内日": setsu_day(blk, r["開催日"])})

        # 左端が切れた節は 1〜2日目を観測していない。分子にも分母にも入れない。
        ev_by_day = Counter(e["日付"] for e in events)
        if blk[0] != WINDOW_START:
            for d in days:
                sd = setsu_day(blk, d)
                exp_denom[sd] += 1
                if ev_by_day.get(d):
                    exp_days[sd] += 1
                    exp_events[sd] += ev_by_day[d]

        # 末尾からの逆算は、右端も切れていない節でしか意味がない
        # （右端が切れていると本当の最終日が窓の外にある）。
        if blk[0] != WINDOW_START and blk[-1] != WINDOW_END:
            heavy_by_day = defaultdict(bool)
            for e in events:
                if HEAVY_PARTS & {p[0] for p in e["部品"]}:
                    heavy_by_day[e["日付"]] = True
            for d in days:
                ed = len(blk) - blk.index(d)      # 1 = 最終日
                end_denom[ed] += 1
                if ev_by_day.get(d):
                    end_days[ed] += 1
                    if heavy_by_day[d]:
                        end_heavy[ed] += 1
                    else:
                        end_light[ed] += 1

        ndays = len(days)
        row = {
            "節キー": skey, "節名": name, "節名_出所": src,
            "節名_注記": ABORTED.get((jcd, bs, be), ""),
            "jcd": jcd, "場名": rs[0]["場名"],
            "開始日": days[0], "終了日": days[-1], "日数": ndays,
            "登番": int(toban), "氏名": rs[0]["氏名"], "女子": toban in female,
            "機番": int(mno), "走数": len(rs),
            "交換点数": pts_all, "交換部品": sorted(set(names_all)),
            "交換イベント": events, "プロペラ新": prop,
            "整備規模": ("大掛かり" if HEAVY_PARTS & set(names_all)
                         else ("軽微" if names_all else "")),
            "節日数": len(blk),
            "節末2連率": sess_motors.get(skey, {}).get(str(int(mno)),
                          sess_motors.get(skey, {}).get(mno)),
            "欠測あり": days[0] == WINDOW_START,
            "不完全節": days[0] == WINDOW_START or days[-1] == WINDOW_END,
        }

        if ndays >= 4 and len(daily_day) >= 4:
            e0, l0 = early_late(daily_day)
            row["展示_序盤"] = round(e0, 4)
            row["展示_終盤"] = round(l0, 4)
            row["短縮秒"] = round(l0 - e0, 4)     # 正規化済み → 正 = 改善
            row["傾き"] = round(slope(list(range(len(daily_day))),
                                     [v for _, v in daily_day]), 5)
            if len(daily_race) >= 4:
                e1, l1 = early_late(daily_race)
                row["短縮秒_race"] = round(l1 - e1, 4)
            else:
                row["短縮秒_race"] = None
        else:
            row["展示_序盤"] = row["展示_終盤"] = None
            row["短縮秒"] = row["傾き"] = row["短縮秒_race"] = None
        table.append(row)

    say(f"  基底テーブル行数            : {len(table):,}")
    say(f"  部品交換の日内重複(除外済み): {dup_parts:,}")
    measurable = [r for r in table if r["短縮秒"] is not None]
    say(f"  日数>=4 で短縮秒が出た行    : {len(measurable):,}")
    say(f"    うち 不完全節=false       : {sum(1 for r in measurable if not r['不完全節']):,}")
    say(f"    うち 節名_出所=history    : {sum(1 for r in measurable if r['節名_出所']=='history'):,}")
    say(f"  日数の分布: {dict(sorted(Counter(r['日数'] for r in table).items()))}")
    say(f"  走数の分布(短縮秒あり行): 中央値 "
        f"{sorted(r['走数'] for r in measurable)[len(measurable)//2]}, "
        f"最小 {min(r['走数'] for r in measurable)}, 最大 {max(r['走数'] for r in measurable)}")
    say(f"  節末2連率が引けた行         : {sum(1 for r in table if r['節末2連率'] is not None):,} / {len(table):,}")

    withp = [r for r in table if r["交換点数"] > 0]
    say(f"\n  交換ありの行                : {len(withp):,} ({len(withp)/len(table)*100:.1f}%)")
    say(f"  整備規模の内訳              : {dict(Counter(r['整備規模'] for r in withp))}")
    ev = [e for r in table for e in r["交換イベント"]]
    say(f"  交換イベント                : {len(ev):,} 件")
    say(f"    節内日が確定した件数      : {sum(1 for e in ev if e['節内日'] is not None):,}"
        f"（残りは窓の左端で節の開始日が不明）")
    say(f"    節内日の生ヒストグラム    : "
        f"{dict(sorted(Counter(e['節内日'] for e in ev if e['節内日']).items()))}")
    say(f"  プロペラ新のある行          : {sum(1 for r in table if r['プロペラ新']):,}")

    head("節内日の交換率（露出補正）")
    say("  分母 = その節内日が実データに存在する (節×機×登番, 日) の数。")
    say("  左端が切れた節は 1〜2日目を観測していないので分子・分母とも除外。")
    say(f"\n  {'節内日':>5} | {'観測(行,日)':>11} | {'交換あり':>8} | {'交換率':>7} | {'イベント':>7}")
    rate_rows = []
    for sd in sorted(exp_denom):
        den, num, evn = exp_denom[sd], exp_days[sd], exp_events[sd]
        rate = num / den * 100
        rate_rows.append({"節内日": sd, "観測": den, "交換あり": num,
                          "交換率": round(rate, 2), "イベント": evn})
        say(f"  {sd:>5} | {den:>11,} | {num:>8,} | {rate:>6.2f}% | {evn:>7,}")
    say(f"\n  生ヒストグラムは分母の縮みを見ていない。補正後の形が実際の傾向。")
    say(f"  節内日が確定しなかった交換イベント: "
        f"{sum(1 for e in ev if e['節内日'] is None):,} 件（すべて左端切れ）")
    say("  → 左端切れでは初日の交換が優先的に欠落する。"
        "「初日より2日目が多い」は現時点では結論にできない。")

    say("\n  --- 節末からの逆算（両端とも切れていない節のみ）---")
    say("  準優・優勝戦は節の末尾から固定位置。節の長さが4〜7日とばらつくので、")
    say("  節頭で揃えると『準優前に手を入れる』かどうかは滲んで見えない。")
    say(f"\n  {'節末から':>7} | {'観測(行,日)':>11} | {'交換あり':>8} | {'交換率':>7}"
        f" | {'軽微':>6} | {'大掛かり':>8}")
    end_rows = []
    for ed in sorted(end_denom):
        den, num = end_denom[ed], end_days[ed]
        lg, hv = end_light[ed], end_heavy[ed]
        lab = "最終日" if ed == 1 else f"{ed-1}日前"
        end_rows.append({"節末から": ed, "ラベル": lab, "観測": den,
                         "交換あり": num, "交換率": round(num / den * 100, 2),
                         "軽微": lg, "大掛かり": hv,
                         "軽微率": round(lg / den * 100, 2),
                         "大掛かり率": round(hv / den * 100, 2)})
        say(f"  {lab:>7} | {den:>11,} | {num:>8,} | {num/den*100:>6.2f}%"
            f" | {lg/den*100:>5.2f}% | {hv/den*100:>7.2f}%")
    say(f"\n  軽微 計 {sum(end_light.values()):,} / 大掛かり 計 {sum(end_heavy.values()):,}")
    say("  言えるのは2点だけ: (1)最終日の落ち込みは大掛かりの方が深い"
        "(中盤比 軽微≈0.63 / 大掛かり≈0.29)、(2)大掛かりは節の早い側に寄る。")
    say("  日ごとの上下は件数の揺れと区別できない。特定の日を『ピーク』とは書かないこと。")

    # ---------------- §7-4 分布 ----------------
    head("§7-4 短縮秒の分布")
    vals = sorted(r["短縮秒"] for r in measurable)
    n = len(vals)

    def q(p):
        return vals[int(n * p)]
    say(f"  n={n:,}  最小 {vals[0]:+.3f}  Q1 {q(.25):+.3f}  中央 {q(.5):+.3f}  "
        f"Q3 {q(.75):+.3f}  最大 {vals[-1]:+.3f}")
    say(f"  平均 {mean(vals):+.4f}")
    iqr = q(.75) - q(.25)
    lo, hi = q(.25) - 1.5 * iqr, q(.75) + 1.5 * iqr
    say(f"  外れ値(1.5IQR外): {sum(1 for v in vals if v < lo or v > hi):,} 件 "
        f"(境界 {lo:+.3f} / {hi:+.3f})")
    say(f"  正(改善)の割合: {sum(1 for v in vals if v > 0)/n*100:.1f}%")

    rr = [r for r in measurable if r["短縮秒_race"] is not None]
    if rr:
        say(f"  2方式の短縮秒の相関: r = "
            f"{pearson([r['短縮秒'] for r in rr], [r['短縮秒_race'] for r in rr]):.4f} (n={len(rr):,})")

    # ---------------- 検証: 個人差は偶然を超えるか ----------------
    #
    # 検定に使うのは主系（短縮秒 = (場,日付) 正規化）のみ。副系（短縮秒_race）は
    # 検定に一切かけない。2方式それぞれで p を出すと「良い方を採る」余地が生まれ、
    # それは検定ではなく選択（多重比較）になるため。副系は食い違う行を個別に
    # 見るための材料に用途を限定する。
    head("検証 — 短縮秒に個人差があるか（並べ替え検定・主系のみ）")

    def between_var(groups_):
        gm = [mean(v) for v in groups_.values()]
        return mean([(g - mean(gm)) ** 2 for g in gm])

    def perm_test(groups_, n_perm=10000, seed=20260731):
        """群サイズを保ったまま値を入れ替え、選手間分散の帰無分布を作る。"""
        obs = between_var(groups_)
        pool = [v for vs in groups_.values() for v in vs]
        sizes = [len(v) for v in groups_.values()]
        rnd = random.Random(seed)
        null = []
        for _ in range(n_perm):
            rnd.shuffle(pool)
            i, g = 0, {}
            for j, s in enumerate(sizes):
                g[j] = pool[i:i + s]
                i += s
            null.append(between_var(g))
        null.sort()
        p = (sum(1 for x in null if x >= obs) + 1) / (len(null) + 1)
        return obs, null[len(null) // 2], p

    by_racer = defaultdict(list)
    for r in measurable:
        by_racer[r["登番"]].append(r["短縮秒"])
    multi = {k: v for k, v in by_racer.items() if len(v) >= 2}
    say(f"  選手数 {len(by_racer):,} / うち2行以上 {len(multi):,} "
        f"({sum(len(v) for v in multi.values()):,}行)")

    # (a) n>=2 の選手だけ。n=1 の選手は観測側でも帰無側でも
    #     「群平均 = その1行の値」で同じ挙動になり、検定に情報を足さない。
    #     参考として全選手版も併記し、希釈の有無を数字で示す。
    if len(multi) >= 10:
        obs, med, p = perm_test(multi)
        say(f"\n  (a) n>=2 の {len(multi)}人のみ")
        say(f"      観測の選手間分散 {obs:.6f} / 帰無中央値 {med:.6f} / 比 {obs/med:.3f}")
        say(f"      p = {p:.4f}")

        obs2, med2, p2 = perm_test(by_racer)
        say(f"  (参考) 全 {len(by_racer):,}人（n=1 を含む）")
        say(f"      観測 {obs2:.6f} / 帰無中央値 {med2:.6f} / 比 {obs2/med2:.3f} / p = {p2:.4f}")

        # (b) 平均への回帰を落とした残差で同じ検定。
        #     短縮秒 = 終盤 − 序盤 は、序盤がたまたま悪く出た機ほど上がる成分を
        #     必ず含む。この成分は選手間でランダムに散るので選手間分散を押し下げ、
        #     観測値が帰無中央値を下回る原因になりうる。序盤を共変量に取り、
        #     残差 = 短縮秒 − (a + b*序盤) で同じ検定を行う。
        #     回帰は測定可能な全1,408行で当てる（群構造と独立に推定するため）。
        xs = [r["展示_序盤"] for r in measurable]
        ys = [r["短縮秒"] for r in measurable]
        b = slope(xs, ys)
        a = mean(ys) - b * mean(xs)
        rxy = pearson(xs, ys)
        say(f"\n  (b) 平均への回帰の大きさ: 短縮秒 ~ 序盤 の傾き b = {b:+.4f}, r = {rxy:+.4f}")
        say(f"      → 序盤の分散が短縮秒の分散の {rxy**2*100:.1f}% を説明する")

        resid_by_racer = defaultdict(list)
        for r in measurable:
            resid_by_racer[r["登番"]].append(r["短縮秒"] - (a + b * r["展示_序盤"]))
        rmulti = {k: v for k, v in resid_by_racer.items() if len(v) >= 2}
        obs3, med3, p3 = perm_test(rmulti)
        say(f"      残差での検定（n>=2 の {len(rmulti)}人）")
        say(f"      観測 {obs3:.6f} / 帰無中央値 {med3:.6f} / 比 {obs3/med3:.3f}")
        say(f"      p = {p3:.4f}")
    else:
        say("  2行以上の選手が少なすぎて検定できない")

    # ---------------- 出力 ----------------
    with open(out + ".json", "w", encoding="utf-8") as f:
        json.dump({"note": "モーター整備 基底テーブル。仕様 motor_maintenance_spec.md。"
                           "短縮秒は正規化済み・正=改善。4日未満は null。",
                   "window": {"from": WINDOW_START, "to": WINDOW_END},
                   "rows": table}, f, ensure_ascii=False, indent=1)
    cols = ["節キー", "節名", "節名_出所", "jcd", "場名", "開始日", "終了日", "日数",
            "節日数", "登番", "氏名", "女子", "機番", "走数", "交換点数", "交換部品",
            "整備規模", "展示_序盤", "展示_終盤", "短縮秒", "短縮秒_race", "傾き",
            "節末2連率", "欠測あり", "不完全節"]
    with open(out + ".csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in table:
            r2 = dict(r)
            r2["交換部品"] = " ".join(r2["交換部品"])
            w.writerow(r2)
    say(f"\n  出力(非公開): {out}.json / {out}.csv")

    # ---------------- 公開データ ----------------
    # 短縮秒・展示_序盤・展示_終盤・傾き・短縮秒_race は公開しない。
    # 計算は正しいが解釈が支持されていないため（p=0.25 は未決）。
    # 蓄積後にやり直せるよう localdata 側には残す。
    PUBLIC = ["節名", "節名_出所", "節名_注記", "jcd", "場名", "開始日", "終了日", "日数",
              "節日数", "登番", "氏名", "女子", "機番", "走数", "交換点数", "交換部品",
              "交換イベント", "プロペラ新", "整備規模", "節末2連率", "欠測あり", "不完全節"]
    # 空配列・false・0 は書き出さない（ページ側で既定値として扱う）。
    # 2,235行×日本語キーの繰り返しがファイルサイズの大半を占めるため。
    DROP_IF_EMPTY = {"交換部品", "交換イベント", "プロペラ新", "女子",
                     "欠測あり", "不完全節", "交換点数", "整備規模", "節名_注記"}
    pub_rows = [{k: r[k] for k in PUBLIC
                 if not (k in DROP_IF_EMPTY and not r[k])} for r in table]
    pub = {
        "updated": mp["updated"],
        "source": "boatrace.jp公式 直前情報（部品交換）＋ 節完結時点のモーター2連率",
        "window": {"from": WINDOW_START, "to": WINDOW_END},
        "note": "節×場×機番×登番 を1行とする整備記録。実データのみ・推測なし。"
                "部品交換は場の記録であり、誰の判断かはデータからは分からない。",
        "節内日交換率": rate_rows,
        "節末逆算交換率": end_rows,
        "節内日不明の交換件数": sum(1 for e in ev if e["節内日"] is None),
        "整備規模の定義": "ピストン・シリンダ・シャフト・キャリボのいずれかを含む行を"
                          "「大掛かり」、それ以外の交換を「軽微」とする機械的な区分。"
                          "実データの共起（単独率）に基づく。シャフト12件・キャリボ9件は"
                          "件数が少なく、この2つの割り当ては部品知識による判断。",
        "rows": pub_rows,
    }
    pub_path = os.path.join(D, "data", "motorMaintenance.json")
    with open(pub_path, "w", encoding="utf-8") as f:
        json.dump(pub, f, ensure_ascii=False, separators=(",", ":"))
    say(f"  出力(公開)  : {pub_path}  ({os.path.getsize(pub_path)/1024:,.0f} KB)")

    tpl_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "template_maintenance.html")
    if os.path.exists(tpl_path):
        html = open(tpl_path, encoding="utf-8").read().replace(
            "__DATA_PLACEHOLDER__", json.dumps(pub, ensure_ascii=False, separators=(",", ":")))
        page_dir = os.path.join(D, "motor-maintenance")
        os.makedirs(page_dir, exist_ok=True)
        page = os.path.join(page_dir, "index.html")
        with open(page, "w", encoding="utf-8") as f:
            f.write(html)
        say(f"  出力(ページ): {page}  ({os.path.getsize(page)/1024:,.0f} KB)")
    else:
        say(f"  テンプレート未配置のためページ生成をスキップ: {tpl_path}")

    with open(out + "_report.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(REPORT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
