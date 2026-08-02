# -*- coding: utf-8 -*-
"""
CSV 書き込み前の検証ガード（追記型CSVの共通部品）

「検証してから書く」の型は build_highlights.py:941-949（自己検査→sys.exit(3)）と
kdataMergeEntries.py:65-67（行数検証→書かずに中止）に倣う。

対象は「既存CSVを全行読み直し、新規分を足して全文を書き戻す」作りのスクリプト。
この作りは、読み込みか取得のどちらかがこけると、既存データを丸ごと失った状態で
ヘッダだけを書き戻してしまう。実際に docs/payouts/kiryuPayouts.csv が
ヘッダ1行だけになる事故が起きている（2026-07-02）。

検証項目:
  (1) 書き戻す行数が既存ファイルのデータ行数を下回ったら書かない
      … このCSVは追記型なので、行が減ることは異常
  (2) データ行が0件なら書かない
  (3) 列構成が既存と一致しなければ書かない
      … 併せて、全データ行の列数がヘッダと一致することも確認する
  ※ 既存ファイルが無い初回は (1) をスキップし、(2)(3) を適用する

NG のときは既存ファイルを open すらせずに中止するため、既存データは無傷で残る。
理由を標準エラーへ出し、非ゼロ終了する（握りつぶさない）。
"""
import csv
import os
import sys

EXIT_GUARD_NG = 3


class GuardError(Exception):
    """書き込み前検証に落ちたことを表す。"""


def _read_existing(path):
    """既存CSVの (ヘッダ, データ行数) を返す。空ファイルなら (None, 0)。"""
    with open(path, encoding="utf-8", newline="") as f:
        r = csv.reader(f)
        header = next(r, None)
        n = sum(1 for row in r if row)
    return header, n


def check_before_write(path, header, rows):
    """書き込んでよいかを検証する。NG なら GuardError を送出する。

    path   … 書き込み先（既存ファイルの比較対象）
    header … これから書くヘッダ（列名のリスト）
    rows   … これから書くデータ行（ヘッダを含まない）
    """
    header = list(header)
    reasons = []

    # (2) データ行が0件なら書かない（初回・既存ありを問わず適用）
    if not rows:
        reasons.append("データ行が0件")

    # (3) 列構成: 全データ行の列数がヘッダと一致するか（初回でも適用）
    ncol = len(header)
    bad = [i for i, row in enumerate(rows) if len(row) != ncol]
    if bad:
        reasons.append(
            "列数不一致の行が%d件（先頭は%d行目: %d列 != ヘッダ%d列）"
            % (len(bad), bad[0] + 1, len(rows[bad[0]]), ncol))

    if os.path.exists(path):
        try:
            old_header, old_n = _read_existing(path)
        except Exception as e:
            # 既存が読めない状態で上書きするのが最も危険なので、ここで止める
            reasons.append("既存ファイルを読めない（%r）" % (e,))
        else:
            # (3) 列構成が既存と一致するか
            if old_header is not None and old_header != header:
                reasons.append(
                    "列構成が既存と不一致（既存 %s / 新 %s）" % (old_header, header))
            # (1) 行数が既存を下回ったら書かない
            if len(rows) < old_n:
                reasons.append(
                    "行数が既存を下回る（新 %d行 < 既存 %d行）" % (len(rows), old_n))

    if reasons:
        raise GuardError(" / ".join(reasons))


def guarded_write_csv(path, header, rows, exit_code=EXIT_GUARD_NG):
    """検証を通ったときだけ CSV を書く。

    NG のときは path に一切触れず、理由を標準エラーへ出して非ゼロ終了する。
    OK なら書き込んだデータ行数を返す。
    """
    header = list(header)
    try:
        check_before_write(path, header, rows)
    except GuardError as e:
        sys.stderr.write(
            "GUARD NG: %s → %s を書かずに中止（既存ファイルは保持）\n" % (e, path))
        sys.stderr.flush()
        sys.exit(exit_code)

    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return len(rows)
