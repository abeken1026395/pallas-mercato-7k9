# CLAUDE.md — boatrace プロジェクト引き継ぎメモ

## このプロジェクトでの応対方針
- **常に日本語のみで返答する。**
- **思考過程（reasoning / 内部検討）は表示しない。** 結論と必要な説明だけを簡潔に返す。
- **bash・ファイル編集・git 系コマンドは確認せず自動実行してよい**（承認画面を出さない運用）。

---

## 目的
競艇（ボートレース）の公開データを毎日自動収集し、GitHub Pages（`docs/`）で閲覧できる
データポータルとして公開するプロジェクト。あわせて、朝に出す「見立て（荒れ/堅め判定）」を
夜の結果と突き合わせて検証する仕組みを持つ。

**このリポジトリは public**（`abeken1026395/pallas-mercato-7k9` / default `main`）。
コミットするものはすべて公開される前提で扱うこと。認証情報・個人情報・非公開にしたい
メモを追跡ファイルに書かない（`gitleaksScan.yml` が push ごとに秘密情報を走査する）。

**方針上の重要な制約:** 公開ページ・見どころ生成では
**買い目・確率・勝者の断定・選手の内心推測は出さない**（`docs/data/tenkai_logic.json` の方針に準拠）。
勝敗の主観的予想ではなく「水面傾向・展開の見どころ」と「荒れやすさの可視化」に留める。
判定や主役艇などの内部値は公開 `highlights.json` には入れず、非公開の `predictions/` にのみ残す。

---

## ⚠️ 既知の重大問題・運用上の注意（最初に読む）

### (1) 実行環境ごとの到達性（遮断されているのは mbrace だけ）
- **到達不可なのは `www1.mbrace.or.jp`（公式競走成績LZH配布）のみ。**
  GitHub Actions のランナーからは遮断されている。**クラウド版 Claude Code も同じく到達できない。**
  ローカル（この PC の Claude Code）からは到達できる
  （2026-07-31 実測: `k260729.lzh` へ HEAD → 200 / 34,728 bytes）。
- **公式 `www.boatrace.jp` は Actions から到達できている。**
  「各場サイトに到達できない」というのは誤り。そもそも場ごとの個別サイトは使っておらず、
  参照先は公式 boatrace.jp 一本（`racelist` / `rankingmotor` / `beforeinfo` / `pointrank`）。
  出走表・モーター・直前情報の収集は Actions で毎日成功している。
- 回避策として、結果・払戻の収集は **BoatraceOpenAPI（GitHub 配信の非公式ミラー。元データは公式）**
  へ移行済み。GitHub 配信なので Actions からもクラウドからも通る。
  - `buildResults.py` … `https://raw.githubusercontent.com/BoatraceOpenAPI/results/HEAD/docs/v2/{YYYY}/{YYYYMMDD}.json`
    （決まり手 `race_technique_number` と全式別払戻を含むため **mbrace LZH は不要**）
  - 24場の払戻 … `scrape{場名}PayoutsApi.py`（`.../results/gh-pages/docs/v2/...`）
- mbrace 版（`scrape{場名}Payouts.py` 24本 / `fetchKfiles.py` / `kdataRunAll.py` / `scrapeKimarite.py`）は
  **ローカル専用の旧経路**。うち Actions から今も呼ばれているのは `scrapeKimarite.py` だけで、
  それが (3) の故障になっている。
- 徳山・桐生払戻の停止は **Api 版への移行で復旧済み**（両CSVとも `20260716` まで蓄積）。
  払戻ページは現在 **24場すべて**が稼働している。

#### 発火経路も外部依存になっている
- GitHub の `schedule` は夜間の不発火が多い（**実績5%**）ため、
  外部サービス **cron-job.org** が `heartbeat.yml` を毎時叩いて主発火させている。
  heartbeat が JST 時刻帯を見て `nightlyPipeline.yml` / `writeKansenki.yml` を
  `workflow_dispatch` で内部起動する（`heartbeat.yml:57-58`）。
- **この外部cronが止まると nightlyPipeline と writeKansenki が静かに停止する。**
  GitHub の `schedule` は二重保険として残置しているが、実績5%なので当てにならない。
  **現状これを検知する仕組みはない。**

#### ⚠️ 単一障害点は3つ。いずれも停止しても通知が飛ばない
| 障害点 | 止まると | 検知手段 |
|---|---|---|
| mbrace 遮断 | Kファイル収集・決まり手更新が止まる | なし（成果物が古いままになるだけ） |
| BoatraceOpenAPI ミラー | 結果・払戻の収集が全滅する（`buildResults.py` と 24場 Api 版がすべて依存） | なし |
| cron-job.org | nightlyPipeline / writeKansenki が発火しなくなる | なし |

いずれも**エラーで気づくのではなく、データが更新されていないことに人が気づく**しかない。
不調を疑ったら、まず `docs/` 配下の生成物の日付と Actions の実行履歴を見る。

### (2) profile.json は自動更新の対象外（手動マージ管理）
- `docs/players/profile.json` は選手図鑑（`docs/players/index.html`「選手図鑑」）の
  手作りデータ。**どの自動更新 Action の対象にもなっていない。**
