# codeWatcher.ps1
# 統括チャット（claude.ai）が Drive の codeShikyu に置いた支給物を、ローカルCodeで無人実行する見張り。
# けんが「latest.md を読んで実行」の1行を貼る手間をなくす（2026-09-27 けん裁定・案1）。
#
# 動き（タスクスケジューラから5分ごと）:
#   1. codeShikyu\<作業フォルダ>\ のうち、latest.md と kick.txt があり、report.md と done.txt が無いものを探す
#   2. kick.txt の1行目（sha256）と latest.md の実物の sha256 が一致したものだけ実行する
#      一致しないときは Drive の同期待ちとみなし、kick.txt から30分までは次の回に回す。30分を超えたら停止扱い
#   3. claude -p で「latest.md を読んで実行」を渡す。kick.txt の2行目以降（けん承認の一文）を指示に足す
#   4. 終わったら done.txt を置く。Code が report.md を置かずに終わったときは、見張りが「停止」の report.md を置く
#
# 起動の合図は kick.txt だけ。統括は latest.md と付属物を置き終えてから、最後に kick.txt を置く。
# kick.txt の承認文は、けんが claude.ai のチャットで承認したときだけ統括が書く（見張りは中身を判断しない）。
#
# ログは C:\Users\USER\boatrace\scripts\logs\codeWatcher_YYYYMMDD.log（.gitignore 済み）。
# 文字コード: このファイルは UTF-8 BOM 付きで保存すること（BOM無しだと PS5.1 が cp932 と誤解釈する）。

$ErrorActionPreference = 'Stop'

$Repo    = 'C:\Users\USER\boatrace'
$Shikyu  = 'G:\マイドライブ\データ攻め\codeShikyu'
$Py      = 'C:\Users\USER\AppData\Local\Python\pythoncore-3.14-64\python.exe'
$Claude  = 'C:\Users\USER\.local\bin\claude.exe'
$PyDir   = Split-Path $Py
$LogDir  = Join-Path $Repo 'scripts\logs'
$LogFile = Join-Path $LogDir ("codeWatcher_{0}.log" -f (Get-Date -Format 'yyyyMMdd'))
$Lock    = Join-Path $LogDir '.codeWatcher.lock'
$SyncWaitMinutes = 30

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }

function Log($msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
    Add-Content -Path $LogFile -Value $line -Encoding utf8
}

function Write-Utf8NoBom($path, $text) {
    [System.IO.File]::WriteAllText($path, $text, (New-Object System.Text.UTF8Encoding $false))
}

# --- 多重起動の防止 ---------------------------------------------------------
if (Test-Path $Lock) {
    $old = Get-Content $Lock -ErrorAction SilentlyContinue
    if ($old -and (Get-Process -Id $old -ErrorAction SilentlyContinue)) { exit 0 }
    Remove-Item $Lock -Force -ErrorAction SilentlyContinue
}

if (-not (Test-Path $Shikyu)) { Log "codeShikyu が見えない（Drive 未起動か未同期）: $Shikyu"; exit 0 }

# --- 候補を探す（kick.txt の古い順に1件だけ） -------------------------------
$cands = @(Get-ChildItem -Path $Shikyu -Directory | Where-Object {
    (Test-Path (Join-Path $_.FullName 'kick.txt')) -and
    (Test-Path (Join-Path $_.FullName 'latest.md')) -and
    -not (Test-Path (Join-Path $_.FullName 'report.md')) -and
    -not (Test-Path (Join-Path $_.FullName 'done.txt'))
} | Sort-Object { (Get-Item (Join-Path $_.FullName 'kick.txt')).LastWriteTime })

if ($cands.Count -eq 0) { exit 0 }

$dir    = $cands[0].FullName
$name   = $cands[0].Name
$latest = Join-Path $dir 'latest.md'
$kick   = Join-Path $dir 'kick.txt'
$report = Join-Path $dir 'report.md'
$done   = Join-Path $dir 'done.txt'

