# writeKansenkiLocal.ps1
# 観戦記の自走をローカルPCで実行する（認証済み claude CLI＝Maxプラン枠・API課金なし）。
# GitHub Actions では OAuth/Secret 問題で自走が安定しなかったため、ローカルのタスクスケジューラで毎朝実行する。
# 登録: scripts/registerWriteKansenkiLocal.ps1（毎日 JST 5:30・Interactive＋WakeToRun）。
#
# 処理順（writeKansenki.yml のローカル移植）:
#   a. main へ同期（checkout main → pull）。作業ツリーが汚れていれば何もせず退避（ユーザー作業の巻き込み回避）。
#   b. kansenki_pubplan.py で掲載日の toWrite を得て、三状態で判定する（writeKansenki.yml の plan と同じ分類）。
#      正常な0（全場執筆済・前日非開催の構造上の除外だけ）→ 正常終了（exit 0）。
#      source が無い・掲載日が取れない・場数0・入力が揃わず書けない場が残る → 未検証（exit 1）。
#      実例: 2026-08-28・08-29 は 05:30 時点で source が無く toWrite=0 のまま「正常終了」していた。
#   c. 二重執筆防止: articles/<pubdate>-*.json が既に在れば skip（既存記事は不変）。
#   d. assign_styles.py（位置引数）でスタイル決定。
#   e. claude -p ... で未執筆場のみ執筆（runbook 全文＋kansenkiRules をシステムプロンプト）。claude は push しない。
#   f. lint（各記事＋--coverage）。FAIL の記事は削除して持ち越し。
#   g. lint PASS の記事だけ add → commit → pull --rebase → push。
#   h. 全工程を scripts/logs/writeKansenki_<pubdate>.log に追記。
#
# 不変条件: 既存 articles/predictions は上書きしない。lint FAIL は書かない（持ち越し）。
#           source に無い事実・買い目・確率は出さない（規範は kansenkiRules.md / runbook.md）。

$ErrorActionPreference = 'Stop'

# KANSENKI_LOCAL_REPO / KANSENKI_LOCAL_CLAUDE / KANSENKI_LOCAL_PUBDATE は検証用の上書き（本番のタスクでは未設定）。
$Repo    = if ($env:KANSENKI_LOCAL_REPO) { $env:KANSENKI_LOCAL_REPO } else { 'C:\Users\USER\boatrace' }
# 絶対パス固定: タスクスケジューラの PATH は対話シェルと異なり、py.exe/npm系エイリアスは非対話で不安定。
$Py      = 'C:\Users\USER\AppData\Local\Python\pythoncore-3.14-64\python.exe'
$Git     = 'C:\Program Files\Git\cmd\git.exe'
$Claude  = if ($env:KANSENKI_LOCAL_CLAUDE) { $env:KANSENKI_LOCAL_CLAUDE } else { 'C:\Users\USER\.local\bin\claude.exe' }
$PyDir   = Split-Path $Py   # claude 内部の Bash が叩く `python scripts/...` を実体に解決させるため PATH 先頭へ
$Ps      = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"  # 破壊防止ガード呼び出し用
$Guard   = Join-Path $Repo 'scripts\checkRepoGuard.ps1'                      # ガード本体（pull前後で呼ぶ）

$Pubdate = if ($env:KANSENKI_LOCAL_PUBDATE) { $env:KANSENKI_LOCAL_PUBDATE } else { (Get-Date).ToString('yyyyMMdd') }   # 掲載日＝当日（JST）
$LogDir  = Join-Path $Repo 'scripts\logs'    # .gitignore 済み（logは決してcommitしない）
$LogFile = Join-Path $LogDir ("writeKansenki_{0}.log" -f $Pubdate)
$LockFile = Join-Path $LogDir '.writeKansenki.lock'

$SourceRel   = "docs/data/kansenki/source/$Pubdate.json"
$ArticlesDir = Join-Path $Repo 'docs\data\kansenki\articles'
$RunbookPath = Join-Path $Repo 'docs\data\kansenki\runbook.md'
$RulesPath   = 'docs/data/kansenki/kansenkiRules.md'

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }

