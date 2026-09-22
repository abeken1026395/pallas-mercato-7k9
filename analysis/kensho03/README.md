# 検証03「F持ちのインは遅れるのか」の集計（2026-08-27 と 2026-09-22）

- buildFmochiTen.py：本文の10年集計（2016-11-01から2026-08-27）。入力はローカルの `localdata/kfilesTen/`（Kファイルの月別CSV）と `C:\Users\USER\bfiles\rankHistory.json`
- stage1.py・stage1b.py・stage2.py・stage3.py：2026-09-22 の改修で足した集計（置換による偶然の幅・級別・隠れF・年ごと）。`stage0` は buildFmochiTen.py の出力先だけを作業フォルダに変えた複製で、元の出力 fmochiTen.json と全項目一致を確かめてから使った
- 出力はリポジトリの外（作業フォルダ）に書く。スクリプト中の絶対パスはその作業フォルダを指している
- 公開ページ：/kensho/fmochi/（PR #505）
