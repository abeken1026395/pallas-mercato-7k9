# dispatchNightly.ps1
# 夜間パイプライン（nightlyPipeline.yml）を GitHub の workflow_dispatch で起動するだけの小さなスクリプト。
# Windowsタスクスケジューラから 18:05 / 20:05 / 22:05 に実行される想定（登録: scripts/registerDispatchNightly.ps1）。
#
# なぜ要るか（2026-09-30 けん裁定）:
#   翌日の見どころ（highlights_next.json）は nightlyPipeline が作る。その起動は GitHub の schedule と
#   heartbeat（これも schedule）だけに頼っていた。2026-09-30 は 17:03 から 23:36 の予定27回が1回も発火せず、
#   手動で起動するまで翌日分が出なかった。PCの定時タスクから起動をかけて、18時台に翌日分を出す。
#   nightlyPipeline は冪等（現物を見て no-op／補完する）なので、多重に起動しても壊れない。
#
# 認証（上から順に使う）:
#   1) C:\Users\USER\.boatrace\dispatchToken.txt … 権限を「このリポジトリの Actions: Read and write」だけに
#      絞った fine-grained トークン（1行）。置いてあればこれを使う。
#   2) 無ければ、このPCの Git Credential Manager が持つ github.com の認証（dailyBfiles が push に使うもの）。
#   トークンの値はログにも画面にも出さない。
#
# 方針:
#   - 何も書き換えない（リポジトリの作業ツリーにも触れない）。起動をかけて、結果の HTTP コードを記録するだけ。
#   - 失敗してもPCの他作業を止めない。ログを残して非0で終了する。
#   - 引数 -Workflow で別のWFも起動できる（既定は nightlyPipeline.yml）。
# 文字コード: このファイルは UTF-8 BOM 付きで保存すること。
param([string]$Workflow = 'nightlyPipeline.yml')

$ErrorActionPreference = 'Stop'

$Owner   = 'abeken1026395'
$RepoNm  = 'pallas-mercato-7k9'
$Git     = 'C:\Program Files\Git\cmd\git.exe'
$TokFile = 'C:\Users\USER\.boatrace\dispatchToken.txt'
$LogDir  = 'C:\Users\USER\boatrace\scripts\logs'
$LogFile = Join-Path $LogDir ("dispatchNightly_{0}.log" -f (Get-Date -Format 'yyyyMMdd'))

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
function Log($msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
    Add-Content -Path $LogFile -Value $line -Encoding utf8
}

function Get-Token {
    if (Test-Path $TokFile) {
        $t = (Get-Content $TokFile -Raw).Trim()
        if ($t) { return @{ Token = $t; From = 'dispatchToken.txt' } }
    }
    # Git Credential Manager から github.com の認証を読む（標準入力に protocol/host を渡す）。
    $prev = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    try {
        $env:GCM_INTERACTIVE = 'never'
        $env:GIT_TERMINAL_PROMPT = '0'
        $out = "protocol=https`nhost=github.com`n`n" | & $Git credential fill 2>$null
    } finally { $ErrorActionPreference = $prev }
    $pw = ($out | Where-Object { $_ -like 'password=*' } | Select-Object -First 1)
    if ($pw) { return @{ Token = $pw.Substring(9); From = 'Git Credential Manager' } }
    return $null
}

try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $tk = Get-Token
    if (-not $tk) { throw '認証が見つからない（dispatchToken.txt も Git Credential Manager も無い）' }

    $uri  = "https://api.github.com/repos/$Owner/$RepoNm/actions/workflows/$Workflow/dispatches"
    $hdr  = @{
        'Authorization'        = 'Bearer ' + $tk.Token
        'Accept'               = 'application/vnd.github+json'
        'X-GitHub-Api-Version' = '2022-11-28'
        'User-Agent'           = 'boatrace-dispatchNightly'
    }
    $resp = Invoke-WebRequest -Uri $uri -Method Post -Headers $hdr -ContentType 'application/json' `
        -Body '{"ref":"main"}' -UseBasicParsing -TimeoutSec 30
    if ([int]$resp.StatusCode -eq 204) {
        Log ("起動OK: {0}（HTTP 204・認証={1}）" -f $Workflow, $tk.From)
        exit 0
    }
    throw ("想定外の応答: HTTP {0}" -f $resp.StatusCode)
}
catch {
    $code = $null
    if ($_.Exception.Response) { try { $code = [int]$_.Exception.Response.StatusCode } catch {} }
    Log ("起動NG: {0}（HTTP {1}）{2}" -f $Workflow, $code, $_.Exception.Message)
    exit 1
}
