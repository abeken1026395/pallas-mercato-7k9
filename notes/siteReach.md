# siteReach ─ 流入元の記録（URLの貼り方）

siteReachPlan20260911 V4。コードの変更はない。外にURLを貼るときの形だけを決めて記録する。

## 貼るURLの形

外に貼るURLの末尾に `?from=` を1つだけ付ける。

| 値 | 貼る場所 | 例 |
|---|---|---|
| `?from=desc` | YouTube の動画の概要欄 | `https://abeken1026395.github.io/pallas-mercato-7k9/kensho/ninki/?from=desc` |
| `?from=yt` | YouTube の概要欄以外（チャンネルのリンク欄・固定コメントなど） | `https://abeken1026395.github.io/pallas-mercato-7k9/?from=yt` |
| `?from=oc` | LINE オープンチャット | `https://abeken1026395.github.io/pallas-mercato-7k9/payouts/?from=oc` |

- 値はこの3つだけ。増やすときはこの表に先に書き足してから使う
- 貼るのは検索に開いている35本（トップ・検証5本・用語辞典・24場・場の文化・実況アナ・万舟25本）を基本にする。閉じたページ（出走表・見どころなど）に付けても表示は変わらない
- ページ側のコードは `?from=` を読まない。付けても付けなくても表示は同じ
- 各ページの canonical は `?from=` の無いURLなので、検索エンジンには同じページとして扱われる

## `?from=` は補助

- 計測を入れれば（V5 Cloudflare Web Analytics）、参照元（youtube.com・line.me など）はブラウザが送る情報から別に見える。`?from=` は、参照元が送られない経路（アプリ内ブラウザ・コピーして貼られたURLなど）を見分けるための補助
- 2026-09-14 時点で V5 は保留（トークン未提供）。計測が入るまでは `?from=` を集計する仕組みは無い

## 既存のURLは書き換えない

- すでに概要欄・オープンチャット・読者のブックマークにあるURLは、そのままにする（読者が保存しているため）
- `?from=` を付けるのは、これから新しく貼るURLだけ
