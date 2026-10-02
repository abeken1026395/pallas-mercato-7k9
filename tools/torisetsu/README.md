# トリセツの作り直しの道具（2026-10-01 保全）

本番 `docs/torisetsu/`（main 125dbd1 時点）と実験場 `docs/next/torisetsu.html`（版 n）を作った道具一式。
クラウドのコンテナにしか無かったものを、消えないようにリポジトリの `tools/torisetsu/` に置いた（2026-10-01 けん「消えない様にしっかり道具格納してて」）。サイト（`docs/`）の外なのでページとしては出ない（リポジトリは公開なので GitHub 上では読める。秘密情報は入れない）。

## 中身

- `book/p0からp3b.html` … 本文の正本（部ごと）。文章を直すのはここ
- `book/newG01.html`・`newG03.html` … 出走表・モーターの節の書き換え版（p2/p3 に取り込み済み）
- `next/shell.html` … 外枠（CSS・JS・目次・戻るボタン・水紋）。版表示は `var VER='n'`
- `next/build.py` … shell と部を組み立てて `next/index.html` を作る
- `fig.py` … 番号の丸を描く共通部品（shootFigs.py が読む）
- `next/shootTop.py` … トップの図3枚（figTopNav・figTopKaisai・figTopKensho）
- `next/shootUranai.py` … 選手占いの図4枚（figUranai・figUranaiCheck・figUranaiMine・figUranaiRace）。撮ったあと dark.py・cue.py を回し、cue.json は既存の値に2件を足す形で合わせる
- `next/shootFigs.py` ほか `shoot*.py`・`probe*.py`・`cap.py` … 本番ページを Playwright で撮って図を作る（番号の丸は要素の矩形から自動）
- `next/dark.py`（図の左の白帯を地の色に）・`cue.py`（オレンジの丸を検出して cue.json）
- `next/toProd.py`（本番 `docs/torisetsu/` へ・外部リクエスト0）・`toDocs.py`（実験場へ）
- `next/delaSub.woff2`・`delaChars.txt` … 見出し書体の切り出し（153字・SIL OFL）
- `next/verifyHaran.py` … 出走表と見どころの①着外の一致を数える

## 使い方

1. `tools/torisetsu/` の中身（book・next・fig.py）を `/home/claude/` の下に写す（スクリプトが絶対パスで書かれている）。撮影の前に `python3 -m http.server 8112 -d docs` でサイトを手元に出す
2. 足りないものを入れる：`npm pack @fontsource/dela-gothic-one@5.3.0 @fontsource/zen-kaku-gothic-new@5.3.0` を `next/fonts/` に展開／React 18.2.0 の umd を `/home/claude/vendor/` に
3. Playwright は Chromium（`/opt/pw-browsers/chromium`）で、`service_workers="block"` が要る（sw.js が route を素通りさせる）
4. 図を撮る → dark.py → cue.py → build.py → toDocs.py で実験場 → けんが見て承認 → toProd.py で本番
5. 道具を直したら、ここにも写し戻す
6. 見出しに新しい字を使ったら増えたら、Dela の切り出しを作り直す（delaChars.txt に足す）

## 注意

- 図の生 PNG は入れていない（撮り直せば作れる）。本番の図は `docs/torisetsu/img/` にある
- 本番へ出すのはけんの裁定が要る。実験場（`docs/next/` だけ）は lintGuard PASS でマージしてよい