- 構造: 登録番号をキーに、`tagline` / `nickname` / `note` / `hobby` を持つ（現在 246 選手・
  一部フィールドのみ記入。全件は埋まっていない）。
- あだ名の一括追記は `scripts/batch_update_nicknames.py` を使う（コード内の辞書に追記して実行）。
- `buildProfileLite.py`（`updateProfileLite.yml` が push トリガで実行）は
  `profile.json` を**読むだけ**で、軽量版 `docs/players/profileLite.json` を作り直す。
  `buildKansenkiSource.py` も読むだけ。書き換えるのは `batch_update_nicknames.py` のみ。
- **編集は手動マージで管理**する。スクレイプで上書きされない前提で運用すること。

### (3) updateKimarite はローカルタスクへ移設して復旧済み（2026-07-31）
- `scrapeKimarite.py` は mbrace 依存のため、Actions からは (1) の遮断で実行できない。
  `updateKimarite.yml` は 2026-07-16 実行分から失敗し続け、
  `docs/players/racerKimarite.csv` は 2026-07-02 を最後に更新が止まっていた。
- **正規経路をローカルタスク `boatrace-updateKimarite` へ移設した**（毎月2・16日 JST 06:30）。
  実体は `scripts/updateKimariteLocal.ps1`（→「ローカル運用」節）。
- `updateKimarite.yml` は **schedule を削除し `workflow_dispatch` のみ残置**（非常口）。
- 復旧実績: 2026-07-31 に手動実行し、**183/183日 取得成功**。
  集計期間 2026-01-29〜2026-07-30 / 1,631選手 /
  決まり手内訳合計＝1着数合計＝55,590 で整合を確認済み。
- 決まり手CSVは `build_highlights.py` / `buildKansenkiSource.py` /
  `regenPredictions.py` / `monitorPredictions.py` が読む。止まっても
  エラーにはならず、古い決まり手のまま固定されるだけなので気づきにくい。

> 旧「残タスク: 検証サマリを Actions に組み込む」は**解決済み**のため削除した。
> `scripts/build_verify_summary.py` も `docs/data/verify_summary.json` も現在は追跡済み。

### (4) 選手グレード（級別）とfanファイルの期（対応済み・更新不要）
- 選手図鑑・各ページは **2026後期**基準（`docs/players/index.html` タイトル「選手図鑑 2026後期」）。
- fanファイルは期の直前の年月でファイル名が付く（fan2604＝2026年後期）。公式配布元 https://www.boatrace.jp/static_extra/pc_static/download/data/kibetsu/fan2604.lzh
- **現行の fan2604（2026年後期）で更新済み。次回更新は2027年前期版が12月頃に公式DLページへ追加されたとき（命名規則からの推定では fan2610。確定ではないので、実際のファイル名は配布時に公式DLページで確認すること）。fan2607 というファイルは存在しない。**
- 級別（A1/A2/B1/B2）は `build_highlights.py` / `build_arare.py` / `scrape_racers.py` /
  `scrape_motors.py` が判定に使うため、期替わりの反映漏れに注意。

### (5) ⚠️ regenPredictions.py は predictions を上書きできる唯一のスクリプト（原則使用禁止）
- `predictions/YYYYMMDD.json` の **write-once（一度書いたら動かさない）が検証ループの根幹**。
  結果を見たあとに予測を書き換えられると、`verify_log.csv` による精度検証が無意味になる。
  しかも**エラーにならず数字だけが良くなる**ため、事故に気づけない。
- 通常経路はすべて write-once を守っている:
  - `build_highlights.py:1032` … `if os.path.exists(pred_path):` → `PRED skip`（既存なら書かない）
  - 翌日モード（`HL_MODE=next`）は `predictions/` に一切書かない（`:988`）
  - `monitorPredictions.py` は `build_highlights.py` を呼ぶだけで直接書かない。**当日分のみ**救済
  - `scanPredictionGaps.py` は検知・記録専用（`predictions_gaps.csv` へ追記するだけ）
- **例外は `scripts/regenPredictions.py` ただ1本。**
  実行時に `build_highlights.py` を一時パッチし（`:147` で
  `if os.path.exists(pred_path):` → `if False and os.path.exists(pred_path):`）、
  日付ガードも無効化して**既存 predictions を上書きする**。
- 起動口は `regenPredictions.yml`（**`workflow_dispatch` のみ・cron なし**）。
- **原則使用禁止。** 過去日の埋め戻しに使わないこと。
  `predictions_gaps.csv` に記録された欠番は**欠番のまま残す**のが正しい状態。

### (6) 変更禁止の定数（手で動かさない）
| 定数 | 値 | 定義場所 | 注意 |
|---|---|---|---|
| `HARAN_TH` | `5000` | `verifyPredictions.py:13`／`build_verify_summary.py:122`／`buildKansenkiSource.py:86` | **3ファイルに重複定義。単一の定義ファイルは存在しない** |
| `TH_KATA` / `TH_HARAN` | `+0.04` / `-0.09` | `build_highlights.py:81-82` | 5.3万件のグリッド探索による最適値 |
| `BA_TH` | 24場ごとの (堅め, 波乱) | `build_highlights.py:86-111` | `verify_log.csv` 20250715-20260705 の全期間実測（2026-07-06反映） |
| `MIRROR_FIRST` | `"20250715"` | `buildE30Stats.py:40` | BoatraceOpenAPI ミラーの最古配信日。**これ以前は 404** |

