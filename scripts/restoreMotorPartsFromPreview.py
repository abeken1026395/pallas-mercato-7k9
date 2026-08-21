# -*- coding: utf-8 -*-
# restoreMotorPartsFromPreview.py
# 収集が全損した開催日の motorParts.json 行を preview/ と results/ から復元する。
#
# 背景:
#   体重欄が空の艇が1艇でもあると assert_row_sane が sys.exit(1) し、その日の収集が全損した。
#   2026-08-13/14/15/18 の全9便が失敗し、開催日 20260812/0813/0814/0817 が0行になった。
#   収集経路（fetchPartsExchange.py）は PR #267 で止血済み。本スクリプトは過去分の復元専用。
#
# 設計（安全第一・ハルシネーション防止）:
#   - 収集経路は一切触らない。本スクリプトは docs/data/motorParts.json に行を追加するだけ。
#   - preview に無い項目（モーターNo・anteiban）は創作しない。空文字で入れる。
#     モーターNo は本スクリプトの後に backfillMotorPartsMotorNo.py（Kファイル由来）で埋める。
#     ★埋めないと buildMotorMaintenance.py の usable() で全行 dropped になり短縮秒に寄与しない。
#   - 取得日時 も空。これが「復元行」の識別子になる（収集行は必ず YYYY-MM-DD HH:MM が入る）。
#   - 展示タイム空・体重空の艇は行を作らない（収集側 fetchPartsExchange.py と同じルール）。
#   - 書き込み前に4つの自己検証を通す。1つでも落ちたら何も書かずに異常終了する。
#       検証1 二重適用防止 : 対象日の行が既に1行でもあれば中止
#       検証2 変換の正当性 : 成功日を同じ変換で再構成し、本番行と15項目完全一致を要求
#       検証3 既存行の不変 : 対象日以外の行が1行も変化していないこと（順序・値とも）
#       検証4 件数        : 追加行数が期待値と一致すること
#   - updated は変更しない（復元は過去データの追加であり、最新取得時刻を偽らないため）。
#   - 保存書式は収集側と同一（ensure_ascii=False, indent=2）。原本と再dumpのバイト一致を確認済み。
#
# 使い方:
#   python scripts/restoreMotorPartsFromPreview.py --dry     # 検証だけ。書き込まない
#   python scripts/restoreMotorPartsFromPreview.py           # 検証を通れば書き込む
# 終了コード: 0=正常, 2=検証失敗（未書込）, 3=入力不備
import os
import sys
import json
import argparse

# 復元対象の開催日（収集が全損した4日）
TARGET_DAYS = ["20260812", "20260813", "20260814", "20260817"]
# 変換の正当性を確かめる成功日（本番行と突き合わせる）
VERIFY_DAYS = ["20260815", "20260819"]
# 期待する追加行数（preview 実測から算出済み）
EXPECT_ADD = 4307

DEFAULT_PATH = os.path.join("docs", "data", "motorParts.json")
DEFAULT_PREV = "preview"
DEFAULT_RES = "results"

# 部品交換の数量は全角数字。収集側の表記に合わせる（例 リング×２）
ZEN = str.maketrans("0123456789", "０１２３４５６７８９")
URL = "https://www.boatrace.jp/owpc/pc/race/beforeinfo?rno={rno}&jcd={jcd}&hd={hd}"

# 本番行と突き合わせる項目。モーターNo/anteiban/取得日時 は preview に無いか
# 復元時刻依存のため構造上一致しない＝照合から外す（値は空文字で入れる）。
CMP_KEYS = ["jcd", "場名", "開催日", "rno", "枠", "登番", "氏名", "節名", "部品交換",
            "展示タイム", "チルト", "プロペラ", "体重", "tenjiST", "tenjiCourse", "出典URL"]
ALL_KEYS = ["jcd", "場名", "開催日", "rno", "枠", "登番", "氏名", "モーターNo", "節名",
            "部品交換", "展示タイム", "チルト", "プロペラ", "体重", "tenjiST",
            "tenjiCourse", "anteiban", "出典URL", "取得日時"]