$kickLines = @(Get-Content $kick -Encoding UTF8)
$want = if ($kickLines.Count -ge 1) { $kickLines[0].Trim().ToLower() } else { '' }
$have = (Get-FileHash -Algorithm SHA256 $latest).Hash.ToLower()

if ($want -ne $have) {
    $age = ((Get-Date) - (Get-Item $kick).LastWriteTime).TotalMinutes
    if ($age -lt $SyncWaitMinutes) {
        Log ("[{0}] sha256 不一致（同期待ち {1:N0}分）want={2} have={3}" -f $name, $age, $want, $have)
        exit 0
    }
    Write-Utf8NoBom $report "停止 / 見張り: latest.md の sha256 が kick.txt と一致しないまま30分を超えた（実行していない）"
    Write-Utf8NoBom $done ("{0} sha不一致で停止" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))
    Log ("[{0}] sha256 不一致のまま30分超。停止の report.md を置いた" -f $name)
    exit 0
}

# --- 実行 -------------------------------------------------------------------
Set-Content -Path $Lock -Value $PID -Encoding ascii
try {
    Set-Location $Repo
    $env:PYTHONIOENCODING = 'utf-8'
    [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
    $env:PATH = $PyDir + ';' + $env:PATH

    $approval = (($kickLines | Select-Object -Skip 1) -join "`n").Trim()
    $prompt = "$latest を読んで実行。"
    if ($approval) { $prompt += " $approval" }
    $prompt += "`n`nこれは見張りタスク codeWatcher からの無人実行で、チャットの相手はいない。質問して待たず、latest.md の停止条件に当たったら停止として report.md を置いて終える。報告は latest.md の指示どおり同じフォルダの report.md に置く。"

    $out = Join-Path $LogDir ("codeWatcher_{0}.json" -f $name)
    Log ("[{0}] 実行開始 sha256={1} 承認文={2}" -f $name, $have, ($(if ($approval) { 'あり' } else { 'なし' })))

    $prev = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    & $Claude -p $prompt `
        --add-dir $dir `
        --allowedTools "Read,Write,Edit,Glob,Grep,Bash(git:*),Bash(python:*),Bash(python3:*),Bash(py:*),Bash(gh:*),Bash(curl:*),Bash(ls:*),Bash(cat:*),Bash(head:*),Bash(tail:*),Bash(wc:*),Bash(grep:*),Bash(diff:*),Bash(sha256sum:*),Bash(cp:*),Bash(mkdir:*),Bash(node:*),Bash(npm:*),Bash(date:*),Bash(sleep:*)" `
        --disallowedTools "Bash(git push --force:*),Bash(git push -f:*),Bash(git clean:*),Bash(git rebase:*),Bash(git reset --hard:*),Bash(git add -A:*),Bash(git add .:*),Bash(git checkout --:*),Bash(git restore:*),Bash(git stash:*)" `
        --permission-mode acceptEdits `
        --max-turns 300 `
        --output-format json 2>&1 | Out-File -FilePath $out -Encoding utf8
    $rc = $LASTEXITCODE
    $ErrorActionPreference = $prev

    $sid = ''
    try { $sid = (Get-Content $out -Raw -Encoding utf8 | ConvertFrom-Json).session_id } catch {}
    Log ("[{0}] 終了 rc={1} session={2}" -f $name, $rc, $sid)

    if (-not (Test-Path $report)) {
        Write-Utf8NoBom $report ("停止 / 見張り: Code が report.md を置かずに終了（rc={0}・ログ scripts\logs\codeWatcher_{1}.json）" -f $rc, $name)
        Log ("[{0}] report.md が無いため停止の report.md を置いた" -f $name)
    }
    Write-Utf8NoBom $done ("{0} rc={1} session={2}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $rc, $sid)
}
catch {
    Log ("[{0}] 見張り自体の例外: {1}" -f $name, $_.Exception.Message)
    if (-not (Test-Path $report)) { Write-Utf8NoBom $report "停止 / 見張り: 実行中に例外（ログ参照）" }
    Write-Utf8NoBom $done ("{0} 例外" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))
}
finally {
    Remove-Item $Lock -Force -ErrorAction SilentlyContinue
}