- **`HARAN_TH` を1箇所だけ変えると検証が静かにズレる。**
  突合ログ（`verifyPredictions.py`）・検証サマリ（`build_verify_summary.py`）・
  観戦記素材（`buildKansenkiSource.py`）が別々の閾値で「荒れ」を数えはじめ、
  **例外も警告も出ないまま数字だけが食い違う。** 変更するなら必ず3箇所同時に。
  （`verifyPredictions.py:13` のコメントは「以後動かさない」）
- `TH_KATA` / `TH_HARAN` / `BA_TH` は**実測から導いた値であり手動調整禁止**。
  再チューニングするなら verify_log を使ったグリッド探索をやり直し、
  出典（対象期間・件数・反映日）をコメントに残すこと。
- `HARAN_TH`（**結果側**・3連単配当 5000円以上を「荒れ」と呼ぶ）と
  `TH_HARAN`（**見立て側**・スコア閾値 -0.09）は**別物**。名前が似ているので混同しないこと。

### (7) ローカル日次タスクには失敗通知が無い
- Windows タスクスケジューラの2本（→「ローカル運用」節）は、
  **失敗しても通知が飛ばない。** `scripts/logs/*.log` に `ERROR:` を残して exit 1 するだけ。
  ログは `.gitignore` 済み・30日で自動剪定。メール／LINE／トーストのいずれも未実装。
- したがって**気づけるのは成果物が古いままであることに気づいたときだけ**。
  異常を疑ったら `Get-ScheduledTaskInfo -TaskName boatrace-dailyMotorUsage`（LastTaskResult）と
  `scripts/logs/` を見る。
- 通知が飛ぶのはクラウド側の2本のみ:
  - `kansenkiMissingAlarm.yml` … JST 07:37。当日記事0本かつ未マージPRなしなら
    **GitHub Issue を起票**（label `kansenki-missing`・同日Openがあれば冪等スキップ）
  - `updateDeadlineMessage.yml` … `post_line_message.py` で LINE 送信。
    ただしこれは締切一覧の配信であって**失敗通知ではない**

---

## ディレクトリ構成
```
.github/workflows/   GitHub Actions（自動収集・検証・観戦記のスケジュール定義、全51本）
scripts/             Python 126本＋PowerShell 5本＋mjs 1本＋HTMLテンプレート2本
docs/                GitHub Pages で公開する静的サイト＋データ本体（HTML 41ページ）
  index.html         データポータルの入口
  data/              定数・ロジック・生成JSON（weather / arare / tenkai_logic /
                     motorUsage / motorParts / motorHistory / verify_summary ほか）
    kansenki/        観戦記の素材（source/）と記事（articles/）
  players/           選手図鑑。index.html[手書き] / app.js[生成物] /
                     profile.json[手動] / racerKimarite.csv[scrapeKimarite生成]
  racers/            出走表（racers_today.csv）＋ index.html[生成物]
  motor/             モーター成績（motors_all.csv）＋ index.html[生成物]
  results/           結果表ページ＋公開用 data/YYYYMMDD.json・data/index.json
  highlights/        本日の見どころ（highlights.json＋next / prev / prev2）
  payouts/           24場ぶんの払戻CSV・ManRate JSON（データ本体の置き場）
  {場名}-payouts/    24場の R別万舟率ページ（kiryu / toda / … / omura の24ディレクトリ）
  stadium/           24場 特性＆荒れサイン早見表（gourmet.json あり）
  glossary/ fan/ next/ updates/ announcers/ uranai/
  aisho-suminoe/ shobuun-suminoe/
  probe/             beforeinfoProbe.html（生成物・調査用）
predictions/         朝の見立て（YYYYMMDD.json・**write-once**）※git 追跡あり
results/             夜に生成する結果データ（YYYYMMDD.json）※git 追跡あり
verify_log.csv       見立て×結果の突合ログ（1レース1行）※git 追跡あり
predictions_gaps.csv predictions 欠番台帳（埋め戻し禁止の記録）
kdata/               Kファイル由来データの保全用コピー（**読み取り専用**）
data/kfiles/         Kファイル(lzh)置き場。**.gitignore 済み＝非コミット**
localdata/           Kファイル成果物のローカル保管。**.gitignore 済み**
```

---