def say(msg):
    print(msg)


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def parts_str(parts):
    """preview の parts 配列を収集側の文字列表記に直す。
    quantity が None の部品は数量を書かない（例 キャブ / シリンダ）。"""
    out = []
    for p in parts or []:
        name = p.get("number_source") or ""
        qty = p.get("quantity")
        out.append(name + ("×" + str(qty).translate(ZEN) if qty is not None else ""))
    return " ".join(out)


def build_jcd_name(records):
    """jcd -> 場名 の対応表を本番データから作る（対応表を新たに書き起こさない）。"""
    table = {}
    for r in records:
        table.setdefault(r["jcd"], r["場名"])
    return table


def restore_day(day, prevdir, resdir, jcd2name):
    """1日分を preview + results から再構成する。戻り値 (rows, stat)。"""
    ppath = os.path.join(prevdir, day + ".json")
    rpath = os.path.join(resdir, day + ".json")
    if not os.path.exists(ppath):
        return None, "preview が無い: " + ppath
    if not os.path.exists(rpath):
        return None, "results が無い: " + rpath
    prev = load_json(ppath)
    res = load_json(rpath)

    # results から (jcd, rno, 枠) -> 登番/氏名 を引く
    rmap = {}
    for rec in res["結果"]:
        jcd = str(rec["場コード"]).zfill(2)
        rno = int(str(rec["レース"]).replace("R", ""))
        for b in rec["艇"]:
            rmap[(jcd, rno, str(b["枠"]))] = b

    rows = []
    stat = {"preview艇": 0, "展示空skip": 0, "体重空skip": 0, "results欠": 0}
    for race in prev["直前情報"]:
        jcd = str(race["場コード"]).zfill(2)
        rno = int(str(race["レース"]).replace("R", ""))
        for b in race["racers"]:
            stat["preview艇"] += 1
            if not (b.get("exhibition_time_source") or "").strip():
                stat["展示空skip"] += 1
                continue
            if not (b.get("weight_source") or "").strip():
                stat["体重空skip"] += 1
                continue
            rb = rmap.get((jcd, rno, str(b["entry_number"])))
            if rb is None:
                stat["results欠"] += 1
                continue
            rows.append({
                "jcd": jcd,
                "場名": jcd2name.get(jcd, ""),
                "開催日": day,
                "rno": rno,
                "枠": str(b["entry_number"]),
                "登番": str(rb["登番"]),
                "氏名": rb["氏名"],
                "モーターNo": "",       # preview に無い。backfillMotorPartsMotorNo.py で埋める
                "節名": "",
                "部品交換": parts_str(b.get("parts")),
                "展示タイム": b.get("exhibition_time_source") or "",
                "チルト": b.get("tilt_adjustment_source") or "",
                "プロペラ": b.get("propeller") or "",
                "体重": b.get("weight_source") or "",
                "tenjiST": b.get("start_timing_source") or "",
                "tenjiCourse": str(b.get("course_number") or ""),
                "anteiban": "",         # preview に無い。復元できない（推測値を入れない）
                "出典URL": URL.format(rno=rno, jcd=jcd, hd=day),
                "取得日時": "",         # 復元行の識別子
            })
    return rows, stat


