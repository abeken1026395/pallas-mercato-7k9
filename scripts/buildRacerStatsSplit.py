# -*- coding: utf-8 -*-
# buildRacerStatsSplit.py
# docs/data/racerStats.json（正本・期首固定）を、選手図鑑の初期表示に必要な最小集合
# （core）と、詳細パネル／支部傾向タブでしか使わない残り（detail）の2ファイルに割る。
#
#   入力: docs/data/racerStats.json          ← 読むだけ。絶対に書き換えない。
#   出力: docs/data/racerStatsCore.json      一覧表示＋ソートに要る項目だけ
#         docs/data/racerStatsDetail.json    残り全項目 ＋ c1 の全6値
#
# 選手図鑑 index.html には window.__D={"players":[...]} が静的埋め込みされていた。
# 埋め込みを外して core を fetch する形にすると初期転送量が下がるが、丸ごと外部化
# しただけでは転送量がほとんど減らない（実測 -2.6%）ため、初期に要る項目だけを
# 切り出している。
#
# 1回限りの移行スクリプトではない。期替わりなどで racerStats.json を更新したら
# 必ずこれを再実行して2ファイルを作り直すこと。実行は冪等で、同じ入力からは
# 常に同じバイト列が出る（辞書のキー順は入力の出現順に固定している）。
#
#   $ python scripts/buildRacerStatsSplit.py
#
# 標準ライブラリのみ。pip 不要。
import io
import json
import os
import sys

SRC = os.path.join("docs", "data", "racerStats.json")
CORE_OUT = os.path.join("docs", "data", "racerStatsCore.json")
DETAIL_OUT = os.path.join("docs", "data", "racerStatsDetail.json")

# 一覧カードの描画とソートに必要な項目。
#   no/name/kana/branch : 検索（名前・ふりがな・登番・支部）と表示
#   name                : ★ br_oshi（⭐フォロー）の保存名に使うため必ず core 側に置く。
#                           detail 側に落とすと詳細未取得のまま☆を押したとき
#                           name が undefined で localStorage に入る。
#   rank/female         : 級別バッジ・級別フィルタ・♥女子フィルタ
#   win/fukusho         : 一覧カード右の大きな数字2列
#   out/yusyo           : 並び替え「アウト戦順」「優勝数順」
#   c1                  : 並び替え「イン1着率順」が c1[0] だけを見る。
#                         core では 1要素の配列 [c1[0]] として持ち、detail 到着時に
#                         6要素の本体で上書きされる。既存の p.c1[0] がそのまま動く。
CORE_KEYS = ("no", "name", "kana", "branch", "rank", "female",
             "win", "fukusho", "out", "yusyo")


def build(players):
    """players（racerStats.json の配列）から (core配列, detail辞書) を作る。

    detail は core に無い全キー ＋ c1 の全6値。no をキーにした辞書で返す。
    値は racerStats.json のものをそのまま使う（丸め・型変換を一切しない）。
    """
    core, detail = [], {}
    for p in players:
        row = {}
        for k in CORE_KEYS:
            row[k] = p.get(k)
        c1 = p.get("c1")
        # ソートが見るのは先頭（1コース）だけ。無い/空なら detail 側だけに任せる。
        row["c1"] = [c1[0]] if isinstance(c1, list) and c1 else []
        core.append(row)

        rest = {}
        for k in p:
            if k in CORE_KEYS:
                continue
            rest[k] = p[k]
        detail[p["no"]] = rest
    return core, detail


def verify(players, core, detail):
    """core と detail を結合すると元の racerStats.json に完全に戻ることを確認する。

    分割で値が落ちたり丸められたりしていないことを、生成のたびに機械的に保証する。
    1件でも食い違ったら書き出さずに終了する。
    """
    if len(core) != len(players):
        return ["件数不一致: core={} / racerStats={}".format(len(core), len(players))]
    bad = []
    for src, row in zip(players, core):
        no = src["no"]
        if row["no"] != no:
            bad.append("並び順不一致: {} != {}".format(row["no"], no))
            continue
        merged = dict(row)
        merged.update(detail.get(no, {}))
        if set(merged) != set(src):
            miss = sorted(set(src) - set(merged))
            extra = sorted(set(merged) - set(src))
            bad.append("{} キー不一致 欠落={} 余分={}".format(no, miss, extra))
            continue
        for k in src:
            if merged[k] != src[k]:
                bad.append("{} {}: {!r} != {!r}".format(no, k, merged[k], src[k]))
    return bad


def main():
    with io.open(SRC, "r", encoding="utf-8") as f:
        players = json.load(f).get("players", [])
    if not players:
        print("ERROR: {} に players がありません".format(SRC), file=sys.stderr)
        return 1

    core, detail = build(players)

    bad = verify(players, core, detail)
    if bad:
        print("ERROR: 分割の検証に失敗しました（{}件）。書き出しを中止します。".format(len(bad)),
              file=sys.stderr)
        for line in bad[:20]:
            print("  " + line, file=sys.stderr)
        return 1

    docs = (
        (CORE_OUT, {"source": SRC.replace(os.sep, "/"), "count": len(core),
                    "players": core}),
        (DETAIL_OUT, {"source": SRC.replace(os.sep, "/"), "count": len(detail),
                      "players": detail}),
    )
    for path, doc in docs:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with io.open(path, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
        print("OK: {} ({}名 / {} bytes)".format(
            path, doc["count"], os.path.getsize(path)))

    print("検証OK: core + detail = racerStats.json（全{}名・全キー・全値が一致）"
          .format(len(players)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
