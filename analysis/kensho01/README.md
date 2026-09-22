# 検証01「勝負駆けは効くのか」の集計（2026-09-22）

- 設計（集計の前に固定）：design.md
- 入力：ローカルのKファイルから作った月別CSV（`scripts/kdataFromLzh.py` の出力、2016-11-01から2026-08-31）と、Bファイル由来の `C:\Users\USER\bfiles\rankHistory.json`。どちらもリポジトリには入れていない
- 実行順：stage0.py（節の復元と準優判定の再現）→ stage1.py（設計どおりの比較）→ stage2.py（坂をならした段差。stage1_core.py を読み込む）
- 出力はリポジトリの外（作業フォルダ）に書く。スクリプト中の絶対パスはその作業フォルダを指している
- 公開ページ：/kensho/shobugake/（PR #510）