def verify_conversion(records, prevdir, resdir, jcd2name):
    """検証2: 成功日を同じ変換で再構成し、本番行と CMP_KEYS 完全一致を要求する。"""
    ok = True
    for day in VERIFY_DAYS:
        rows, stat = restore_day(day, prevdir, resdir, jcd2name)
        if rows is None:
            say("  [NG] %s: %s" % (day, stat))
            ok = False
            continue
        real = {}
        for r in records:
            if r["開催日"] == day:
                real[(r["jcd"], r["rno"], r["枠"])] = r
        if len(real) == 0:
            say("  [NG] %s: 本番に該当日の行が無く照合できない" % day)
            ok = False
            continue
        ng = 0
        for r in rows:
            t = real.get((r["jcd"], r["rno"], r["枠"]))
            if t is None:
                ng += 1
                continue
            for k in CMP_KEYS:
                if r[k] != t[k]:
                    ng += 1
                    if ng <= 5:
                        say("    差分 %s %s %s %s: 復元=%r 本番=%r"
                            % (day, r["jcd"], r["rno"], k, r[k], t[k]))
                    break
        if len(rows) != len(real) or ng:
            say("  [NG] %s: 本番%d行 / 復元%d行 / 不一致%d件" % (day, len(real), len(rows), ng))
            ok = False
        else:
            say("  [OK] %s: 本番%d行 / 復元%d行 / 不一致0件" % (day, len(real), len(rows)))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default=DEFAULT_PATH)
    ap.add_argument("--prevdir", default=DEFAULT_PREV)
    ap.add_argument("--resdir", default=DEFAULT_RES)
    ap.add_argument("--days", default=",".join(TARGET_DAYS))
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    days = [d.strip() for d in args.days.split(",") if d.strip()]
    if not os.path.exists(args.path):
        say("[ERR] 入力が無い: " + args.path)
        return 3

    data = load_json(args.path)
    records = data["records"]
    before_n = len(records)
    jcd2name = build_jcd_name(records)
    say("対象ファイル : %s" % args.path)
    say("既存行数     : %d" % before_n)
    say("復元対象日   : %s" % ", ".join(days))

    # 検証1 二重適用防止
    say("[検証1] 二重適用の確認")
    exist = {}
    for r in records:
        if r["開催日"] in days:
            exist[r["開催日"]] = exist.get(r["開催日"], 0) + 1
    if exist:
        say("  [NG] 対象日の行が既に存在する: %s" % exist)
        return 2
    say("  [OK] 対象日の行は0件")

    # 検証2 変換の正当性
    say("[検証2] 成功日での再現テスト")
    if not verify_conversion(records, args.prevdir, args.resdir, jcd2name):
        say("  [NG] 再現テストに失敗した。書き込まずに中止する")
        return 2

    # 復元
    say("[復元] 対象日を再構成")
    newrows = []
    for day in days:
        rows, stat = restore_day(day, args.prevdir, args.resdir, jcd2name)
        if rows is None:
            say("  [NG] %s: %s" % (day, stat))
            return 2
        say("  %s : %d行  内訳=%s" % (day, len(rows), stat))
        newrows.extend(rows)
    say("  追加合計 : %d行" % len(newrows))

    # 検証4 件数
    say("[検証4] 件数")
    if len(newrows) != EXPECT_ADD:
        say("  [NG] 追加行数が期待値と違う: 実測%d / 期待%d" % (len(newrows), EXPECT_ADD))
        return 2
    say("  [OK] 追加%d行 → 累計%d行" % (len(newrows), before_n + len(newrows)))

    # 開催日で安定ソート（既存の日内の並びは保たれる）
    merged = sorted(records + newrows, key=lambda r: r["開催日"])

    # 検証3 既存行の不変
    say("[検証3] 既存行の不変")
    kept = [r for r in merged if r["開催日"] not in days]
    if len(kept) != before_n:
        say("  [NG] 既存行数が変わった: %d → %d" % (before_n, len(kept)))
        return 2
    for i, (a, b) in enumerate(zip(records, kept)):
        if a is not b:
            say("  [NG] 既存行の順序が変わった: index %d" % i)
            return 2
    say("  [OK] 既存%d行は順序・値とも不変" % before_n)

    # キーの形をそろえる（余剰キー・欠損キーを作らない）
    for r in newrows:
        if list(r.keys()) != ALL_KEYS:
            say("  [NG] 復元行のキー構成が既存と違う: %s" % list(r.keys()))
            return 2

    data["records"] = merged
    # updated は変更しない（復元は過去データの追加）

    if args.dry:
        say("[dry] 書き込まずに終了する")
        return 0

    with open(args.path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    say("[書込] %s / 累計%d行" % (args.path, len(merged)))
    say("★次にやること: backfillMotorPartsMotorNo.py でモーターNoを埋める")
    say("  埋めないと buildMotorMaintenance.py の usable() で復元行が全て捨てられる")
    return 0


if __name__ == "__main__":
    sys.exit(main())
