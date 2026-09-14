# siteReachPlan20260911 ─ 到達性C案（読み物だけ検索に開く）

前提：`notes/facts.md` 7章「C 到達性」の別テーマ扱いを、2026-09-11 の裁定で解除する。
関門・禁止・打ち切り・`[updates]`・worktree の扱いは `notes/pageAuditFixPlan20260911.md` 第2節をそのまま適用する（M1 の許可範囲は各テーマの「触ってよいファイル」）。

## 0. 裁定（2026-09-11）

| # | 項目 | 確定 |
|---|---|---|
| 1 | 到達性 | C案。読み物だけ検索に開き、毎日更新される判断画面は閉じたままにする |
| 2 | 開くページ（35本） | トップ／`kensho/` 5本／`glossary/`／`stadium/`／`fan/`／`announcers/`／万舟25本（総合＋24場） |
| 3 | 閉じたまま（14本） | `racers/`・`highlights/`・`results/`・`motor/`・`motor-maintenance/`・`players/`・`updates/`・`uranai/`・`aisho-suminoe/`・`shobuun-suminoe/`・`next/` 3本・`probe/` |
| 4 | og:image | 当面は既存の `icon512.png` を使う。専用画像（1200×630）は別テーマ |
| 5 | 計測 | Cloudflare Web Analytics。トークンが未提供ならV5は実施せず記録して次へ |
| 6 | Search Console | 検証値が未提供ならV6は実施せず記録して次へ |

## 1. テーマ（この順に回す）

### V1 検索に開く（robots と noindex）

触ってよいファイル：`docs/robots.txt`／第2節の開くページ35本の `index.html`／その正本テンプレート（`scripts/templateKensho.html`・`scripts/templateTaiju.html`・`scripts/templateFmochi.html`）

- `docs/robots.txt` を次に置き換える。**閉じたままのページを1本ずつ Disallow で列挙する**（許可の書き忘れより、拒否の書き忘れの方が害が大きいため、`Allow` に頼らない）

```
User-agent: *
Disallow: /pallas-mercato-7k9/racers/
Disallow: /pallas-mercato-7k9/highlights/
Disallow: /pallas-mercato-7k9/results/
Disallow: /pallas-mercato-7k9/motor/
Disallow: /pallas-mercato-7k9/motor-maintenance/
Disallow: /pallas-mercato-7k9/players/
Disallow: /pallas-mercato-7k9/updates/
Disallow: /pallas-mercato-7k9/uranai/
Disallow: /pallas-mercato-7k9/aisho-suminoe/
Disallow: /pallas-mercato-7k9/shobuun-suminoe/
Disallow: /pallas-mercato-7k9/next/
Disallow: /pallas-mercato-7k9/probe/
Disallow: /pallas-mercato-7k9/data/

Sitemap: https://abeken1026395.github.io/pallas-mercato-7k9/sitemap.xml
```

- 開く35本から `<meta name="robots" content="noindex, nofollow">`（表記ゆれ `noindex,nofollow` も）を削除する。**生成物ではなく正本テンプレートを直す**
- 閉じたままの14本の `noindex, nofollow` は**そのまま残す**（robots.txt と二重でかける）
- `docs/data/` 配下の運用メモ（`kansenki/SECRET_SETUP.md` など6本）は Disallow で塞ぐ
- M2：開く35本で `noindex` が0件、閉じた14本で14件。`robots.txt` の Disallow 行が13行
- M4：Playwright で開く35本のうち5本を開き、JS例外0・表示に変化がないこと

### V2 description と OGP

触ってよいファイル：開く35本の `index.html` と、その正本テンプレート3本

各ページの `<head>` に次を入れる（すでに `canonical` があるので、その直後に置く）。

```
<meta name="description" content="〈本文から作る80〜120字〉">
<meta property="og:type" content="article">
<meta property="og:title" content="〈title から「| データ攻め」を除いたもの〉">
<meta property="og:description" content="〈description と同じ〉">
<meta property="og:image" content="https://abeken1026395.github.io/pallas-mercato-7k9/icon512.png">
<meta property="og:url" content="〈canonical と同じ〉">
<meta property="og:site_name" content="データ攻め">
<meta name="twitter:card" content="summary">
```

- description は**そのページの本文から作る**。煽り語・感嘆符・絵文字は使わない。数字を入れるときは分母か期間を添える
- 万舟24本は場名と期間が違うだけなので、同じ型で場名を差し替える（例「〈場名〉のR別万舟率。〈開催日数〉開催日・〈レース数〉レースを数えた記録です。」。数値は各ページの実物から取る）
- `og:title` に「｜」「|」が混在しているので、`og:site_name` に寄せて本文側からは外す
- M2：開く35本すべてに description・og:title・og:image・og:url がある。閉じた14本には**入れない**
- M4：1本を開き、`document.querySelector('meta[property="og:image"]').content` が200で返ること

### V3 sitemap.xml

触ってよいファイル：`scripts/buildSitemap.py`（新規）・`docs/sitemap.xml`（生成物）・`.github/workflows/`（新規WF1本）

- 開く35本のURLだけを列挙する。`lastmod` は各ファイルの最終コミット日時（`git log -1 --format=%cI -- <path>`）
- `priority`・`changefreq` は書かない（Googleは無視するため）
- WFは日次（JST 04:00・`updateNigeSecond.yml` の03:30と重ならない時刻）＋手動実行。`docs/` を触るのでPagesが起動する
- M2：`sitemap.xml` の `<url>` が35件、閉じた14本のURLが0件
- マージ後、WFを手動実行し、生成物で同じ件数を数え直す

### V4 流入元の記録（コードなし）

触ってよいファイル：`notes/siteReach.md`（新規）

- YouTube概要欄・オープンチャットに貼るURLの形を決めて記録する：`?from=yt`・`?from=oc`・`?from=desc`
- Cloudflare側では参照元（youtube.com・line.me 等）も出るため、`?from=` は補助であることを明記
- 既存のURLは書き換えない（読者が保存しているため）

### V5 Cloudflare Web Analytics（トークンが提供された場合のみ）

触ってよいファイル：49本すべての `index.html` と正本テンプレート

- `</body>` の直前に、Cloudflareが発行するビーコン1行を入れる（Cookieなし・利用者を追跡しない）
- **閉じたページにも入れる。** 検索に出さないことと、読者の行動を数えることは別
- 入れる前に代表5本（トップ・出走表・見どころ・万舟総合・整備一覧）のLCPを測り、入れた後にもう一度測る。**2.5秒を超えたら、そのPRをマージせず記録して次へ**
- M2：49本すべてにビーコンが1つずつ（重複0）

### V6 Search Console（検証値が提供された場合のみ）

触ってよいファイル：`docs/index.html`

- `<meta name="google-site-verification" content="...">` をトップだけに入れる
- sitemapの登録はけんがSearch Console側で行う（作業ではない）

## 2. 終了時

1. `notes/facts.md` 7章の「C 到達性」の行を、実施した内容に書き換える（「別テーマ」をやめ、開いた35本・閉じた14本の方針を記す）
2. `notes/state.md` に裁定（第0節）と結果を追記する
3. けんへ返すのは次の1行だけ

```
完了 / 実施テーマ数 / 保留（番号と一言） / 差し戻し（番号） / 最終 main SHA
```
