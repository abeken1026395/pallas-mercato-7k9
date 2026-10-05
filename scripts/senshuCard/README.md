# 選手カードのデータを作るスクリプト

選手カード（本番 docs/players/card.html）が読む docs/players/card/ の common.json・index.json・p/・h2h/ を作る。実験場 senshuCardE.html の元データ（card2D.json・ayumi.json）も全体版として出せる。
決まり（技・段・技名・積み上げ・表示の原則）は Project の `claude/senshuCardLaunch.md` が正。

## 使い方
```
# 1. 優勝戦の判定に使う公式番組を取る（履歴の最終日より後の日だけでよい。すでにある日は取らない）
python3 scripts/senshuCard/fetchPrograms.py 20261003 最終日 番組フォルダ
# 2. 一式を作る（検査を通らなければ書き出さない）
python3 scripts/senshuCard/build.py 最終日 番組フォルダ docs/players/card [照合用の全体版フォルダ]
```
必要なもの：Python 3、numpy、scipy

## ファイル
| ファイル | 役目 |
|---|---|
| officialRaces.py | 公式の出走の数え方にそろえた艇ごとの表。results/ に、責任の有無（S0/S1・L0/L1・K0/K1）と results に無いレースを Kファイルから足す |
| buildCard.py | 出走・着・ST・コース別・決まり手・計器（6項目）・総合・優勝（yc・yu・yo）・名前（np・kp） |
| finals.py | 優勝戦の一覧（2017-01-01〜）。副題の規則で拾う。履歴 data/senshuCard/finalsHistory.json より後の日だけ番組から拾う |
| waza.py | 技（tg）10系統と段。経験ベイズの事前分布（tagPrior）。コースの持ち味（co1〜co6・course()） |
| facts.py | 積み上げた事実（ayumi.json） |
| h2h.py | 直接対決 |
| check.py | 書き出す前の検査（ページと同じ決まりで4つを組み立て、何もない選手0人・技名がすべて誰かに出る・技名の重複0・数の整合） |
| fetchPrograms.py | BoatraceOpenAPI の番組（と2025-07-14以前の結果）を日ごとに小さくして保存 |

## データ
| ファイル | 中身 |
|---|---|
| data/senshuCard/kExtra.csv | kdata に無い日の Kファイルから、着が普通でない行と results に無いレースの全行（2025-07-15〜2025-07-21・2026-07-22〜2026-10-02。PCで取得、Drive codeShikyu\kfileParse20261003\kSmall.csv と同じ） |
| data/senshuCard/finalsHistory.json | 優勝戦の一覧と、番組が空の場日の数（日ごと）。2017-01-01〜to |

## 照合の結果（2026-10-04・最終日 2026-10-02）
- 集計（出走・着・ST・コース別・決まり手・計器・総合・名前・優勝・優出・直接対決）は、PR #677 で作った card2.json・h2h と全件一致
- 技は card2D.json と、好スタート（ゼロ台の牙）以外の12系統で全件一致。好スタートは、results に無く Kファイルにだけあるレース（不成立など）の ST を数えるようにしたため少し変わる
- 積み上げた事実は8人で本番ST最速が変わる（同じ理由）

## 注意
- Kファイル（mbrace）は GitHub Actions からも、このクラウドからも取れない（遮断）。kdata・kExtra に無い日は、着7〜16の責任の有無が分からない
- 新しい日の Kファイルは PC で取り、kExtra.csv に足す必要がある（毎週の自動更新を作るときに決める）