function Log($msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
    Add-Content -Path $LogFile -Value $line -Encoding utf8
}

# native の stderr を 2>&1 で拾うと PS5.1 では ErrorRecord 化し、Stop 下で exit0 でも失敗扱いになる。
# 捕捉中だけ Continue に落とし、成否は $LASTEXITCODE で判定する（gitleaks等のstderr対策）。
function Invoke-Native([scriptblock]$block) {
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { return (& $block 2>&1 | Out-String) }
    finally { $ErrorActionPreference = $prev }
}
function Invoke-Step($what, [scriptblock]$block) {
    $out = Invoke-Native $block
    if ($out.Trim()) { Log ("{0}:`n{1}" -f $what, $out.TrimEnd()) }
    if ($LASTEXITCODE -ne 0) { throw ("{0} が失敗 (exit {1})" -f $what, $LASTEXITCODE) }
    return $out
}

# 執筆計画の三状態判定。.github/workflows/writeKansenki.yml の plan ステップ（PR #387）と同じ分類。
#   執筆 : 未執筆かつ書ける場がある
#   正常 : 全場執筆済、または書けない場が前日非開催（lint --coverage と同じ除外）だけ
#   未検証: 掲載日が取れない / source が無い / 場数0 / 入力が揃わず書けない場がある
# 引数: plan.json のパス。出力: {state, why, unresolved:[..], excused:[..]} の JSON 1行。
$PlanJudgePy = @'
import json, sys
sys.path.insert(0, "scripts")
from lintKansenki import prev_day_race_count
p = json.load(open(sys.argv[1], encoding="utf-8-sig"))
pub = p.get("pubdate") or ""
to_write = p.get("toWrite") or []
venues = (p.get("counts") or {}).get("venues", 0)
unresolved, excused = [], []
for s in p.get("skip") or []:
    if "results空" in (s.get("reason") or "") and pub and prev_day_race_count(pub, s.get("jcd")) == 0:
        excused.append(s.get("jcd"))
    else:
        unresolved.append("%s(%s): %s" % (s.get("jcd"), s.get("venue"), s.get("reason")))
if not pub:
    state, why = "未検証", "掲載日を決定できない（CSV・highlights とも取れない）"
elif not p.get("source"):
    state, why = "未検証", "source/%s.json が無い（入力なし）" % pub
elif venues == 0:
    state, why = "未検証", "source/%s.json の場数が0（判定できない）" % pub
elif to_write:
    state, why = "執筆", "未執筆かつ書ける場 %d" % len(to_write)
elif unresolved:
    state, why = "未検証", "書ける場0・入力が揃わず書けない場 %d" % len(unresolved)
else:
    state, why = "正常", "全%d場 執筆済 %d・構造上除外 %d" % (venues, len(p.get("done") or []), len(excused))
print(json.dumps({"state": state, "why": why, "unresolved": unresolved, "excused": excused}, ensure_ascii=False))
'@

# 生成済み記事(articles/<pubdate>-<jcd>.json)の jcd 一覧を返す（レジューム判定用）。
function Get-DoneJcds {
    @(Get-ChildItem -Path (Join-Path $ArticlesDir ("{0}-*.json" -f $Pubdate)) -ErrorAction SilentlyContinue |
        ForEach-Object { [regex]::Match($_.Name, '-(\d{2})\.json$').Groups[1].Value } |
        Where-Object { $_ })
}

# --- 同時実行防止 --------------------------------------------------------
if (Test-Path $LockFile) {
    $old = Get-Content $LockFile -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($old -and (Get-Process -Id $old -ErrorAction SilentlyContinue)) {
        Log ("先行プロセス(PID {0})が実行中のため中止" -f $old); exit 0
    }
    Log "残存ロックを検出（前回が異常終了）。奪取して続行"
    Remove-Item $LockFile -Force -ErrorAction SilentlyContinue
}
Set-Content -Path $LockFile -Value $PID -Encoding ascii

