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

## 2026-11-08 作り直し（本番 #1004）で足したもの・直したもの

- `six/shootSaisaku.py` … いまの本番の画面から図31枚を撮る（`SHOOT=prod python3 six/shootSaisaku.py [top race hl motor maint rest players uranai ichimark]`）。図ごとに「切り出す範囲」と「番号を付ける要素」を書く。要素の頭に「→」を付けると、手前に別の文字があっても折れ線でその要素まで線を引く
- `six/shootLib.py` … 撮影の共通部品。日本語の画面で撮る（locale ja-JP・ブラウザは `--lang=ja-JP` で起動。付けないと日付の入力欄が 04/01/1990 になる）。図の上端・下端で文字が途中で切れるときは、空いた行まで詰める（`trim`）
- `fig.py` … 番号の丸と線。線は、その高さで最初に出てくる文字や枠の手前で止める（`clear_x`）。カードの縦の枠線は越えて考える（`ink_x`）。2けたの番号は字を小さくする。数字は濃い色で描く
- `next/dark.py` … 左の白い余白を画面の左端と同じ色で塗る。引き出し線が通る行は線の色を拾わない（拾うと、線が左端から丸の数字を横切る）
- `next/toSaisaku.py` … `python3 next/toSaisaku.py next` で実験場（`docs/next/torisetsu.html`・`docs/next/torisetsuImg/`）、`prod` で本番（`docs/torisetsu/`）に書き出す
- 撮るときのデータは、11/7 と 11/8 の出走表がそろった版（main 3f7f9fb）を `git worktree` で出して `:8112` で配る。いまの作業ツリーだと1日分しかなく、撮れない図がある
- 出したあとの確かめ方：31枚すべてで番号の数と説明の項目数が一致すること、左端に線の色が残っていないこと、全図を目で見ること

## 注意

- 図の生 PNG は入れていない（撮り直せば作れる）。本番の図は `docs/torisetsu/img/` にある
- 本番へ出すのはけんの裁定が要る。実験場（`docs/next/` だけ）は lintGuard PASS でマージしてよい
