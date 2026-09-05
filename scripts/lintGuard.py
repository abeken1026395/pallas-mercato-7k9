#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lintGuard.py — コピー検知の網羅リント

docs 配下の全HTMLを4分類のいずれかに割り当て、防御の抜けを機械検査する。
どの分類にも属さないHTMLが増えたら FAIL＝新規ページの防御方針を決めるまで通さない。

分類:
  GUARD    … docs/assets/guard.js への参照が必須
  L2       … 難読化L2トラップ（判定式のハードコード）が必須
  APPJS    … 同ディレクトリの app.js 側の判定式が必須（HTML自体は器）
  EXEMPT   … 対象外（けん裁定済み。触らない遺物・内部用・payouts 24場）

使い方:
  python scripts/lintGuard.py        # 全検査。1件でもFAILなら非ゼロ終了
検査は読み取りのみ。ファイルを書き換えない。
"""

import glob
import io
import os
import sys

GUARD_REF = "assets/guard.js"
JUDGE = '"/pallas-mercato-7k9/"'  # 判定式のハードコード痕跡（L2/appjs 検出用）
GUARD_FILE = "docs/assets/guard.js"

# guard.js 参照が必須のページ（正本が別にある生成物も、生成物側で検査する）
GUARD = [
    "docs/index.html",
    "docs/announcers/index.html",
    "docs/glossary/index.html",
    "docs/highlights/index.html",
    "docs/kensho/index.html",
    "docs/kensho/fmochi/index.html",
    "docs/kensho/ninki/index.html",
    "docs/kensho/shobugake/index.html",
    "docs/kensho/taiju/index.html",
    "docs/motor-maintenance/index.html",
    "docs/next/courseLast10Preview.html",
    "docs/next/index.html",
    "docs/payouts/index.html",
    "docs/results/index.html",
    "docs/updates/index.html",
    "docs/uranai/index.html",
]

# L2トラップ（判定式ハードコード）で守られているページ
L2 = [
    "docs/fan/index.html",
    "docs/stadium/index.html",
    "docs/racers/index.html",       # 生成物。正本 scripts/template_racers.html
    "docs/next/stadiumPreview.html",
]
# ※ docs/index.html と docs/payouts/index.html は guard に加えて L2 も持つ（下で両方検査）
L2_ALSO = ["docs/index.html", "docs/payouts/index.html"]

# app.js 側で守られているページ（HTMLは器で、判定式は app.js にある）
# docs/motor/ は JSX の事前ビルド化（babel-standalone 廃止）で判定式が app.js 側へ移った。
APPJS = {
    "docs/players/index.html": "docs/players/app.js",
    "docs/motor/index.html": "docs/motor/app.js",   # 生成物。正本 scripts/template.html＋scripts/motor/app.jsx
}

# 対象外（けん裁定済み）
EXEMPT_PREFIX = ("docs/aisho-suminoe/", "docs/shobuun-suminoe/", "docs/probe/")
EXEMPT_SUFFIX = "-payouts/index.html"  # 24場の万舟率ページ（2026-08-08 見送り裁定）


def read(path):
    with io.open(path, "r", encoding="utf-8") as f:
        return f.read()


def main():
    fails = []
    all_html = sorted(glob.glob("docs/**/*.html", recursive=True))

    # 0) guard.js 本体
    if not os.path.exists(GUARD_FILE):
        fails.append("guard.js 本体が無い: " + GUARD_FILE)
    elif JUDGE not in read(GUARD_FILE):
        fails.append("guard.js に判定式が無い: " + GUARD_FILE)

    # 1) 全HTMLがいずれかの分類に属するか
    known = set(GUARD) | set(L2) | set(APPJS)
    for p in all_html:
        p2 = p.replace(os.sep, "/")
        if p2 in known:
            continue
        if p2.startswith(EXEMPT_PREFIX) or p2.endswith(EXEMPT_SUFFIX):
            continue
        fails.append("未分類のHTML（防御方針が未決）: " + p2)

    # 2) GUARD ページに参照があるか
    for p in GUARD:
        if not os.path.exists(p):
            fails.append("GUARD対象が存在しない: " + p)
        elif GUARD_REF not in read(p):
            fails.append("guard.js 参照が無い: " + p)

    # 3) L2 ページに判定式が残っているか（誤削除の検知）
    for p in L2 + L2_ALSO:
        if not os.path.exists(p):
            fails.append("L2対象が存在しない: " + p)
        elif JUDGE not in read(p):
            fails.append("L2判定式が消えている: " + p)

    # 4) players・motor は app.js 側を検査
    for p, appjs in APPJS.items():
        if not os.path.exists(p):
            fails.append("APPJS対象が存在しない: " + p)
        if not os.path.exists(appjs):
            fails.append("app.js が無い: " + appjs)
        elif JUDGE not in read(appjs):
            fails.append("app.js に判定式が無い: " + appjs)

    if fails:
        print("FAIL %d 件" % len(fails))
        for m in fails:
            print("  - " + m)
        return 1
    print("PASS: HTML %d 件（GUARD %d / L2 %d / APPJS %d / EXEMPT %d）"
          % (len(all_html), len(GUARD), len(L2) + len(L2_ALSO), len(APPJS),
             len(all_html) - len(GUARD) - len(L2) - len(APPJS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
