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
    "docs/next/topYosou.html",  # 実験場：トップにAI予想部屋の紹介（2026-11-01）
    "docs/next/topHeya.html",  # 実験場：トップに新レース部屋への入口（2026-11-01）
    "docs/next/topKoki.html",  # 実験場：トップに阿部の一言（2026-11-01）
    "docs/index.html",
    "docs/announcers/index.html",
    "docs/glossary/index.html",
    "docs/choukan/index.html",
    "docs/ichimark/index.html",  # 1マークの見立て（2026-11-01 実験場から本番へ）
    "docs/highlights/index.html",
    "docs/kensho/index.html",
    "docs/kensho/flow/index.html",
    "docs/kensho/fmochi/index.html",
    "docs/kensho/jimoto/index.html",
    "docs/kensho/kado/index.html",
    "docs/kensho/kisetsu/index.html",
    "docs/kensho/ninki/index.html",
    "docs/kensho/shobugake/index.html",
    "docs/kensho/taiju/index.html",
    "docs/kensho/tilt/index.html",
    "docs/kensho/tenji/index.html",
    "docs/kensho/buhin/index.html",
    "docs/next/kenshoSg/index.html",  # 実験場：検証12（SGの1号艇）。guard.js を読み込む（2026-10-30）
    "docs/motor-maintenance/index.html",
    "docs/next/courseLast10Preview.html",
    "docs/next/kisetsuYearly.html",
    "docs/next/koushinRireki.html",  # 実験場：更新履歴の見せ方の見本（2026-10-30）
    "docs/next/index.html",
    "docs/next/tiltLab.html",
    "docs/next/tiltShrink.html",
    "docs/next/kensho10Tenji.html",
    "docs/next/kensho11Buhin.html",
    "docs/next/buhinTsuzuki.html",
    "docs/next/sgKaitsuzuke.html",
    "docs/next/senshuCard.html",
    "docs/next/senshuCardC.html",
    "docs/next/senshuCardD.html",
    "docs/next/senshuCardE.html",
    "docs/next/senshuCardSn.html",
    "docs/next/senshuCardSnA.html",
    "docs/next/motorKeireki.html",
    "docs/next/kansenNote.html",
    "docs/next/torisetsu.html",
    "docs/next/topI.html",
    "docs/next/choukanTop.html",
    "docs/next/choukan.html",
    "docs/next/choukanB.html",
    "docs/next/playersH.html",
    "docs/next/kansei6/announcers.html",
    "docs/next/kansei6/fan.html",
    "docs/next/kansei6/glossary.html",
    "docs/next/kansei6/highlights.html",
    "docs/next/kansei6/index.html",
    "docs/next/kansei6/kensho.html",
    "docs/next/kansei6/kenshoFlow.html",
    "docs/next/kansei6/kenshoFmochi.html",
    "docs/next/kansei6/kenshoJimoto.html",
    "docs/next/kansei6/kenshoKado.html",
    "docs/next/kansei6/kenshoKisetsu.html",
    "docs/next/kansei6/kenshoNinki.html",
    "docs/next/kansei6/kenshoShobugake.html",
    "docs/next/kansei6/kenshoTaiju.html",
    "docs/next/kansei6/kenshoTilt.html",
    "docs/next/kansei6/motor.html",
    "docs/next/kansei6/motorMaintenance.html",
    "docs/next/kansei6/payouts.html",
    "docs/next/kansei6/playersCard.html",
    "docs/next/kansei6/racers.html",
    "docs/next/kansei6/results.html",
    "docs/next/kansei6/stadium.html",
    "docs/next/kansei6/torisetsu.html",
    "docs/next/kansei6/updates.html",
    "docs/next/kansei6/uranai.html",
    "docs/next/topH.html",
    "docs/next/playersG.html",
    "docs/next/kansei5/announcers.html",
    "docs/next/kansei5/fan.html",
    "docs/next/kansei5/glossary.html",
    "docs/next/kansei5/highlights.html",
    "docs/next/kansei5/index.html",
    "docs/next/kansei5/kensho.html",
    "docs/next/kansei5/kenshoFlow.html",
    "docs/next/kansei5/kenshoFmochi.html",
    "docs/next/kansei5/kenshoJimoto.html",
    "docs/next/kansei5/kenshoKado.html",
    "docs/next/kansei5/kenshoKisetsu.html",
    "docs/next/kansei5/kenshoNinki.html",
    "docs/next/kansei5/kenshoShobugake.html",
    "docs/next/kansei5/kenshoTaiju.html",
    "docs/next/kansei5/kenshoTilt.html",
    "docs/next/kansei5/motor.html",
    "docs/next/kansei5/motorMaintenance.html",
    "docs/next/kansei5/payouts.html",
    "docs/next/kansei5/playersCard.html",
    "docs/next/kansei5/racers.html",
    "docs/next/kansei5/results.html",
    "docs/next/kansei5/stadium.html",
    "docs/next/kansei5/torisetsu.html",
    "docs/next/kansei5/updates.html",
    "docs/next/kansei5/uranai.html",
    "docs/payouts/index.html",
    "docs/players/card.html",
    "docs/note/index.html",  # 観戦ノート（本番。2026-10-30 けん「観戦ノート出して良いよ」）
    "docs/results/index.html",
    "docs/torisetsu/index.html",
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

# クレジット層（canonical照合）。判定関数がトップレベル定数を包んでいる。関数名が消えたら検知する
# /kensho/ ハブは判定関数を持たず canonical だけ
CREDIT = {
    "docs/updates/index.html": "baseRows",
    "docs/announcers/index.html": "glyphWidth",
    "docs/glossary/index.html": "emStep",
    "docs/next/index.html": "baselineGrid",
    "docs/uranai/index.html": "kernPair",
    "docs/results/index.html": "rowGutter",
    "docs/highlights/index.html": "stemWidth",
    "docs/kensho/index.html": None,
}

# 対象外（けん裁定済み）
EXEMPT_PREFIX = ("docs/aisho-suminoe/", "docs/shobuun-suminoe/", "docs/probe/", "docs/in/", "docs/players/card/s/")  # docs/in/ は告知用の入口（中身なし・即移動。2026-10-03）／players/card/s/ は選手カードの共有用の入口（OGPだけ・即移動。2026-10-08）
EXEMPT_SUFFIX = "-payouts/index.html"  # 24場の万舟率ページ（2026-08-08 見送り裁定）
EXEMPT_FILES = ("docs/404.html",)  # 見つからないページ用（データなし・トップへの案内だけ。2026-10-19）


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
        if p2.startswith(EXEMPT_PREFIX) or p2.endswith(EXEMPT_SUFFIX) or p2 in EXEMPT_FILES:
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

    # 5) クレジット層に canonical と判定関数が残っているか
    for p, fn in CREDIT.items():
        if not os.path.exists(p):
            fails.append("クレジット層の対象が存在しない: " + p)
            continue
        s = read(p)
        if 'rel="canonical"' not in s:
            fails.append("canonical が無い: " + p)
        if fn and s.count(fn) < 2:
            fails.append("クレジット層の判定関数が消えている: %s（%s）" % (p, fn))

    if fails:
        print("FAIL %d 件" % len(fails))
        for m in fails:
            print("  - " + m)
        return 1
    print("PASS: HTML %d 件（GUARD %d / L2 %d / APPJS %d / EXEMPT %d / CREDIT %d）"
          % (len(all_html), len(GUARD), len(L2) + len(L2_ALSO), len(APPJS),
             len(all_html) - len(GUARD) - len(L2) - len(APPJS), len(CREDIT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
