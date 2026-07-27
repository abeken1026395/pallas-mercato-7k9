# -*- coding: utf-8 -*-
"""読者ログ照合用の最小データを公開する。

出走表ページで読者が記録した「①は残る / 崩れる」の答え合わせを、
ブラウザ側で機械集計するために必要な最小限だけを出す。

  入力 : results/YYYYMMDD.json（buildResults.py の出力・リポジトリ直下＝Pages非公開）
  出力 : docs/data/inSurvival.json（直近 KEEP_DAYS 日分）

判定定義（変更禁止・見どころの①着外率19.2%と同一）:
  「1着」「2着」「3着」が全て整数のとき
      3つの中に 1 が無い → "1"（①が着外＝崩れる）
      3つの中に 1 がある → "0"（①が3着以内＝残る）
  揃わない（中止・欠落等）  → "-"（判定不能）

配当・着順・決まり手・選手名は一切含めない。
"""
import os
import io
import re
import json
import glob
import datetime

IN_DIR = "results"
OUT_PATH = os.path.join("docs", "data", "inSurvival.json")
KEEP_DAYS = 30
MAX_R = 12

DEF_TEXT = (
    "①（1号艇）が3着以内なら0、4着以下（着外）なら1、判定不能は-。"
    "各値は12文字でi文字目が(i+1)R。"
)


def day_files():
    """results/ の YYYYMMDD.json を新しい順に KEEP_DAYS 件返す。"""
    out = []
    for p in glob.glob(os.path.join(IN_DIR, "*.json")):
        base = os.path.basename(p)
        if re.match(r"^\d{8}\.json$", base):
            out.append((base[:8], p))
    out.sort(key=lambda x: x[0], reverse=True)
    return out[:KEEP_DAYS]


def build_day(path):
    """1日分 → {場コード: '0/1/- を12文字'}"""
    d = json.load(io.open(path, encoding="utf-8"))
    day = {}
    for r in d.get("結果", []) or []:
        jcd = str(r.get("場コード", "")).zfill(2)
        if not re.match(r"^\d{2}$", jcd):
            continue
        m = re.match(r"(\d+)", str(r.get("レース", "")))
        if not m:
            continue
        rno = int(m.group(1))
        if rno < 1 or rno > MAX_R:
            continue
        top3 = [r.get("1着"), r.get("2着"), r.get("3着")]
        ok = [x for x in top3 if isinstance(x, int)]
        if len(ok) < 3:
            v = "-"
        else:
            v = "0" if 1 in ok else "1"
        day.setdefault(jcd, ["-"] * MAX_R)[rno - 1] = v
    return dict((jcd, "".join(a)) for jcd, a in day.items())


def main():
    files = day_files()
    days = {}
    for hd, path in files:
        one = build_day(path)
        if one:
            days[hd] = dict(sorted(one.items()))
    keys = sorted(days.keys())
    now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=9)
    out = {
        "生成時刻": now.strftime("%Y-%m-%d %H:%M:%S") + " JST",
        "定義": DEF_TEXT,
        "期間": {
            "開始": keys[0] if keys else "",
            "終了": keys[-1] if keys else "",
            "日数": len(keys),
        },
        "日": dict((k, days[k]) for k in sorted(days.keys(), reverse=True)),
    }
    outdir = os.path.dirname(OUT_PATH)
    if outdir and not os.path.isdir(outdir):
        os.makedirs(outdir)
    with io.open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    n1 = sum(s.count("1") for d in days.values() for s in d.values())
    n0 = sum(s.count("0") for d in days.values() for s in d.values())
    rate = (100.0 * n1 / (n1 + n0)) if (n1 + n0) else 0.0
    print("days=%d bytes=%d rate=%.1f%% (1:%d 0:%d)"
          % (len(keys), os.path.getsize(OUT_PATH), rate, n1, n0))


if __name__ == "__main__":
    main()