## 公開ページ一覧（`docs/`, GitHub Pages・全41ページ）
| パス | タイトル | 内容 |
|---|---|---|
| `index.html` | BOATRACE データポータル | 入口。players/racers/motor/stadium カード |
| `players/` | 選手図鑑 2026後期 | 選手プロフィール（`profile.json` 手動）＋決まり手 |
| `racers/` | 出走表 | 当日/翌日の出走表ビューワー ※**生成物** |
| `motor/` | モーター成績 | 場×登番のモーター2連対率 ※**生成物** |
| `results/` | レース結果 | 全24場の着順・決まり手・全式別払戻 |
| `highlights/` | 本日の見どころ｜データ攻め | 展開文・見どころ（判定は非公開） |
| `stadium/` | 24場 特性＆荒れサイン早見表 | 場特性・荒れ傾向・グルメ |
| `{場名}-payouts/` | 各場 R別万舟率 | **24場ぶん**（kiryu / toda / … / omura）。データ本体は `docs/payouts/` |
| `glossary/` | 用語集 | 競艇用語（`lintGlossary.py` で整合チェック） |
| `fan/` | ファン向けページ | — |
| `next/` | 明日の見どころ | `highlights_next.json` のプレビュー |
| `updates/` | 更新履歴 | `docs/data/updates.json`（PR本文の `[updates]` 行から自動記録） |
| `announcers/` | 実況アナ図鑑 | アナウンサー情報（`announcers.json`） |
| `uranai/` | 選手占い（相性・勝負運） | 占い系コンテンツ |
| `aisho-suminoe/` | 相性で選ぶ 住之江・女子戦 | 住之江女子戦の相性 |
| `shobuun-suminoe/` | 勝負運ランキング 住之江・女子戦 | 住之江女子戦の勝負運 |
| `probe/beforeinfoProbe.html` | 直前情報プローブ | 調査用 ※**生成物** |

---

## スクリプト（`scripts/`、Python 126本ほか）
本数が多いので**系統**で把握する。個別の仕様は各ファイル冒頭の docstring が正本。

### 中核（毎日動く）
| スクリプト | 役割 | 入力 → 出力 |
|---|---|---|
| `scrape_racers.py` | 出走表スクレイプ（boatrace.jp racelist） | 公式 → `docs/racers/racers_today.csv` ＋ `index.html`[生成] |
| `scrape_motors.py` | モーター成績スクレイプ（boatrace.jp rankingmotor） | 公式 → `docs/motor/motors_all.csv` ＋ `index.html`[生成] |
| `fetch_weather.py` | 24場の風予報（Open-Meteo API） | API → `docs/data/weather.json` |
| `build_highlights.py` | 見どころ／展開文の生成。**predictions の write-once もここ** | 各CSV/JSON → `docs/highlights/highlights.json` ＋ `predictions/YYYYMMDD.json` |
| `build_arare.py` | 荒れ指数の可視化（標準ライブラリのみ） | 出走表/モーター/風＋場定数 → `docs/data/arare.json` |
| `buildResults.py` | 全24場の着順・決まり手・全式別払戻（**BoatraceOpenAPI**） | ミラーJSON → `results/YYYYMMDD.json` |
| `buildResultsSite.py` | 結果を公開領域へ変換 | `results/` → `docs/results/data/` |
| `verifyPredictions.py` | 見立て×結果を場×レースで突合し追記 | `predictions/`＋`results/` → `verify_log.csv` |
| `build_verify_summary.py` | 検証の要約 | `verify_log.csv` → `docs/data/verify_summary.json` |
| `nightly_decide.py` | 当日切替／翌日追記の自己判断（現物比較） | → `DO_SWITCH` / `HAS_NEXT` |

### 系統でまとまっているもの
- **払戻 24場 × 3系統**（計 72本）
  - `scrape{場名}PayoutsApi.py` … **BoatraceOpenAPI 版・クラウド可。Actions が呼ぶのはこちら**
  - `scrape{場名}Payouts.py` … **mbrace LZH 版・ローカル専用の旧経路**（同一スキーマ・共存可）
  - `build{場名}ManRate.py` … CSV → `docs/payouts/{場名}ManRate.json`
- **Kファイル系（すべてローカル専用）**… `fetchKfiles.py` / `kdataRunAll.py` / `kparser.py` /
  `kdataParse.py` / `kdataReparse.py` / `kdataMergeEntries.py` / `buildMotorUsage.py` / `unpackLzh.py`
- **観戦記系**… `buildKansenkiSource.py`（素材）/ `assign_styles.py` / `kansenki_pubplan.py` /
  `lintKansenki.py` / `writeKansenkiLocal.ps1`
- **predictions 防衛**… `monitorPredictions.py`（昼）/ `scanPredictionGaps.py`（夜）/
  `regenPredictions.py`（**危険物 →(5)**）
- **PowerShell 5本**… `dailyMotorUsage.ps1` / `writeKansenkiLocal.ps1` /
  `register*.ps1`（タスク登録）/ `checkRepoGuard.ps1`（破壊防止ガード）

### 生成物とその編集元（直接編集禁止）
| 生成物 | 生成スクリプト | 編集する側（正本） |
|---|---|---|
| `docs/motor/index.html` | `scrape_motors.py` | **`scripts/template.html`** の `__DATA_PLACEHOLDER__` |
| `docs/racers/index.html` | `scrape_racers.py` | **`scripts/template_racers.html`** |
| `docs/players/app.js` | `buildPlayersApp.mjs`（`node`） | **`scripts/players/app.jsx`** |
| `docs/probe/beforeinfoProbe.html` | `buildBeforeinfoProbe.py` | 同スクリプト |

