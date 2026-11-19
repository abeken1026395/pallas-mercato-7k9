# authPrecheck.ps1
# 観戦記の執筆に使う claude の認証が生きているかを毎日確かめる（夕方便 18:40 の前）。
# 通ったら何も知らせず exit 0。落ちたら通知用WF kansenkiAuthAlarm.yml を起動（bot が Issue を立てる＝本人に通知が届く。
# ラベル kansenki-auth の Open があれば起票しない）して exit 1。結果は scripts\logs\authPrecheck_YYYYMMDD.log に1行。
# トークンは読むだけ。値は表示・記録しない。
# 試験用: 環境変数 AUTHPRECHECK_DRYRUN=1 なら Issue を起票せず、文面を標準出力に出す（「試験」付きの文面）。
#         プロセス環境に CLAUDE_CODE_OAUTH_TOKEN が既にあればユーザー環境変数で上書きしない（無効値での失敗試験用）。
# 文字コード: このファイルは UTF-8 BOM 付きで保存すること。

$ErrorActionPreference = 'Continue'

$Repo   = Split-Path $PSScriptRoot
$Claude = if ($env:KANSENKI_LOCAL_CLAUDE) { $env:KANSENKI_LOCAL_CLAUDE } else { 'C:\Users\USER\.local\bin\claude.exe' }
$LogDir = Join-Path $Repo 'scripts\logs'
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
$LogFile = Join-Path $LogDir ("authPrecheck_{0}.log" -f (Get-Date -Format 'yyyyMMdd'))
$DryRun  = ($env:AUTHPRECHECK_DRYRUN -eq '1')

function Log([string]$msg) {
    Add-Content -Path $LogFile -Value ("[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg) -Encoding utf8
}

if (-not $env:CLAUDE_CODE_OAUTH_TOKEN) {
    $tok = [Environment]::GetEnvironmentVariable('CLAUDE_CODE_OAUTH_TOKEN', 'User')
    if ($tok) { $env:CLAUDE_CODE_OAUTH_TOKEN = $tok }
}

$ok = $false; $why = ''
if (-not (Test-Path $Claude)) {
    $why = 'claude.exe が見つからない'
} else {
    $out = & $Claude -p 'ok とだけ返してください' --max-turns 1 --model claude-sonnet-5 --output-format json 2>&1 | Out-String
    $rc = $LASTEXITCODE
    if ($rc -ne 0) { $why = "rc=$rc" }
    elseif ($out -match '(?i)"is_error"\s*:\s*true|authentication|expired|unauthorized|invalid.*token|/login') { $why = "認証エラーの疑い rc=0" }
    else { $ok = $true }
}

if ($ok) {
    Log 'OK 認証は通った（rc=0）'
    exit 0
}

Log ("NG 認証の事前チェックに失敗（{0}）" -f $why)
$title = '観戦記の認証が切れています（事前チェック失敗）'
$body  = "観戦記の認証が切れています。PCで claude setup-token をやり直してください。`n`n事前チェック（scripts/authPrecheck.ps1）で claude -p が失敗しました（$why）。夕方便（18:40〜）の執筆が落ちる前に直してください。`n（自動起票。直ったら Issue を閉じてください。）"
if ($DryRun) {
    $title = '【試験】' + $title
    $body  = '【試験】これは試験で、実際の起票はしていません。' + "`n" + $body
    Write-Output ("DRYRUN 通知: {0}`n{1}" -f $title, $body)
    Log 'DRYRUN のため Issue は起票しない'
    exit 1
}

try {
    Push-Location $Repo
    & gh workflow run kansenkiAuthAlarm.yml -f ("reason=" + $why) 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { Log '通知用WF（kansenkiAuthAlarm）を起動した' } else { Log '通知用WFの起動に失敗（ログのみ）' }
} catch { Log ("通知失敗: {0}" -f $_.Exception.Message) }
finally { Pop-Location }
exit 1
