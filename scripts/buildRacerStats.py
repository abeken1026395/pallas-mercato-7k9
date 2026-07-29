# -*- coding: utf-8 -*-
# buildRacerStats.py
#
# ★このスクリプトは「1回限りの移行用」であり、正本ではない。
#   選手成績データの正本は docs/data/racerStats.json（このスクリプトの出力）。
#   出力後は racerStats.json を直接メンテナンスする。定期実行してはいけない。
#
# 目的:
#   docs/players/index.html に静的埋め込みされた window.__D を、そのまま
#   docs/data/racerStats.json へ切り出す。同じデータは docs/highlights/index.html
#   にも別形式（const PROF=...、キー名短縮のサブセット）で二重に埋め込まれており、
#   共通JSONに寄せて二重管理を解消するための第1段（切り出しのみ）。
#
# 制約:
#   - 入力 docs/players/index.html は読むだけ。書き換えない。
#   - 値の丸め・型変換・キー名変更・並べ替えを一切しない。
#   - {"players":[...]} の形式を維持する（配列のまま。辞書化しない）。
import io
import os
import json

SRC = os.path.join("docs", "players", "index.html")
OUT = os.path.join("docs", "data", "racerStats.json")

PREFIX = "<script>window.__D = "
SUFFIX = ";</script>"


def extract(html):
    """index.html から window.__D の JSON 本体を切り出す。

    埋め込みは1行まるごと `<script>window.__D = {...};</script>` の形。
    黙って壊れた出力を書かないよう、境界が想定どおりかを検証してから返す。
    """
    hits = [ln for ln in html.split("\n") if ln.startswith(PREFIX)]
    if len(hits) != 1:
        raise SystemExit(
            "想定外: '%s' で始まる行が %d 本ある（1本のはず）。%s の構造が変わった可能性がある。"
            % (PREFIX, len(hits), SRC)
        )
    line = hits[0]
    if not line.endswith(SUFFIX):
        raise SystemExit(
            "想定外: window.__D の行が '%s' で終わっていない。%s の構造が変わった可能性がある。"
            % (SUFFIX, SRC)
        )
    return line[len(PREFIX):-len(SUFFIX)]


def main():
    with io.open(SRC, "r", encoding="utf-8") as f:
        html = f.read()

    data = json.loads(extract(html))

    if list(data.keys()) != ["players"]:
        raise SystemExit("想定外: window.__D のトップレベルキーが %r" % (list(data.keys()),))
    players = data["players"]
    if not isinstance(players, list) or not players:
        raise SystemExit("想定外: players が空、または配列でない")

    with io.open(OUT, "w", encoding="utf-8") as f:
        json.dump({"players": players}, f, ensure_ascii=False, separators=(",", ":"))

    # 書き戻した内容が抽出元と完全一致することを確認する（丸め・欠落の検出）
    with io.open(OUT, "r", encoding="utf-8") as f:
        again = json.load(f)
    if again["players"] != players:
        raise SystemExit("検証失敗: 出力が抽出元と一致しない。%s を採用してはいけない。" % OUT)

    print("wrote", OUT, len(players), "players (from", SRC + ")")


if __name__ == "__main__":
    main()