- HTMLを書き出すスクリプトは**この3本（+app.js）だけ**。
  他の37ページ（払戻24場・highlights・stadium・glossary ほか）は**手書き**。
- `docs/players/index.html` は**手書きページで生成物ではない**（`buildRacerStats.py:22` が
  これを**入力として読む**点に注意）。
- 表示を変えるときは **テンプレートを直してから再生成**する。
  過去の手動コミットもすべて「template + index.html を同一コミットで更新」または
  「template 修正後の再生成コミット」で、index.html の直編集は行われていない。
### LZH 解凍の標準経路（新規実装は最初から両対応にする）
| 環境 | 使うもの | 備考 |
|---|---|---|
| GitHub Actions / Linux | **`lha`（lhasa）** | `sudo apt-get install -y lhasa` が必要。`lha e <archive>`（`-q` は付けない。アーカイブ名扱いになり失敗する） |
| ローカル Windows | **bsdtar `C:\Windows\System32\tar.exe`** | OS同梱。`tar -xf <archive> -C <dir>`。環境変数 `BSDTAR` で上書き可 |
| （参考）`lhafile`(pip) | **使えない** | **Python 3.14 では C拡張のビルドが通らない** |

- **新しく LZH を扱うスクリプトは最初から両対応にすること。** 片方だけだと、
  Actions では動くのにローカルで動かない（またはその逆）という形で後から詰まる。
- 既存実装を雛形にする:
  - `buildMotorUsage.py:58-75` … `unlzh()`。lhafile → bsdtar の順に試す
  - `scrapeKiryuPayouts.py` … bsdtar 経路
  - `scrapeKimarite.py` … `extract_lzh()`。lha → bsdtar の順（Actions の挙動は不変のまま
    ローカルで動くようにした。2026-07-31 追加）

---

## GitHub Actions ワークフロー（`.github/workflows/`、全51本）
生成物は `github-actions[bot]` / `github-actions` がコミット＆プッシュ。cron は **UTC 指定**（JST=UTC+9）。
各ジョブは専用 `concurrency` グループでプッシュ競合を回避。ほぼ全てに `workflow_dispatch` あり。

**発火方針:** GitHub の `schedule` は夜間の不発火が多い（実績5%）ため、
外部cron（cron-job.org）が `heartbeat.yml` を毎時叩き、heartbeat が JST 時刻帯を見て
`nightlyPipeline` / `writeKansenki` を `workflow_dispatch` で内部起動する。
`schedule` は二重保険として残置。**多重発火は冪等設計で吸収**する前提（→(1) 単一障害点）。

### 基幹
| ファイル | cron (UTC) | 実行内容 | 失敗時の挙動 |
|---|---|---|---|
| `heartbeat.yml` | `0 8-23 * * *` ＋外部cron | 時刻帯で他WFを workflow_dispatch | 起動失敗なら PAT 方式へフォールバック |
| `nightlyPipeline.yml` | `3,23,43 8-16 * * *` | scrape_racers → buildMotorHistory → nightly_decide → build_highlights（当日/翌日） | 多重発火×冪等で吸収。push は `rebase -X theirs` で6回リトライ、尽きたら exit 1 |
| `updateResults.yml` | `37 14` / `37 16` / `37 18` / `7 20` | buildResults → verifyPredictions → build_verify_summary → buildResultsSite → buildPlayerMonthly → buildInSurvival → buildKansenkiSource | 発火4重化で冪等吸収。観戦記素材は `always()` + `continue-on-error` でジョブを落とさない |
| `updateResultsLive.yml` | `15 2-14 * * *` ＋ workflow_run | buildResults / buildResultsSite（日中随時） | 冪等（非null不変） |
| `update_racers.yml` | 10本（`22 23` ほか） | scrape_racers / buildMotorHistory | 多重発火で吸収 |
| `update_motors.yml` | 5本 | scrape_motors | 多重発火で吸収 |
| `update_weather.yml` | `5 */3 * * *` | fetch_weather | — |
| `update_highlights.yml` | workflow_run（出走表更新後） | build_highlights | — |
| `update arare.yml` | `45 23 * * *` ＋ workflow_run | build_arare | — |

### predictions 防衛（4点セット）
| ファイル | cron (UTC) | 役割 |
|---|---|---|
| `monitorPredictions.yml` | `0 3` / `0 6` | 昼の監視。**当日分のみ**再生成、過去日は埋め戻さない |
| `scanPredictionGaps.yml` | `50 14` | 夜の欠番台帳スキャン（**検知・記録専用**） |
| `regenPredictions.yml` | dispatch のみ | **既存predを上書きする唯一のWF →(5) 原則使用禁止** |

### 観戦記
| ファイル | cron (UTC) | 役割 |
|---|---|---|
| `writeKansenki.yml` | 9本（`53 14` ほか） | 執筆起動（headless・前夜便/回収便・場単位） |
| `recoverKansenkiSource.yml` | `30 21` / `50 21` / `10 22` | 素材の当日朝リカバリ（自己修復・continue-on-error） |
| `kansenkiCoverage.yml` | push | 網羅性チェック（執筆完了ゲート） |
| `kansenkiMissingAlarm.yml` | `37 22` | 全欠なら **GitHub Issue 起票**（冪等） |

