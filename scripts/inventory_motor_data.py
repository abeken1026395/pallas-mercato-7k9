#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
inventory_motor_data.py

目的: 既にリポジトリに溜まっているモーター関連データの棚卸し。
      「後任効果」が何サンプル取れるかを判定する。新規取得は一切しない。

判定したいこと:
  Q1. 選手番号がエントリに入っているか      → 交代が追えるか
  Q2. 節の区切りが判定できるか              → 誰から誰へ、が切れるか
  Q3. 節ごとの成績が紐づくか                → 効果を測る対象があるか
  Q4. 実際に何ペアの「選手交代」が存在するか

実行（リポジトリのルートで）:
  py scripts/inventory_motor_data.py
  py scripts/inventory_motor_data.py --root docs/data

出力: 標準出力 + inventory_report.txt
"""

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime

REPORT = []


def say(*args):
    line = " ".join(str(a) for a in args)
    print(line)
    REPORT.append(line)


def head(title):
    say("\n" + "=" * 70)
    say(title)
    say("=" * 70)


# --- 列名の当たりをつける ------------------------------------------------
# スキーマを俺は知らんので、それっぽい名前を総当たりで探す。
PATTERNS = {
    "racer":  [r"racer", r"player", r"toban", r"登録", r"登番", r"選手", r"氏名",
               r"regno", r"racer_?no"],
    "motor":  [r"motor", r"モーター", r"機番", r"motor_?no", r"mno"],
    "venue":  [r"jcd", r"venue", r"place", r"stadium", r"場", r"jyo"],
    "date":   [r"date", r"hd", r"day", r"日付", r"開催日", r"ymd", r"初出日", r"最新日"],
    "series": [r"series", r"節", r"setu", r"meeting", r"period"],
    "score":  [r"rate", r"率", r"win", r"着", r"rank", r"point", r"result",
               r"tenji", r"展示", r"連"],
}


def guess_roles(keys):
    """列名リストから役割を推定して {役割: [列名]} を返す。"""
    found = defaultdict(list)
    for k in keys:
        kl = str(k).lower()
        for role, pats in PATTERNS.items():
            if any(re.search(p, kl) for p in pats):
                found[role].append(k)
    return found


def flatten_keys(obj, prefix="", depth=0, out=None):
    """ネストしたJSONのキーパスを集める（深さ3まで）。"""
    if out is None:
        out = []
    if depth > 3:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else str(k)
            out.append(path)
            flatten_keys(v, path, depth + 1, out)
    elif isinstance(obj, list) and obj:
        flatten_keys(obj[0], prefix + "[]", depth + 1, out)
    return out


# --- ファイル探索 ---------------------------------------------------------
def scan(root):
    hits = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in
                       (".git", "node_modules", "__pycache__", ".github")]
        for fn in filenames:
            if not fn.lower().endswith((".json", ".csv")):
                continue
            low = fn.lower()
            if not any(k in low for k in
                       ("motor", "part", "usage", "machine", "engine", "tenji", "e30")):
                continue
            p = os.path.join(dirpath, fn)
            try:
                hits.append((p, os.path.getsize(p)))
            except OSError:
                pass
    return sorted(hits, key=lambda x: -x[1])


def inspect_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        say(f"  読み込み失敗: {e}")
        return None

    if isinstance(data, list):
        say(f"  形式: 配列 / {len(data):,} 件")
        sample = data[0] if data else None
        records = data
    elif isinstance(data, dict):
        say(f"  形式: オブジェクト / トップレベルキー {len(data):,} 個")
        say(f"  トップレベル: {list(data)}")
        # 先頭キーは updated / note 等のメタであることが多い。
        # dict/list を値に持つキーのうち最大のものを本体とみなす。
        body_keys = [k for k, v in data.items() if isinstance(v, (dict, list)) and v]
        if not body_keys:
            say("  本体らしいキーなし（メタのみ）")
            return None
        body_key = max(body_keys, key=lambda k: len(data[k]))
        body = data[body_key]
        say(f"  本体キー: {body_key!r}（{len(body):,} 件）")
        if isinstance(body, list):
            sample = body[0]
            records = body
        else:
            first = next(iter(body))
            say(f"  本体の先頭キー: {first!r}")
            sample = body[first]
            records = list(body.values())
    else:
        say("  形式: スカラー（対象外）")
        return None

    keys = flatten_keys(sample)
    say(f"  キーパス（先頭30）:")
    for k in keys[:30]:
        say(f"    - {k}")

    roles = guess_roles(keys)
    say("  役割推定:")
    for role in ("racer", "motor", "venue", "date", "series", "score"):
        got = roles.get(role, [])
        mark = "OK  " if got else "なし"
        say(f"    [{mark}] {role:7s} -> {got[:4]}")

    say(f"  サンプル1件: {json.dumps(sample, ensure_ascii=False)[:400]}")
    return records


def inspect_csv(path):
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            rdr = csv.reader(f)
            header = next(rdr, [])
            rows = sum(1 for _ in rdr)
    except Exception as e:
        say(f"  読み込み失敗: {e}")
        return None

    say(f"  形式: CSV / {rows:,} 行")
    say(f"  ヘッダ: {header}")
    roles = guess_roles(header)
    say("  役割推定:")
    for role in ("racer", "motor", "venue", "date", "series", "score"):
        got = roles.get(role, [])
        mark = "OK  " if got else "なし"
        say(f"    [{mark}] {role:7s} -> {got[:4]}")
    return None


# --- 後任効果のペア数え --------------------------------------------------
def count_handovers(records, key_venue, key_motor, key_racer, key_date):
    """
    (場, 機番) ごとに日付順で並べ、選手が変わった回数を数える。
    = 後任効果を測れるペアの上限数。
    """
    timeline = defaultdict(list)
    skipped = 0
    for r in records:
        if not isinstance(r, dict):
            skipped += 1
            continue
        try:
            v = r[key_venue]; m = r[key_motor]
            p = r[key_racer]; d = str(r[key_date])
        except (KeyError, TypeError):
            skipped += 1
            continue
        timeline[(v, m)].append((d, p))

    handovers = 0
    per_motor = []
    for key, seq in timeline.items():
        seq.sort()
        changes = 0
        prev = None
        for _, p in seq:
            if prev is not None and p != prev:
                changes += 1
            prev = p
        handovers += changes
        per_motor.append(changes)

    say(f"\n  対象モーター数      : {len(timeline):,}")
    say(f"  スキップした行      : {skipped:,}")
    say(f"  選手交代の総回数    : {handovers:,}")
    if per_motor:
        per_motor.sort()
        mid = per_motor[len(per_motor) // 2]
        say(f"  1機あたり中央値     : {mid}")
        say(f"  1機あたり最大       : {per_motor[-1]}")
    return handovers


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".", help="探索の起点")
    ap.add_argument("--handover", nargs=4, metavar=("FILE", "VENUE", "MOTOR", "RACER_DATE"),
                    help="ペア数え。例: --handover docs/data/motorUsage.json jcd motorNo 'racer:date'")
    args = ap.parse_args()

    head("1. モーター関連ファイルの探索")
    hits = scan(args.root)
    if not hits:
        say("該当ファイルなし。--root を確認して。")
        return 1
    for p, size in hits:
        say(f"  {size/1024:9,.0f} KB  {p}")

    head("2. 各ファイルのスキーマ")
    loaded = {}
    for p, _ in hits[:12]:
        say(f"\n--- {p}")
        if p.lower().endswith(".json"):
            recs = inspect_json(p)
            if recs:
                loaded[p] = recs
        else:
            inspect_csv(p)

    head("3. 後任効果ペアの概算")
    if args.handover:
        f, kv, km, kr_kd = args.handover[0], args.handover[1], args.handover[2], args.handover[3]
        kr, kd = kr_kd.split(":")
        recs = loaded.get(f)
        if recs is None:
            recs = inspect_json(f)
        if recs:
            count_handovers(recs, kv, km, kr, kd)
    else:
        say("  上の役割推定を見て、実際の列名を指定して再実行して:")
        say("    py inventory_motor_data.py --handover docs/data/motorUsage.json <場列> <機番列> <選手列>:<日付列>")

    with open("inventory_report.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(REPORT))
    say("\n\nレポート: inventory_report.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
