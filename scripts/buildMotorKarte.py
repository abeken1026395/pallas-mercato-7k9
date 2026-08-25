#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
モーターページ（docs/motor/）の整備履歴カルテ専用の軽量派生JSONを作る。

  入力: docs/data/motorParts.json （全列・約21MB・ブラウザで丸ごと読むと iPhone が固まる）
  出力: docs/data/motorKarte.json （描画に使う8列だけ・機ごとに索引済み）

motorParts.json は削除も改変もしない（build_highlights.py が展示偏差の算出に使う）。
このスクリプトは読むだけ。

出力の構造:
  {
    "updated": "YYYY-MM-DD HH:MM",          # motorParts.json の updated をそのまま
    "出典":    "boatrace.jp公式 直前情報",   # motorParts.json の source をそのまま
    "取得日時": {"<jcd>_<モーターNo>": "YYYY-MM-DD HH:MM"},  # 各機の先頭行の取得日時
    "records": {"<jcd>_<モーターNo>": [[開催日,rno,枠,氏名,節名,部品交換,プロペラ,展示タイム], ...]}
  }

records の各行はキー名を持たない配列にする（辞書のままだと 5.39MB、配列化で約2MB）。
列順は下の COLS の通り。並びは 開催日 昇順 → rno 昇順（現行 index.html の並び順と一致）。

「取得日時」を別テーブルに分けている理由:
  カルテの出典行が parts[0]["取得日時"] を表示している。8列だけだとこの1文字が消えるため、
  各機の先頭行の取得日時だけを持つ（全行に持たせると約0.7MB増えるので持たせない）。

実行:
  python scripts/buildMotorKarte.py
"""
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
SRC = os.path.join(ROOT, "docs", "data", "motorParts.json")
OUT = os.path.join(ROOT, "docs", "data", "motorKarte.json")

# 描画に使う列だけ。並び順は index.html のカルテ行の使用順に合わせる。
COLS = ["開催日", "rno", "枠", "氏名", "節名", "部品交換", "プロペラ", "展示タイム"]


def norm(v):
    """None を空文字にするだけ。数値（rno）は型を保つ。"""
    if v is None:
        return ""
    return v


def build(src_path=SRC, out_path=OUT):
    with open(src_path, "r", encoding="utf-8") as f:
        d = json.load(f)

    recs = d.get("records")
    if not isinstance(recs, list):
        raise SystemExit("records が配列ではありません: {}".format(src_path))

    m = {}
    acq = {}
    skipped = 0
    for r in recs:
        no = str(r.get("モーターNo") or "").strip()
        if not no:                      # モーターNo が空の行はスキップ（現行 index.html と同じ）
            skipped += 1
            continue
        k = str(r.get("jcd") or "").zfill(2) + "_" + no
        m.setdefault(k, []).append(r)

    out_recs = {}
    for k, rows in m.items():
        # 開催日 昇順 → rno 昇順（index.html の sort と同じ比較）
        rows.sort(key=lambda r: (str(r.get("開催日") or ""), int(r.get("rno") or 0)))
        out_recs[k] = [[norm(r.get(c)) for c in COLS] for r in rows]
        t = rows[0].get("取得日時")
        if t:
            acq[k] = t

    out = {
        "updated": d.get("updated", ""),
        "出典": d.get("source", ""),
        "取得日時": acq,
        "records": out_recs,
    }

    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, out_path)

    size = os.path.getsize(out_path)
    print("wrote {} {} bytes / keys={} / rows={} / skipped(モーターNo空)={}".format(
        out_path, size, len(out_recs), sum(len(v) for v in out_recs.values()), skipped))
    return out_path


if __name__ == "__main__":
    a = sys.argv[1:]
    build(a[0] if len(a) > 0 else SRC, a[1] if len(a) > 1 else OUT)