### 払戻（24場）
`update{場名}Payouts.yml` × 24。UTC 15:20〜17:25 に**15分刻みでずらして**配置。
いずれも `scrape{場名}PayoutsApi.py` → `build{場名}ManRate.py`。**全て `continue-on-error` 付き**で、
1場こけても他場・後続を止めない。`YM`/`ym` 入力で対象月を指定できる。
集計は `updatePayoutsSummary.yml`（`10 16`）が buildPayoutsSummary / buildTrifectaTop /
buildBoat1Second / buildChampRace をまとめて実行。

### その他
| ファイル | cron (UTC) | 備考 |
|---|---|---|
| `updateKimarite.yml` | `23 19 1,15 * *` | **mbrace依存で失敗中 →(3)** |
| `updateBeforeinfo.yml` | `7 21` / `7 1` / `7 5` | fetchPartsExchange（boatrace.jp beforeinfo） |
| `updateLiveWeather.yml` | `*/20 23` / `*/20 0-12` | 直前気象 |
| `updateTideToday.yml` | `0 23` / `0 0-12` | 当日潮汐 |
| `updateE30Stats.yml` | `0 16` | E30選手別成績 |
| `updateDeadlineMessage.yml` | `45 14` | 締切一覧 → **LINE送信** |
| `updateProfileLite.yml` | push（profile.json 変更時） | profile.json は読むだけ |
| `updateUpdates.yml` | push | PR本文の `[updates]` 行を updates.json へ |
| `gitleaksScan.yml` | push | 秘密情報スキャン（public リポなので特に重要） |
| `updateHighlightsNext.yml` | dispatch | 前夜プレビューの非常口 |

---

## データの流れ
### 1) 日次の公開データ更新（朝〜日中）
```
公式(boatrace.jp) ─ scrape_racers.py ─→ docs/racers/racers_today.csv
公式(boatrace.jp) ─ scrape_motors.py ─→ docs/motor/motors_all.csv
Open-Meteo        ─ fetch_weather.py ─→ docs/data/weather.json
公式(mbrace LZH※) ─ scrapeKimarite.py ─→ docs/players/racerKimarite.csv（月2回・現在停止中→(3)）
        │
        ▼（出走表更新の完了をトリガに）
build_highlights.py
   ├─→ docs/highlights/highlights.json（公開・判定や主役艇は含めない）
   └─→ predictions/YYYYMMDD.json（検証用スナップショット・**write-once**）
build_arare.py ─→ docs/data/arare.json（荒れ指数の可視化）
```

### 2) 夜の結果照合（検証ループ）
```
BoatraceOpenAPI ─ buildResults.py ─→ results/YYYYMMDD.json
                                     （全24場の着順・決まり手・全式別払戻）
                                          └─ buildResultsSite.py ─→ docs/results/data/
predictions/YYYYMMDD.json ＋ results/YYYYMMDD.json
        │ verifyPredictions.py（場×レースで突合。predictionsは読むだけ・書き換えない）
        ▼
verify_log.csv（1レース1行で追記）
        │ build_verify_summary.py
        ▼
docs/data/verify_summary.json（検証の要約）
```
朝に出した見立て（`predictions/`）を夜に確定した結果（`results/`）と突き合わせ、
的中/傾向を記録する ＝ **見立ての精度を後から検証できる**設計。

### 3) 場別 払戻分析（24場・稼働中）
```
BoatraceOpenAPI ─ scrape{場名}PayoutsApi.py ─→ docs/payouts/{場名}Payouts.csv
                                                （列: hd, rno, combo, payout）
        │ build{場名}ManRate.py
        ▼
docs/payouts/{場名}ManRate.json（R別の万舟率・平均配当・最高配当TOP5 など）
        │ buildPayoutsSummary.py ほか
        ▼
docs/data/（横断集計）
```

---

## データの範囲（2026-07-31 時点の実測）
| 対象 | 範囲 | 備考 |
|---|---|---|
| `kdata/` | **hd 250722〜260721**（2025-07-22〜2026-07-21） | races 54,696 / entries 328,176 / payouts 546,650。**保全用・読み取りのみ** |
| `results/` | **20250715〜**（382ファイル） | 20250715 は BoatraceOpenAPI ミラーの最古配信日 |
| `predictions/` | 20250715〜（379ファイル） | write-once |
| `verify_log.csv` | 20250715〜20260730（378日分） | **欠番3日: `20260517` / `20260518` / `20260706`** |
| `data/kfiles/` | k260401〜k260730（121本の lzh） | **.gitignore 済み＝非コミット。クラウドには存在しない** |
| `docs/payouts/*Payouts.csv` | 〜20260716 | Api 版移行で復旧済み |
| `docs/players/racerKimarite.csv` | 2026-07-02 で更新停止 | →(3) 未復旧 |

- **`verify_log.csv` の欠番3日は埋め戻さない。** 埋め戻すと「結果を見たあとの予測」が
  混入し、検証の意味が失われる。`predictions_gaps.csv` の記録も同様に欠番のまま残す。
