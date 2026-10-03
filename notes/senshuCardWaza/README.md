# 選手カードの技データ（実験場 card2D.json）の作り方

統括チャットの一時作業場にしか無かったスクリプトの退避（2026-10-04）。本番の集計スクリプトを作るときの元にする。

## 順番
1. `load.py` … `results/*.json` を読み、艇ごとの表 `boats.pkl` とレースの表 `races.pkl` を作る（作業場で実行）
2. `newWaza5.py` … `docs/next/senshuCard/card2.json` と `boats.pkl` から技を計算し、`docs/next/senshuCard/card2D.json` を書く
   - `lib.py` の `load()`（欠場・進入なしを除く）と `eb()`（ベータ二項の経験ベイズで順位を付ける）を使う
   - チルトダッシュだけは card2.json の旧値を流用している（チルト角の元データは未特定）
3. `addGlyph.py` と `sharpen.py` … キルゴUの字形を足すとき（`sharpen(K, -14, 1.04, 0)` がCパターン）。書体ファイル自体はリポジトリに置かない（再配布禁止）

## 注意
- パスは作業場の絶対パスのまま。使うときに書き換える
- 技の定義・段・技名の決まりは Project の claude/senshuCardLaunch.md が正
