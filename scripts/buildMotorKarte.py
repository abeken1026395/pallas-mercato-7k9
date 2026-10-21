#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
モーターページ（docs/motor/）の整備履歴カルテ専用の軽量派生JSONを作る。

  入力: data/motorParts.json （全列・約21MB・ブラウザで丸ごと読むと iPhone が固まる）
  出力: docs/data/motorKarte.json （描画に使う8列だけ・機ごとに索引済み）

motorParts.json は削除も改変もしない（build_highlights.py が展示偏差の算出に使う）。
このスクリプトは読むだけ。

出力の構造:
  {
    "updated": "YYYY-MM-DD HH:MM",          # motorParts.json の updated をそのまま
    "出典":    "boatrace.jp公式 直前情報",   # motorParts.json の source をそのまま
    "records": {"<jcd>_<モーターNo>": [[開催日,rno,枠,氏名,節名,部品交換,プロペラ,展示タイム,着], ...]}
  }

records の各行はキー名を持たない配列にする（辞書のままだと 5.39MB、配列化で約2MB）。
列順は下の COLS の通り。並びは 開催日 昇順 → rno 昇順（現行 index.html の並び順と一致）。

出典行の時刻を機ごとに持たない理由:
  カルテは1か月ぶんの出走をまたぐので、1行ぶんの取得時刻を出しても意味が合わない。
  節の最終日で止める案も検討したが、motorParts.json の 節名 が全行空で節の区切りを
  開催日の連続でしか推定できず、推定を挟むと 8/12・8/13・8/14・8/17 の復元行
  （取得日時が空）に当たった135機で出典が消える。トップレベルの updated を
  「時点」として出す形にしたので、機ごとのテーブルは持たない。

実行:
  python scripts/buildMotorKarte.py
"""
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
SRC = os.path.join(ROOT, "data", "motorParts.json")
OUT = os.path.join(ROOT, "docs", "data", "motorKarte.json")

# 描画に使う列だけ。並び順は index.html のカルテ行の使用順に合わせる。
COLS = ["開催日", "rno", "枠", "氏名", "節名", "部品交換", "プロペラ", "展示タイム"]
# 9列目に「着」を足す（results/ の公式レース結果を 開催日・場・レース・枠 で引く。1〜6 は数、7以上は記号。無ければ空）
FINISH_MARK = {7: "妨", 8: "エ", 9: "転", 10: "落", 11: "沈", 12: "不", 13: "失", 14: "F", 15: "L", 16: "欠"}


def load_finishes(dates):
    """{(開催日, jcd2桁, rno, 枠): 着の表記}。dates に含まれる日の results/ だけ読む"""
    out = {}
    for d in sorted(dates):
        f = os.path.join(ROOT, "results", d + ".json")
        if not os.path.exists(f):
            continue
        for r in json.load(open(f, encoding="utf-8")).get("結果") or []:
            jcd = "%02d" % int(r["場コード"])
            rno = int(str(r["レース"]).replace("R", ""))
            for b in r.get("艇") or []:
                ch, w = b.get("着"), b.get("枠")
                if isinstance(ch, int) and isinstance(w, int):
                    mk = ch if 1 <= ch <= 6 else FINISH_MARK.get(ch)
                    if mk is not None:
                        out[(d, jcd, rno, w)] = mk
    return out


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
    skipped = 0
    for r in recs:
        no = str(r.get("モーターNo") or "").strip()
        if not no:                      # モーターNo が空の行はスキップ（現行 index.html と同じ）
            skipped += 1
            continue
        k = str(r.get("jcd") or "").zfill(2) + "_" + no
        m.setdefault(k, []).append(r)

    fin = load_finishes({str(r.get("開催日") or "") for rows in m.values() for r in rows})
    out_recs = {}
    for k, rows in m.items():
        # 開催日 昇順 → rno 昇順（index.html の sort と同じ比較）
        rows.sort(key=lambda r: (str(r.get("開催日") or ""), int(r.get("rno") or 0)))
        jcd = k.split("_")[0]
        out_recs[k] = [[norm(r.get(c)) for c in COLS]
                       + [fin.get((str(r.get("開催日") or ""), jcd, int(r.get("rno") or 0), int(r.get("枠") or 0)), "")]
                       for r in rows]

    out = {
        "updated": d.get("updated", ""),
        "出典": d.get("source", ""),
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