- **`kdata/` は保全（バックアップ）目的で読み取り専用。** `docs/` 配下ではないので Pages 非配信。
  `entries` の本体は `entriesFull.csv`（全13列）。`entriesLite2.csv` は5列を間引いた**派生**であり
  完全版ではない。「All＝完全版」と誤認して月別や `entriesFull.csv` を捨てないこと。
- **`data/kfiles/` の lzh はコミットしない。** クラウド実行環境には存在しないので、
  K依存の集計（`buildMotorUsage.py` など）は**ローカルでしか完走しない**。
  取得できない日は**欠けたまま**にする（補完・推測はしない）。

---

## ローカル運用（Windows タスクスケジューラ）
mbrace 依存と Claude CLI 依存の処理はローカル PC のタスクで回している。**現在3本。**

| タスク名 | 実行 | トリガ | 内容 |
|---|---|---|---|
| `boatrace-writeKansenkiLocal` | `scripts/writeKansenkiLocal.ps1` | 毎日 **JST 05:30** | 認証済み `claude.exe` で観戦記を執筆 → lint → PASS分のみ commit&push |
| `boatrace-dailyMotorUsage` | `scripts/dailyMotorUsage.ps1` | 毎日 **JST 06:00** | fetchKfiles（直近7日・mbrace）→ buildMotorUsage → backfillMotorPartsMotorNo → `motorUsage.json`/`motorParts.json` のみ commit&push |
| `boatrace-updateKimarite` | `scripts/updateKimariteLocal.ps1` | **毎月2・16日 JST 06:30** | scrapeKimarite（183日・mbrace）→ **検証4項目** → 通ったものだけ `racerKimarite.csv` へ配置 → commit&push（→(3)） |

- 登録は `registerDailyMotorUsage.ps1` / `registerWriteKansenkiLocal.ps1` /
  `registerUpdateKimariteLocal.ps1`（いずれも再実行で上書き更新）。
  **Interactive ログオン＋WakeToRun** で登録している。push に使う Git Credential Manager の資格情報が
  DPAPI 保護のため、「ログオンしていなくても実行」にすると**復号できず push が失敗する**。
- 実行時刻は 05:30 → 06:00 → 06:30 とずらしてある。
  `updateKimariteLocal.ps1` は183日ぶんを mbrace から取り直すため**30分前後**かかる
  （2026-07-31 実測 31分33秒）。`dailyMotorUsage` のKファイル取得と競合させない。
- 共通の破壊防止ガード `checkRepoGuard.ps1` を pull 前（remote検証）と pull 後（worktree健全性）に呼ぶ。
- `dailyMotorUsage.ps1` は `updated` だけの差分を捨てて空コミットを作らない。
- **失敗しても通知は飛ばない →(7)。** `scripts/logs/*.log`（gitignore済・30日剪定）を見る。
- Python は絶対パス固定（`...\pythoncore-3.14-64\python.exe`）。
  タスクスケジューラの PATH は対話シェルと異なり、`py.exe` のアプリ実行エイリアスは非対話で不安定。

### ⚠️ 3本とも「作業ツリーが汚れていれば何もせず退避」する
- `main` 以外に居る、または追跡ファイルに未コミット変更があると、
  3本とも**何もせずに正常終了（exit 0）** する。ユーザーの作業を巻き込まないための設計で、これは正しい。
- ただし**退避したこと自体は通知されない。** ログに理由が1行残るだけで、
  終了コードは 0 なのでタスクスケジューラ上も「成功」に見える。
- つまり**手作業の途中で朝を迎えると、その日は静かにスキップされる。**
  日次2本なら翌日取り返せるが、`updateKimarite` は月2回なので**次は2週間後**になる。
- 夜に作業を中断するときは、コミットして `main` をきれいにしておくこと。
  スキップされたかどうかは `scripts/logs/*.log` の最終行（`[RESULT]` 等）で確認できる。

### `writeKansenkiLocal.ps1` は自動執筆の雛形
- 認証済みの `claude.exe` を**非対話**（`-p` / `--allowedTools` 限定）で走らせて観戦記を書かせ、
  `lintKansenki.py` を通した **PASS 分だけをコミットする**。
  FAIL の記事は**削除して持ち越し**（`:169-184`）。全FAILなら公開なしで正常終了。
- つまり **「一発で完結する指示 ＋ 品質ゲート ＋ 不合格は破棄」** という
  自動執筆の型がここに実装されている。
- **同種の自動化を増やすときはこのスクリプトを雛形にすること。** 特に次の3点を踏襲する:
  1. 生成物は必ず機械チェック（lint）を通し、**PASS したものだけを公開経路に乗せる**
  2. 不合格は握りつぶさず**破棄して持ち越す**（中途半端な成果物を残さない）
  3. 既存の成果物（articles / predictions）は**上書きしない**
- 規範は `kansenkiRules.md` / `runbook.md`。source に無い事実・買い目・確率は出さない。

