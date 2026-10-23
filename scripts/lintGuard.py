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
    "docs/motor-maintenance/index.html",
    "docs/next/courseLast10Preview.html",
    "docs/next/kisetsuYearly.html",
    "docs/next/index.html",
    "docs/next/tiltLab.html",
    "docs/next/tiltShrink.html",
    "docs/next/kensho10Tenji.html",
    "docs/next/sgKaitsuzuke.html",
    "docs/next/senshuCard.html",
    "docs/next/senshuCardC.html",
    "docs/next/senshuCardD.html",
    "docs/next/senshuCardE.html",
    "docs/next/senshuCardSn.html",
    "docs/next/senshuCardSnA.html",
    "docs/next/motorKeireki.html",
    "docs/next/torisetsu.html",
    "docs/next/topB.html",
    "docs/next/topC.html",
    "docs/next/topD.html",
    "docs/next/kekkaD.html",
    "docs/next/playersC.html",
    "docs/next/kansei/announcers.html",
    "docs/next/kansei/fan.html",
    "docs/next/kansei/glossary.html",
    "docs/next/kansei/highlights.html",
    "docs/next/kansei/index.html",
    "docs/next/kansei/kensho.html",
    "docs/next/kansei/kenshoFlow.html",
    "docs/next/kansei/kenshoFmochi.html",
    "docs/next/kansei/kenshoJimoto.html",
    "docs/next/kansei/kenshoKado.html",
    "docs/next/kansei/kenshoKisetsu.html",
    "docs/next/kansei/kenshoNinki.html",
    "docs/next/kansei/kenshoShobugake.html",
    "docs/next/kansei/kenshoTaiju.html",
    "docs/next/kansei/kenshoTilt.html",
    "docs/next/kansei/motor.html",
    "docs/next/kansei/motorMaintenance.html",
    "docs/next/kansei/payouts.html",
    "docs/next/kansei/playersCard.html",
    "docs/next/kansei/racers.html",
    "docs/next/kansei/results.html",
    "docs/next/kansei/stadium.html",
    "docs/next/kansei/torisetsu.html",
    "docs/next/kansei/updates.html",
    "docs/next/kansei/uranai.html",
    "docs/next/topE.html",
    "docs/next/playersD.html",
    "docs/next/kansei2/announcers.html",
    "docs/next/kansei2/fan.html",
    "docs/next/kansei2/glossary.html",
    "docs/next/kansei2/highlights.html",
    "docs/next/kansei2/index.html",
    "docs/next/kansei2/kensho.html",
    "docs/next/kansei2/kenshoFlow.html",
    "docs/next/kansei2/kenshoFmochi.html",
    "docs/next/kansei2/kenshoJimoto.html",
    "docs/next/kansei2/kenshoKado.html",
    "docs/next/kansei2/kenshoKisetsu.html",
    "docs/next/kansei2/kenshoNinki.html",
    "docs/next/kansei2/kenshoShobugake.html",
    "docs/next/kansei2/kenshoTaiju.html",
    "docs/next/kansei2/kenshoTilt.html",
    "docs/next/kansei2/motor.html",
    "docs/next/kansei2/motorMaintenance.html",
    "docs/next/kansei2/payouts.html",
    "docs/next/kansei2/playersCard.html",
    "docs/next/kansei2/racers.html",
    "docs/next/kansei2/results.html",
    "docs/next/kansei2/stadium.html",
    "docs/next/kansei2/torisetsu.html",
    "docs/next/kansei2/updates.html",
    "docs/next/kansei2/uranai.html",
    "docs/next/ugokiAll/announcers.html",
    "docs/next/ugokiAll/fan.html",
    "docs/next/ugokiAll/glossary.html",
    "docs/next/ugokiAll/highlights.html",
    "docs/next/ugokiAll/index.html",
    "docs/next/ugokiAll/kensho.html",
    "docs/next/ugokiAll/kenshoFlow.html",
    "docs/next/ugokiAll/kenshoFmochi.html",
    "docs/next/ugokiAll/kenshoJimoto.html",
    "docs/next/ugokiAll/kenshoKado.html",
    "docs/next/ugokiAll/kenshoKisetsu.html",
    "docs/next/ugokiAll/kenshoNinki.html",
    "docs/next/ugokiAll/kenshoShobugake.html",
    "docs/next/ugokiAll/kenshoTaiju.html",
    "docs/next/ugokiAll/kenshoTilt.html",
    "docs/next/ugokiAll/motor.html",
    "docs/next/ugokiAll/motorMaintenance.html",
    "docs/next/ugokiAll/payouts.html",
    "docs/next/ugokiAll/players.html",
    "docs/next/ugokiAll/playersCard.html",
    "docs/next/ugokiAll/racers.html",
    "docs/next/ugokiAll/results.html",
    "docs/next/ugokiAll/stadium.html",
    "docs/next/ugokiAll/torisetsu.html",
    "docs/next/ugokiAll/updates.html",
    "docs/next/ugokiAll/uranai.html",
    "docs/next/kamimen/index.html",
    "docs/next/keijiban/index.html",
    "docs/next/aiNashi/announcers.html",
    "docs/next/aiNashi/fan.html",
    "docs/next/aiNashi/glossary.html",
    "docs/next/aiNashi/highlights.html",
    "docs/next/aiNashi/index.html",
    "docs/next/aiNashi/kensho.html",
    "docs/next/aiNashi/kenshoFlow.html",
    "docs/next/aiNashi/kenshoFmochi.html",
    "docs/next/aiNashi/kenshoJimoto.html",
    "docs/next/aiNashi/kenshoKado.html",
    "docs/next/aiNashi/kenshoKisetsu.html",
    "docs/next/aiNashi/kenshoNinki.html",
    "docs/next/aiNashi/kenshoShobugake.html",
    "docs/next/aiNashi/kenshoTaiju.html",
    "docs/next/aiNashi/kenshoTilt.html",
    "docs/next/aiNashi/motor.html",
    "docs/next/aiNashi/motorMaintenance.html",
    "docs/next/aiNashi/payouts.html",
    "docs/next/aiNashi/players.html",
    "docs/next/aiNashi/playersCard.html",
    "docs/next/aiNashi/racers.html",
    "docs/next/aiNashi/results.html",
    "docs/next/aiNashi/stadium.html",
    "docs/next/aiNashi/torisetsu.html",
    "docs/next/aiNashi/updates.html",
    "docs/next/aiNashi/uranai.html",
    "docs/next/aiNashi2/announcers.html",
    "docs/next/aiNashi2/fan.html",
    "docs/next/aiNashi2/glossary.html",
    "docs/next/aiNashi2/highlights.html",
    "docs/next/aiNashi2/index.html",
    "docs/next/aiNashi2/kensho.html",
    "docs/next/aiNashi2/kenshoFlow.html",
    "docs/next/aiNashi2/kenshoFmochi.html",
    "docs/next/aiNashi2/kenshoJimoto.html",
    "docs/next/aiNashi2/kenshoKado.html",
    "docs/next/aiNashi2/kenshoKisetsu.html",
    "docs/next/aiNashi2/kenshoNinki.html",
    "docs/next/aiNashi2/kenshoShobugake.html",
    "docs/next/aiNashi2/kenshoTaiju.html",
    "docs/next/aiNashi2/kenshoTilt.html",
    "docs/next/aiNashi2/motor.html",
    "docs/next/aiNashi2/motorMaintenance.html",
    "docs/next/aiNashi2/payouts.html",
    "docs/next/aiNashi2/players.html",
    "docs/next/aiNashi2/playersCard.html",
    "docs/next/aiNashi2/racers.html",
    "docs/next/aiNashi2/results.html",
    "docs/next/aiNashi2/stadium.html",
    "docs/next/aiNashi2/torisetsu.html",
    "docs/next/aiNashi2/updates.html",
    "docs/next/aiNashi2/uranai.html",
    "docs/next/aiNashi3/announcers.html",
    "docs/next/aiNashi3/fan.html",
    "docs/next/aiNashi3/glossary.html",
    "docs/next/aiNashi3/highlights.html",
    "docs/next/aiNashi3/index.html",
    "docs/next/aiNashi3/kensho.html",
    "docs/next/aiNashi3/kenshoFlow.html",
    "docs/next/aiNashi3/kenshoFmochi.html",
    "docs/next/aiNashi3/kenshoJimoto.html",
    "docs/next/aiNashi3/kenshoKado.html",
    "docs/next/aiNashi3/kenshoKisetsu.html",
    "docs/next/aiNashi3/kenshoNinki.html",
    "docs/next/aiNashi3/kenshoShobugake.html",
    "docs/next/aiNashi3/kenshoTaiju.html",
    "docs/next/aiNashi3/kenshoTilt.html",
    "docs/next/aiNashi3/motor.html",
    "docs/next/aiNashi3/motorMaintenance.html",
    "docs/next/aiNashi3/payouts.html",
    "docs/next/aiNashi3/players.html",
    "docs/next/aiNashi3/playersCard.html",
    "docs/next/aiNashi3/racers.html",
    "docs/next/aiNashi3/results.html",
    "docs/next/aiNashi3/stadium.html",
    "docs/next/aiNashi3/torisetsu.html",
    "docs/next/aiNashi3/updates.html",
    "docs/next/aiNashi3/uranai.html",
    "docs/next/aiNashi4/announcers.html",
    "docs/next/aiNashi4/fan.html",
    "docs/next/aiNashi4/glossary.html",
    "docs/next/aiNashi4/highlights.html",
    "docs/next/aiNashi4/index.html",
    "docs/next/aiNashi4/kensho.html",
    "docs/next/aiNashi4/kenshoFlow.html",
    "docs/next/aiNashi4/kenshoFmochi.html",
    "docs/next/aiNashi4/kenshoJimoto.html",
    "docs/next/aiNashi4/kenshoKado.html",
    "docs/next/aiNashi4/kenshoKisetsu.html",
    "docs/next/aiNashi4/kenshoNinki.html",
    "docs/next/aiNashi4/kenshoShobugake.html",
    "docs/next/aiNashi4/kenshoTaiju.html",
    "docs/next/aiNashi4/kenshoTilt.html",
    "docs/next/aiNashi4/motor.html",
    "docs/next/aiNashi4/motorMaintenance.html",
    "docs/next/aiNashi4/payouts.html",
    "docs/next/aiNashi4/players.html",
    "docs/next/aiNashi4/playersCard.html",
    "docs/next/aiNashi4/racers.html",
    "docs/next/aiNashi4/results.html",
    "docs/next/aiNashi4/stadium.html",
    "docs/next/aiNashi4/torisetsu.html",
    "docs/next/aiNashi4/updates.html",
    "docs/next/aiNashi4/uranai.html",
    "docs/next/aiNashi5/announcers.html",
    "docs/next/aiNashi5/fan.html",
    "docs/next/aiNashi5/glossary.html",
    "docs/next/aiNashi5/highlights.html",
    "docs/next/aiNashi5/index.html",
    "docs/next/aiNashi5/kensho.html",
    "docs/next/aiNashi5/kenshoFlow.html",
    "docs/next/aiNashi5/kenshoFmochi.html",
    "docs/next/aiNashi5/kenshoJimoto.html",
    "docs/next/aiNashi5/kenshoKado.html",
    "docs/next/aiNashi5/kenshoKisetsu.html",
    "docs/next/aiNashi5/kenshoNinki.html",
    "docs/next/aiNashi5/kenshoShobugake.html",
    "docs/next/aiNashi5/kenshoTaiju.html",
    "docs/next/aiNashi5/kenshoTilt.html",
    "docs/next/aiNashi5/motor.html",
    "docs/next/aiNashi5/motorMaintenance.html",
    "docs/next/aiNashi5/payouts.html",
    "docs/next/aiNashi5/players.html",
    "docs/next/aiNashi5/playersCard.html",
    "docs/next/aiNashi5/racers.html",
    "docs/next/aiNashi5/results.html",
    "docs/next/aiNashi5/stadium.html",
    "docs/next/aiNashi5/torisetsu.html",
    "docs/next/aiNashi5/updates.html",
    "docs/next/aiNashi5/uranai.html",
    "docs/payouts/index.html",
    "docs/players/card.html",
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
