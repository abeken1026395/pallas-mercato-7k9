# REFERENCE.md — boatrace プロジェクト リファレンス

行動規範は `CLAUDE.md`。このファイルは**辞書**であり、必要になったときだけ該当節を読む。
全体を読み通す必要はない。

**目次**
- [目的とプロジェクトの性格](#目的とプロジェクトの性格)
- [既知の重大問題・運用上の注意（作業前に該当節を読む）](#既知の重大問題運用上の注意作業前に該当節を読む)
- [ディレクトリ構成](#ディレクトリ構成)
- [公開ページ一覧](#公開ページ一覧docs-github-pages全41ページ)
- [スクリプト](#スクリプトscriptspython-126本ほか)
- [GitHub Actions ワークフロー](#github-actions-ワークフローgithubworkflows全51本)
- [データの流れ](#データの流れ)
- [データの範囲](#データの範囲2026-07-31-時点の実測)
- [ローカル運用](#ローカル運用windows-タスクスケジューラ)
- [開発メモ](#開発メモ)
- [未確認事項](#未確認事項判明していないことを判明していないまま記録する)

---

## 目的とプロジェクトの性格
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

## 既知の重大問題・運用上の注意（作業前に該当節を読む）

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
- 徳山・桐生払戻の停止は Api 版への移行で解消したが、その移行時に
  `scrape{場名}PayoutsApi.py` 24本中22本の 93行目 `datetime.date.today()` が
  場名の一括置換で `datetime.date.<場名>y()` に壊れていた（`toda`→`kiryu` で
  `today`→`kiryuy`）。`END` が空になる `schedule` 起動でこの行を通るため、
  **22場は毎晩 AttributeError で起動直後に落ち続け、最終収録日が
  20260629〜20260716 で止まっていた**（2026-08-02 に修正・埋め戻し済み）。
  正常だったのは戸田・唐津の2本のみ。`continue-on-error: true` により
  ワークフローは緑のままで、1ヶ月以上気づけなかった。
- **mbrace 版 `scrape{場名}Payouts.py` にも同じ置換ミスが残っている（2026-08-02 実測: 24本中20本）。**
  こちらは変数名まで巻き込まれている（179行目 `amagasakiy = datetime.date.amagasakiy()` →
  180行目 `yesterday = amagasakiy - ...`）。無事なのは唐津・桐生・戸田・徳山の4本
  （桐生143行・徳山129行と行番号も揃っておらず、mbrace 版は Api 版と違って同型ではない）。
  **ローカル専用の旧経路で、ワークフローからの参照は0件のため未修正のまま残してある。**
  使うときは必ず先に直すこと。直さずに走らせると `END` 相当が空の経路で即 AttributeError になる。

#### 発火経路は GitHub schedule のみ（外部cronは未導入）
- **外部サービス cron-job.org への登録は一度も行っていない。今後も導入しない**
  （2026-08-04 けん裁定）。発火はすべて GitHub の `schedule`。
  `heartbeat.yml` が JST 時刻帯を見て `nightlyPipeline.yml` を `workflow_dispatch` で
  内部起動する。**内部起動の対象は nightlyPipeline の1本のみ**
  （`writeKansenki.yml` の内部起動は 2026-08-03 に停止。観戦記はPCローカルで自走）。
- `schedule` の発火率は実測で **heartbeat 42.3% / nightlyPipeline 15〜26%**
  （2026-07-14〜08-03）。不発火は多いが多重発火×冪等で吸収できており、
  nightlyPipeline は日 6〜11 回動いている（実害なし）。
- **発火率がさらに落ちれば静かに止まる点は変わらない。現状これを検知する仕組みはない。**

#### ⚠️ 単一障害点は3つ。いずれも停止しても通知が飛ばない
| 障害点 | 止まると | 検知手段 |
|---|---|---|
| mbrace 遮断 | Kファイル収集・決まり手更新が止まる | なし（成果物が古いままになるだけ） |
| BoatraceOpenAPI ミラー | 結果・払戻の収集が全滅する（`buildResults.py` と 24場 Api 版がすべて依存） | なし |
| GitHub `schedule` の不発火 | heartbeat が撃たれず nightlyPipeline の内部起動が減る（実測発火率 42.3%） | なし |

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

### (8) ⚠️ 監視が「緑」でも壊れている（異常が見えないことがこのリポジトリの主要な故障モード）
(1) の単一障害点3つは「止まっても通知が飛ばない」問題だが、それとは別に
**Actions の結果表示そのものが異常を隠す**経路が4つある。いずれも 2026-08-02 に判明。
**緑（success）や無言を「正常」と解釈しないこと。**

#### a. `writeKansenki.yml` は書く対象が0でも success
- `kansenki_pubplan.py` の `toWrite` が空だと `RUN=0` になり（`:78`）、
  執筆ステップが `if: steps.plan.outputs.run == '1'` でスキップされる（`:93`）。
  ジョブは**そのまま success で終わる**。
- したがって「全場執筆済み」も「そもそも素材が無くて書けない」も**同じ緑**になる。
  緑を見ても、記事が出たことの証明にはならない。
- 認証は `ANTHROPIC_API_KEY`（Anthropic Console の APIキー・`:15`,`:95`）。
  **クラウド側のこの経路は実質使用しておらず、正規経路はローカルタスク
  `boatrace-writeKansenkiLocal`**（認証済み `claude.exe`／→「ローカル運用」節）。
  クラウド側が動いていないこと自体は、緑のままなので画面からは分からない。
- 実測（2026-08-02 時点）: **run #248〜#257 の10回すべて failure。**
  失敗箇所はいずれも `write articles (headless claude)` ステップで、
  `ANTHROPIC_API_KEY` が空のまま `rc=1`（`total_cost_usd=0`）。
  ただし**APIキーを設定すれば動く可能性は残る**ため、
  「使用不可」ではなく **「使用していない」** が正確な表現。
- なお a. の「toWrite:0 なら success」は、この失敗とは別経路。
  キーが無くても、書く対象が0の日は執筆ステップ自体に入らないので緑で終わる。

#### b. `update{場名}Payouts.yml` はスクリプトがクラッシュしても success
- スクレイプ手順に `continue-on-error: true` が付いている。**24本すべてに付いている**
  （2026-08-02 実測: `update*Payouts.yml` 24本 / `continue-on-error` を含むもの 24本）。
- 「1場こけても他場・後続を止めない」ための設計で、意図自体は正しい。
  ただし**結果として、収集が全滅していてもワークフロー一覧は緑で埋まる**。
- 払戻が更新されているかは Actions の色ではなく、
  `docs/payouts/{場名}Payouts.csv` の最終 `hd` を見て判断すること。
- 2026-08-02、この「緑で埋まる」状態で22場が1ヶ月以上停止していたことが実際に発覚した。
  運用（人が最終 `hd` を見る）での回避には限界がある。
  外側から鮮度を見る `dataFreshnessAlarm.yml` を導入した（→ ワークフロー節）。
  `continue-on-error` の除去自体は、監視が動いていることを確認してから1場ずつ試す。

#### c. `kansenkiCoverage.yml` は18日間ずっと赤だった（常時赤いゲートは何も検知しない）
- 実測（2026-08-02 時点の run 履歴）:
  **2026-07-15T15:28Z の success を最後に、27 run 連続で failure。**
  2026-08-02T08:18Z の success で解消。JST では 2026-07-16 早朝から 2026-08-02 夕方まで。
- 原因は**たった1件**。解消直前の run（`30739329733`）のログ:
  ```
  FAIL 網羅 20260716
     [記事欠] 20260716-24(大村) の記事が無い
  網羅結果: 検査22日 / FAIL 1 日
  ```
  他の21日はすべて PASS または SKIP。**過去日の欠場1件が、以後の全 push を赤にし続けた。**
- 問題は赤かったこと自体ではなく、**赤が常態化すると新しい異常を検知できなくなる**こと。
  ゲートは「直った状態を保つ」前提の仕組みで、放置した赤は警報として死ぬ。
- 過去日の FAIL が居座る形の検査を足すときは、**古い FAIL を持ち越さない設計**にすること
  （検査対象日を絞る・既知の欠番は台帳で除外する等）。

#### d. `lintKansenki.py --coverage` は「全欠」を見逃す
- `check_coverage()` は**その日の記事が1本も無ければ SKIP**（`:244-245`, `:262`）。
  コメントの通り「観戦記非運用日」とみなす設計で、`0本は執筆自体の未着手で別問題` と書かれている。
- つまり検知できるのは **「一部書いたのに一部欠けている」乖離だけ**。
  **source があるのに記事が全欠の日は、SKIP されて緑になる。**
- 実ログでも `SKIP 網羅 20260722（当日記事0本＝観戦記非運用日）` のように出る。
  この SKIP が本当の非運用日なのか、執筆が丸ごと落ちた日なのかは**このログからは区別できない**。
- 全欠の検知は `kansenkiMissingAlarm.yml`（JST 07:37・当日分のみ Issue 起票）が担当。
  ただし**当日分だけ**なので、過去日の全欠は誰も検知しない。

### (9) 観戦記の素材・検査に残る既知の穴（2026-08-02 記録）

いずれも**エラーにならず静かに間違う**類。lint も通ってしまうので、執筆時に人／モデルが
気づかなければそのまま公開される。

#### (8-a) `assign_styles.py` の killerHints が主役以外の値を返す 〔**修正済み 2026-08-02**〕
- `killer_hints()` が `focusRacers[0]` 固定で `machine` / `protagonistWins` を作っていたため、
  **主役が `focusRacers[0]` と異なる場で他人の機力・勝ち星を主役の材料として返していた。**
- 発生条件は2つ。代替主役だけの問題ではなかった:
  1. `protagonistForcedAlternate=true`（3日連続回避の差し替え）
  2. `_protag_pool()` がA級を前に寄せるため、`localRacers` のA級が筆頭になる通常ケース
     （例 20260716 宮島: 主役 東潤樹4574 に対し focus[0] は北川幸典3054）
- 数値としては素材内に実在するため `lintKansenki.py` では検出できない。
- 修正: 主役の toban で `focusRacers` → `todayProgram` の順に本人を引く。
  どちらにも無ければ `None` / `[]` を返す（他人の値で埋めない）。
  出走表に機番は無いので、`todayProgram` 経由のときは `machine.no` が `null` になる。
- 影響範囲（全25日の実測）: killerHints に差分が出たのは **115場**。
  `styleType` と `protagonist` は全日・全場で不変。
- **代替主役は `focusRacers` に載らないため `finishTrail` / `stSetsu` / `kimariteType` が無い。**
  つまり人物型の「節内の起伏を柱に」が成立しない場が出る。その場合は当地成績・機力・
  当日の枠と企画名など実在する事実で組み、`killerElement` にその旨を明記すること。
- **既公開の記事には他人の数字が載っている可能性がある**（`wins` が N→0 に変わった場が多数）。
  ただし「公開後の記事は不変」が鉄則なので**遡って直さない**。

#### (8-b) `kimariteType` の winCount と決まり手内訳の合計が一致しない
- `source/*.json` の `focusRacers[].kimariteType` で、`winCount` と
  `nige + sashi + makuri + makurisashi` が合わない場がある。
  - 20260801 桐生: `winCount` 28 に対し内訳合計 24（逃げ14・差し8・まくり0・まくり差し2）
  - 20260801 児島: `winCount` 32 に対し内訳合計 30（逃げ18・差し2・まくり6・まくり差し4）
- 原因は未調査（`racerKimarite.csv` 側か集計側か不明）。
- **当面の回避**: 「N走でM勝、うち逃げ…」と**内訳を部分集合として**書く。
  「M勝の内訳は…」と書くと合計が合わず、読者に矛盾として見える。

#### (8-c) lint が `prevArticle` 内の数値も許容するため、古い値を書いても PASS する
- `lintKansenki.py` の `collect_source_numbers()` は venue を再帰走査するので、
  `prevArticle.body`（前日記事の本文）に含まれる数値も許容集合に入る。
- 前日記事の数値は**前日時点の値**で、当日素材とは食い違う。実測例:
  - 年間実績の `n`（三国 2173→2185 / 福岡 2387→2399 / 若松 2187→2199）
  - 今節平均モーター2連率（多摩川 33.0→32.2 / 三国 31.0→32.1 / 福岡 30.6→31.2）
  - 決まり手の集計窓と母数（福岡 127走21勝 → 234走38勝）
- したがって**古い数値を本文に書いても lint は PASS する**。
  執筆時は必ず当日素材（`reference` / `focusRacers` / `todayProgram`）側の値を採る。
- 恒久対策は未着手（`prevArticle` を許容集合から除外する等）。

### (10) 規範が生まれた事例（`CLAUDE.md` の各条がなぜあるか）
`CLAUDE.md` には規範の1行だけを置き、**その根拠になった事例はここに集約する。**
規範を1条足すたびに、この節へ事例を1つ追加すること。
事例を CLAUDE.md 側に書くと、読むたびのコストが積み上がって行動規範が薄まる。
**なお CLAUDE.md の100行は目標であって上限ではない。削るべきは事例であって条項ではない。**
規範を足すときに無理な圧縮をしないこと。この節への移設で吸収できないなら、超えたままでよい
（読めなくなるほうが害が大きい）。

#### (10-a) 観戦記の「main 直行」は自動タスクの挙動であって Code の権限ではない（2026-08-02）
- 「観戦記は main 直行で PR 不要」という認識があったが、これは
  ローカルタスク `writeKansenkiLocal.ps1` が lint PASS 分だけを main へ
  commit&push する挙動を指したもので、**自動タスクの話**だった。
- Code が手で書く場合の権限は当時どこにも書かれていなかった。
  一方 `docs/data/kansenki/runbook.md` の「禁止」には書き手向けに
  **「PR作成・マージ・push・ネットワークアクセス（この工程はローカル執筆と
  lint のみ。公開は人が行う）」** と明記されている。
- 結論: 書き手には runbook.md が優先される。Code の push 先は作業ブランチ。
  main への反映は従来どおり承認を要する。→ `CLAUDE.md`「承認なしでやっていいこと」

#### (10-b) 古い作業ツリーを根拠に「未着手」と誤判定し、13本を上書きしかけた（2026-08-02）
- 20260801 の13場執筆を指示された際、作業ツリーが `PR #171` マージ前の
  古い main を指したままで `articles/20260801-*.json` を数え、
  **「記事0本＝未着手」と誤判定した。**
- 実際には別セッション（`claude/kansenki-0802-12venues-0wsyl9`）が先に完了させており、
  最新 main には13本すべて存在。実測は **lint 13/13 PASS・coverage も PASS**、
  `kansenki_pubplan.py` は `toWrite: []` / `done: 13場`、
  `assign_styles.py` は13場すべて `locked=true` を返していた。
- そのまま書き始めていれば、runbook.md の「**公開後の記事は不変**」に反して
  13本を上書きしていた。`origin/main` へ fetch した時点で誤りに気づいた。
- ここから2つの規範が出ている。
  1. **作業開始前に `origin/main` へ fetch して現物を確認する**
     （`locked=true` / `done` の確認を怠らない）→ `CLAUDE.md`「作業の型」
  2. **報告ヘッダ**（ブランチ / HEAD / origin/main との差 / 作業内容）を必須にする。
     どのセッションがどの時点のツリーを見ているかを、けんが一目で判別するため。
     **ヘッダの値は報告を書く直前に `git fetch origin` してから取る。**
     fetch していない「差」は、古いツリーを見ていることに気づけないため意味がない。
     この事例はまさにその状態で発生した。→ `CLAUDE.md`「報告の作法」

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
| `docs/motor/app.js` | `buildMotorApp.mjs`（`node`） | **`scripts/motor/app.jsx`** |
| `docs/data/motorKarte.json` | `buildMotorKarte.py`（updateBeforeinfo.yml） | **`docs/data/motorParts.json`**（読むだけ） |
| `docs/racers/index.html` | `scrape_racers.py` | **`scripts/template_racers.html`** |
| `docs/players/app.js` | `buildPlayersApp.mjs`（`node`） | **`scripts/players/app.jsx`** |
| `docs/probe/beforeinfoProbe.html` | `buildBeforeinfoProbe.py` | 同スクリプト |

- HTMLを書き出すスクリプトは**この3本（+ app.js 2本）だけ**。
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

## GitHub Actions ワークフロー（`.github/workflows/`、全52本）
生成物は `github-actions[bot]` / `github-actions` がコミット＆プッシュ。cron は **UTC 指定**（JST=UTC+9）。
各ジョブは専用 `concurrency` グループでプッシュ競合を回避。ほぼ全てに `workflow_dispatch` あり。

**発火方針:** 外部cron（cron-job.org）は**未導入**（2026-08-04 けん裁定）。発火は GitHub の
`schedule` のみで、`heartbeat.yml` が JST 時刻帯を見て `nightlyPipeline` を
`workflow_dispatch` で内部起動する（対象は1本のみ。`writeKansenki` の内部起動は
2026-08-03 に停止）。`schedule` の発火率は実測 heartbeat 42.3% / nightlyPipeline 15〜26%
（2026-07-14〜08-03）。**多重発火は冪等設計で吸収**する前提（→(1) 単一障害点）。

### 基幹
| ファイル | cron (UTC) | 実行内容 | 失敗時の挙動 |
|---|---|---|---|
| `heartbeat.yml` | `0 8-23 * * *` | 時刻帯で nightlyPipeline を workflow_dispatch | 起動失敗は `::error::` で run を落とす（次の発火で再試行） |
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

### 監視（成果物を外から見る）
| ファイル | cron (UTC) | 役割 |
|---|---|---|
| `dataFreshnessAlarm.yml` | `40 22` | 払戻24場・`results/`・決まり手CSV の鮮度を横断チェック。異常なら **Issue 起票**（ラベル `data-stale`・冪等） |

`scripts/checkDataFreshness.py` が本体。**払戻はミラーと突合する（日数しきい値ではない）。**
直近 `WINDOW` 日（既定10日）の日別JSONを取得し、**「ミラーに3連単の払戻があるのに
CSVに無い日」**を場ごとに検出する。開催の有無を問わないので非開催による誤検知が起きない。

- 日数しきい値を採らない理由: 2026-08-02 実測で開催間隔は最大105日（尼崎）・95日（児島）。
  誤検知しない N にすると1ヶ月の停止を検出できず、停止を拾える N にすると非開催の場を毎回誤検知する。
  さらに今回の停止は22/24場で、戸田・唐津は更新され続けていたため
  「全場の最新 `hd`」を見る大域チェックでも素通りする。→ 場ごとの突合しかない。
- `results/`（毎晩更新）と決まり手CSV（毎月2・16日更新）は単一対象なので日数しきい値。
  既定は `TH_RESULTS=3` / `TH_KIMARITE=25`。
- **ミラーに1日でも到達できなければ、それ自体を異常として Issue に載せる。**
  「繋がらなかった」を沈黙で流さない。窓の全日に到達できなかった場合は
  「場ごとの欠落判定は成立していない」と本文に明示する。
- 監視スクリプトが結果を出さずに落ちた場合はワークフロー自体を赤にする
  （この監視まで「緑で壊れる」と意味がないため）。
- 残る限界: **このワークフロー自体が発火しなければ無音になる。** GitHub の `schedule` は
  夜間の不発火が多い（実績5%）ので、外から気づく手段としては完全ではない。

### その他
| ファイル | cron (UTC) | 備考 |
|---|---|---|
| `updateKimarite.yml` | dispatch のみ | **mbrace依存のため schedule 削除済み。正規経路はローカルタスク →(3)** |
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
公式(mbrace LZH※) ─ scrapeKimarite.py ─→ docs/players/racerKimarite.csv（月2回・ローカルタスク→(3)）
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

### 3) 場別 払戻分析（24場）
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
| `docs/payouts/*Payouts.csv` | 〜20260801（全24場） | 2026-08-02 に today() 破損を修正し22場を埋め戻し。書き込み前ガード導入済み |
| `docs/players/racerKimarite.csv` | 2026-07-30 まで（ローカルタスクへ移設して復旧） | →(3) |

- **この表の書き方の原則: 複数対象をまとめた行を、1つの代表値で書かない。**
  ばらつくなら「最も古いもの」を書くか、ばらついている旨を書く。
  2026-08-02 の見逃しはこの構造そのものだった。`docs/payouts/*Payouts.csv` を
  「〜20260716」の1行で書いていたが、20260716 は桐生・徳山だけの値で、
  他22場は 20260629〜20260710 とさらに古かった。**表が「揃っている」ように
  見えるせいで、22場が止まっていることに気づけなかった。**
  代表値は、最も健全なものではなく最も悪いものを採ること。
- **`verify_log.csv` の欠番3日は埋め戻さない。** 埋め戻すと「結果を見たあとの予測」が
  混入し、検証の意味が失われる。`predictions_gaps.csv` の記録も同様に欠番のまま残す。
- **`kdata/` は保全（バックアップ）目的で読み取り専用。** `docs/` 配下ではないので Pages 非配信。
  `entries` の本体は `entriesFull.csv`（全13列）。`entriesLite2.csv` は5列を間引いた**派生**であり
  完全版ではない。「All＝完全版」と誤認して月別や `entriesFull.csv` を捨てないこと。
- **`data/kfiles/` の lzh はコミットしない。** クラウド実行環境には存在しないので、
  K依存の集計（`buildMotorUsage.py` など）は**ローカルでしか完走しない**。
  取得できない日は**欠けたまま**にする（補完・推測はしない）。

### `results/*.json` の「着」は着順ではなくコードを含む（確定）

BoatraceOpenAPI の `racer_place_number` を `buildResults.py:102` がそのまま転記している。
**1〜6 は着順だが、7 以上は着順ではない。**

| コード | 意味 | コード | 意味 |
|---|---|---|---|
| 7 | 妨害 | 12 | 不完走 |
| 8 | エンスト | 13 | 失格 |
| 9 | 転覆 | 14 | F（フライング） |
| 10 | 落水 | 15 | L（出遅れ） |
| 11 | 沈没 | 16 | 欠場 |
| | | 99 | `_`（値なし） |

- 全382日の実測出現数（7〜16のみ計数）:
  `7:269 / 8:292 / 9:1595 / 10:473 / 11:35 / 12:102 / 13:5 / 14:1152 / 15:36 / 16:607`
- **平均着を出すときは 7〜15 を 6 に丸め、16 は分母から除く。**
  生の `int()` だと転覆が「9着」として平均に入る。実測（3日・2,732艇）で平均着が最大 0.15 ずれた。
- **1着率・3着内率・①着外率は影響しない。** `==1` / `<=3` / `>=4` の判定のため。
- `buildE30Stats.py` は `place in (1,2)` の判定しかしておらず、7以上は自然に除外されている。

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

---

## 未確認事項（判明していないことを、判明していないまま記録する）
推測で埋めないこと。確認が取れたらここから移す。

### `motor2` の集計期間が不明
- `motor2` は公式 racelist 掲載のモーター2連率をそのまま使っているが、
  **公式がどの期間で集計しているか（初卸以降の累計か、別の窓か）はリポジトリ内に記述がない。**
- 「節内集計ではない」ことだけは確か（節をまたぐ集計を自前でしていないため）。
- なお `motor2SetsuAvg` は自前計算で、**当日・当場の出走全艇の平均**（→開発メモ）。