### タスク登録の注意（`register*.ps1` を書くとき）
- **「毎月N日」のトリガは `New-ScheduledTaskTrigger -Monthly` では登録できない**
  （そもそも `-Monthly` パラメータが無い）。**タスクXML方式**（`Register-ScheduledTask -Xml`）で
  `<CalendarTrigger><ScheduleByMonth><DaysOfMonth><Day>2</Day>…` と書く。
  実例: `registerUpdateKimariteLocal.ps1`。
  - CIM の `MSFT_TaskMonthlyTrigger` を `New-CimInstance -ClientOnly` で組む方法は
    `Register-ScheduledTask` が `0x80070057`（パラメーターが正しくありません）で拒否する。
    加えて `DaysOfMonth` が **UInt16** のため 16日までしか表現できない。使わないこと。
  - プロパティ名は `MonthOfYear`（**単数形**）。`MonthsOfYear` は存在しない。
- **XML に埋める文字列は必ず `[System.Security.SecurityElement]::Escape()` を通す。**
  とくに説明文に `&` を含めると（例: `commit&push`）
  `Register-ScheduledTask` が `The task XML is malformed` で拒否する。
  `-Description` パラメータ経由なら不要だが、XML方式では必須。
- 毎日1回でよいなら `New-ScheduledTaskTrigger -Daily -At '06:00'` が使える
  （`registerDailyMotorUsage.ps1` / `registerWriteKansenkiLocal.ps1`）。XML方式は月次のときだけ。
- `.ps1` は **UTF-8 BOM 付き**で保存する。PS 5.1 は BOM 無し UTF-8 の日本語を
  ANSI と誤読してコメント・文字列が壊れる。

---

## 開発メモ
- 24場コード（jcd）は各スクリプトにハードコード（01桐生 … 24大村）。
- タイムゾーンは JST（UTC+9）。Actions は UTC 実行なので JST 換算して対象日を決める
  （夜の実行は翌日分を予習対象にするロジックあり）。
- 級別は A1/A2/B1/B2。期替わり（前期/後期）でfanファイルから更新する（→(4)）。
- スクレイプ系は公式サーバ負荷軽減のため `SLEEP`（既定1.0秒）を挟む。
- 出力ファイルは基本 UTF-8。`build_highlights.py` の入力CSVは BOM 付き(`utf-8-sig`)を読む。
- `predictions/` は「結果を見る前の値」。検証で読むだけにし、決して上書きしない（鉄則 →(5)）。
- mbrace 依存の収集はローカルから実行してコミットする（→(1)）。
- **`motor2SetsuAvg` の名前に注意。** コード上「今節平均」と呼ばれているが
  （`buildKansenkiSource.py:771,791`）、実体は `motor_avg()`（`:371-374`）＝
  **その日・その場に出走する全艇のモーター2連率の平均**。**節をまたぐ集計はしていない。**
  「当日・当場の出走全艇の平均」と理解すること。
- `motor2` は出走表CSVの「モーター2連率」をそのまま転記した値
  （出所は公式 racelist ページ。`scrape_racers.py:297`）。
- **boatrace.jp のPC版（racelist / beforeinfo / pcexpect / raceindex）に選手コメント欄は存在しない。**
  2026-07-31 に4ページの生HTMLを取得して grep で確認済み（「コメント」0件）。再調査不要。
  整備の「事実」（部品交換・プロペラ新・チルト・調整重量）は beforeinfo から取れるが、本人の言葉は無い。

## 未確認事項（判明していないことを、判明していないまま記録する）
推測で埋めないこと。確認が取れたらここから移す。

### `results/*.json` の着コード 7〜16 の意味が不明
- 値は BoatraceOpenAPI の `racer_place_number` を `buildResults.py:102` が**そのまま転記**している。
- 全382日の実測出現数: `7:269 / 8:292 / 9:1595 / 10:473 / 11:35 / 12:102 / 13:5 / 14:1152 / 15:36 / 16:607`
- **リポジトリ内に対応表は存在しない。** 唯一の手掛かりは `buildE30Stats.py:156` のコメント
  「F(負値)は平均STから除外（別途フライングは着コードで判別可）」。
- 1〜6 以外を「着順」として扱う処理を足す前に、必ず意味を確認すること。
  現状 `buildE30Stats.py` は `place in (1,2)` の判定しかしておらず、7以上は自然に除外されている。

### `motor2` の集計期間が不明
- `motor2` は公式 racelist 掲載のモーター2連率をそのまま使っているが、
  **公式がどの期間で集計しているか（初卸以降の累計か、別の窓か）はリポジトリ内に記述がない。**
- 「節内集計ではない」ことだけは確か（節をまたぐ集計を自前でしていないため）。
- なお `motor2SetsuAvg` は自前計算で、**当日・当場の出走全艇の平均**（→開発メモ）。

---

## 更新履歴の記録ルール

読者に見える変更（ページの表示・機能・データが変わるもの）を実装したPRには、
PR本文に次の1行を必ず入れる。

  [updates] ページ名 / 何をしたか（読者向けの平易な一文）

- この行があると .github/workflows/updateUpdates.yml が
  docs/data/updates.json に自動で記録し、/updates/ に表示される
- リポジトリ内部だけの変更（リファクタ・CI調整・リポジトリ名変更・
  ドキュメント追加など、読者に見えないもの）には入れない
- ページ名に「/」は使えない（本文との区切りに使うため）
- 1つのPRで複数の変更があれば、行を複数書いてよい