try {
    Set-Location $Repo
    $env:PYTHONIOENCODING = 'utf-8'
    # native(python/git/claude) の stdout を UTF-8 で復号する。
    # 既定は [Console]::OutputEncoding=CP932 のため、pubplan の JSON 出力が化けて
    # ConvertFrom-Json が失敗する（2026-08-12 の記事0本の原因）。
    [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
    $env:PATH = $PyDir + ';' + $env:PATH   # claude の子プロセスで `python` を実体へ
    Log "=== 開始 pubdate=$Pubdate ==="

    # --- a) main へ同期（ユーザー作業に触らない） -----------------------
    $branch = (& $Git rev-parse --abbrev-ref HEAD).Trim()
    if ($branch -ne 'main') { Invoke-Step 'git checkout main' { & $Git checkout main } | Out-Null }
    $dirty = & $Git status --porcelain --untracked-files=no
    if ($dirty) {
        # 退避（ユーザー作業の巻き込み回避）は exit 3。成功(0)・失敗(1)と区別し、health/status.json で「退避」として出す。
        Log ("[退避] 理由=作業ツリーに未コミット変更（ユーザー作業の巻き込み回避）。何もせず終了:`n{0}" -f ($dirty | Out-String).TrimEnd())
        exit 3
    }
    # 破壊防止ガード1（pull前）: remoteが想定リポか検証。旧URL(空リポ)なら非0で中断。
    Invoke-Step 'ガード1(remote検証)' { & $Ps -NoProfile -ExecutionPolicy Bypass -File $Guard -Stage pre -Repo $Repo -LogFile $LogFile -Git $Git } | Out-Null
    Invoke-Step 'git pull origin main' { & $Git pull origin main } | Out-Null
    # 破壊防止ガード2（pull直後）: 必須ファイル消失＝作業ツリー破壊なら非0で中断（自動復旧しない）。
    Invoke-Step 'ガード2(worktree健全性)' { & $Ps -NoProfile -ExecutionPolicy Bypass -File $Guard -Stage post -Repo $Repo -LogFile $LogFile } | Out-Null

    # --- b) 執筆計画（未執筆かつ書ける場） -------------------------------
    $planPath = Join-Path $env:TEMP 'plan.json'
    $planText = Invoke-Native { & $Py scripts\kansenki_pubplan.py --pubdate $Pubdate }
    Set-Content -Path $planPath -Value $planText -Encoding utf8
    if ($LASTEXITCODE -ne 0) { throw "kansenki_pubplan.py が失敗 (exit $LASTEXITCODE)" }
    $plan = $planText | ConvertFrom-Json
    $toWrite = @($plan.toWrite)
    Log ("pubplan: pubdate={0} toWrite=[{1}] (計{2}場)" -f $plan.pubdate, ($toWrite -join ' '), $toWrite.Count)
    # 三状態の判定（旧: toWrite 空なら理由を問わず「正常終了」）
    $judgePath = Join-Path $env:TEMP 'kansenki_plan_judge.py'
    Set-Content -Path $judgePath -Value $PlanJudgePy -Encoding utf8
    $judgeText = Invoke-Native { & $Py $judgePath $planPath }
    if ($LASTEXITCODE -ne 0) { throw ("執筆計画の判定が失敗 (exit {0})`n{1}" -f $LASTEXITCODE, $judgeText.TrimEnd()) }
    $judge = $judgeText | ConvertFrom-Json
    $unresolved = @($judge.unresolved | Where-Object { $_ })
    Log ("判定: {0} — {1}" -f $judge.state, $judge.why)
    foreach ($u in $unresolved) { Log ("  書けない場: {0}" -f $u) }
    if ($judge.state -eq '未検証') {
        Log "※ 未検証（入力が無い・判定できない）のため失敗として終了。"
        exit 1
    }
    if ($judge.state -eq '正常') {
        Log "執筆対象なし（正常な0）。正常終了。"
        exit 0
    }

    # --- c) 二重執筆防止 ------------------------------------------------
    $existing = @(Get-ChildItem -Path (Join-Path $ArticlesDir ("{0}-*.json" -f $Pubdate)) -ErrorAction SilentlyContinue)
    if ($existing.Count -gt 0) {
        # 書ける場が残っているのに書かずに終わる＝未完了。旧: 正常終了（exit 0）。
        Log ("既存記事 {0} 本あり → 二重執筆防止のため書かない。未執筆 {1}場=[{2}] が残るので失敗として終了。" -f $existing.Count, $toWrite.Count, ($toWrite -join ' '))
        exit 1
    }

    # --- d) スタイル決定（位置引数フォーム） ----------------------------
    Invoke-Step 'assign_styles.py' { & $Py scripts\assign_styles.py $SourceRel } | Out-Null

    # --- e) 執筆（headless claude・未執筆場のみ・push しない・レジューム最大3試行） ---
    #   max-turns 到達等で claude が途中終了(rc≠0)しても throw しない（旧実装はここで
    #   生成済みの記事を丸ごと捨てていた）。生成済み分を活かし、不足場のみを対象に
    #   再実行する（初回＋再試行2回＝最大3試行）。既に生成済みの場は対象から外す＝再執筆しない。
    $runbook = Get-Content $RunbookPath -Raw -Encoding utf8
    $claudeOut = Join-Path $env:TEMP ("claude_out_{0}.json" -f $Pubdate)
    $maxAttempts = 3
    $claudeRc = 0
    for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
        $done = @(Get-DoneJcds)
        $remaining = @($toWrite | Where-Object { $_ -notin $done })
        if ($remaining.Count -eq 0) { Log "全対象が生成済み → claude実行不要"; break }
        $targetStr = ($remaining -join ' ')
        $header = "掲載日=$Pubdate。執筆対象の場コード(jcd)は次のみ: $targetStr。この対象場だけを執筆し、既存記事のある場は絶対に上書きしない。PR作成・push・mergeは行わない（公開はスクリプトが行う）。以下のランブックに厳密に従うこと。"
        $prompt = $header + "`r`n`r`n" + $runbook   # runbook はデータとして連結（再解釈させない）
        Log ("claude 実行開始（試行 {0}/{1}・対象{2}場=[{3}]・model=claude-sonnet-5, max-turns=200, acceptEdits）" -f $attempt, $maxAttempts, $remaining.Count, $targetStr)
        $prev = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
        & $Claude -p $prompt `
            --append-system-prompt-file $RulesPath `
            --allowedTools "Read,Write,Edit,Bash(python scripts/assign_styles.py*),Bash(python scripts/lintKansenki.py*),Bash(python scripts/kansenki_pubplan.py*)" `
            --permission-mode acceptEdits `
            --max-turns 200 `
            --model claude-sonnet-5 `
            --output-format json 2>&1 | Out-File -FilePath $claudeOut -Encoding utf8
        $claudeRc = $LASTEXITCODE
        $ErrorActionPreference = $prev
        try {
            $cj = Get-Content $claudeOut -Raw -Encoding utf8 | ConvertFrom-Json
            Log ("claude 完了 rc={0} cost_usd={1} session={2}" -f $claudeRc, $cj.total_cost_usd, $cj.session_id)
        } catch {
            Log ("claude 完了 rc={0}（JSON解析不可・出力先 {1}）" -f $claudeRc, $claudeOut)
        }
        $doneAfter = @(Get-DoneJcds)
        $after = @($toWrite | Where-Object { $_ -notin $doneAfter })
        if ($after.Count -eq 0) { Log ("全{0}場の生成を確認" -f $toWrite.Count); break }
        $progressed = ($after.Count -lt $remaining.Count)
        if ($attempt -lt $maxAttempts) {
            if (-not $progressed -and $claudeRc -eq 0) {
                Log ("進捗なし・rc=0 → 再試行しない（未生成 {0}場=[{1}]）" -f $after.Count, ($after -join ' ')); break
            }
            Log ("未生成 {0}場=[{1}]（rc={2}）→ 再実行 {3}/{4}" -f $after.Count, ($after -join ' '), $claudeRc, ($attempt + 1), $maxAttempts)
        } else {
            Log ("最大試行到達。未生成 {0}場=[{1}]（rc={2}）" -f $after.Count, ($after -join ' '), $claudeRc)
        }
    }

    # --- f) 検査: 各記事 lint → FAIL は削除（持ち越し）。PASS分は必ず公開する ---
    $written = @(Get-ChildItem -Path (Join-Path $ArticlesDir ("{0}-*.json" -f $Pubdate)) -ErrorAction SilentlyContinue)
    if ($written.Count -eq 0) { Log "生成物なし（書ける場があるのに記事が1本も出ない）→ 公開なし。不合格として失敗終了。"; exit 1 }
    $keep = @()
    foreach ($f in $written) {
        $rel = 'docs/data/kansenki/articles/' + $f.Name
        $lintOut = Invoke-Native { & $Py scripts\lintKansenki.py $rel }
        if ($LASTEXITCODE -eq 0) {
            $keep += $rel
        } else {
            Log ("lint FAIL → 除外(持ち越し): {0}`n{1}" -f $f.Name, $lintOut.TrimEnd())
            Remove-Item $f.FullName -Force
        }
    }
    Log ("lint 結果: PASS {0}場 / 生成 {1}場" -f $keep.Count, $written.Count)
    if ($keep.Count -eq 0) { Log "全対象 lint FAIL → 公開なし。不合格として失敗終了。"; exit 1 }

    # --- g) 公開: lint PASS 記事は途中終了でも必ず add → commit → pull --rebase → push ---
    Invoke-Step 'git add' { & $Git add $keep } | Out-Null
    $staged = & $Git diff --staged --name-only
    if (-not $staged) { Log "新規記事なのに差分なし（判定できない）→ 未検証として失敗終了。"; exit 1 }
    $msg = "kansenki: $Pubdate 掲載分 観戦記 +$($keep.Count)場（local・場単位・lint PASS分）"
    Invoke-Step 'git commit' { & $Git commit -m $msg } | Out-Null
    try {
        Invoke-Step 'git pull --rebase' { & $Git pull --rebase origin main } | Out-Null
    } catch {
        Invoke-Native { & $Git rebase --abort } | Out-Null
        throw "git pull --rebase が衝突。中止した（ローカルのコミットは残存。手動確認が必要）"
    }
    Invoke-Step 'git push' { & $Git push origin main } | Out-Null
    $head = (& $Git rev-parse --short HEAD).Trim()

    # --- h) 網羅性の確定（PASS分は公開済み。不足があれば最終行に明記して終了） ---
    $passJcds = @($keep | ForEach-Object { [regex]::Match($_, '-(\d{2})\.json$').Groups[1].Value })
    $missing = @($toWrite | Where-Object { $_ -notin $passJcds })
    if ($missing.Count -eq 0) {
        Invoke-Native { & $Py scripts\lintKansenki.py --coverage $Pubdate } | Out-Null
        if ($unresolved.Count -gt 0) {
            Log ("{0}場を push（{1}）。ただし入力が揃わず書けない場 {2} が残る（未検証）→ 失敗として終了。" -f $keep.Count, $head, $unresolved.Count)
            exit 1
        }
        Log ("=== 完了: {0}場を push（{1}）・全{2}場網羅 ===" -f $keep.Count, $head, $toWrite.Count)
        exit 0
    }
    Log ("{0}場を push（{1}）" -f $keep.Count, $head)
    Log ("未完了：{0}場が未コミット（jcd=[{1}]）。手動穴埋めが必要" -f $missing.Count, ($missing -join ' '))
    exit 1
}
catch {
    Log ("ERROR: {0}" -f $_.Exception.Message)
    Log "※ 失敗のまま終了。次回実行で再試行される"
    exit 1
}
finally {
    Remove-Item $LockFile -Force -ErrorAction SilentlyContinue
    Get-ChildItem $LogDir -Filter 'writeKansenki_*.log' -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } |
        Remove-Item -Force -ErrorAction SilentlyContinue
}
