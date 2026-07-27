# checkRepoGuard.ps1
# 自走スクリプト(writeKansenkiLocal.ps1 / dailyMotorUsage.ps1)の「破壊防止ガード」本体。
# 両スクリプトから pull の前後に呼ぶ。異常時は真偽値を返さず 非0 exit で中断させる。
# ★自動復旧(reset/clean/checkout 等)は一切しない＝中断のみ。localdata等の未追跡を守るため。
#
# 背景(2026-07-27): 旧リポ名が別の空リポに占有され、旧remoteのまま pull --rebase が
#   「成功」してローカル作業ツリーを空リポ状態(scripts が1本)に置換して破壊した。
#   それを2段で防ぐ:
#     -Stage pre  : pull前。origin のURLが想定リポ名を含むか検証。含まなければ中断。
#     -Stage post : pull直後。必須ファイル(build_highlights.py)の存在を確認。無ければ中断。
#
# 使い方(各スクリプトから):
#   & $Ps -NoProfile -ExecutionPolicy Bypass -File checkRepoGuard.ps1 -Stage pre  -Repo <repo> -LogFile <log> -Git <git>
#   & $Ps -NoProfile -ExecutionPolicy Bypass -File checkRepoGuard.ps1 -Stage post -Repo <repo> -LogFile <log>
#   → exit 0=通過 / exit 1=異常(中断)。呼び出し側は Invoke-Step で包み、非0なら throw→中断。

param(
    [Parameter(Mandatory=$true)][ValidateSet('pre','post')][string]$Stage,
    [Parameter(Mandatory=$true)][string]$Repo,
    [Parameter(Mandatory=$true)][string]$LogFile,
    [string]$Git = 'C:\Program Files\Git\cmd\git.exe'
)

# ★リポジトリをリネームしたら、この1行だけ直す（想定リポジトリ名）。
$ExpectedRepo = 'pallas-mercato-7k9'
# pull後に「必ず存在するはず」の必須ファイル（消えていたら作業ツリー破壊とみなす）。
$RequiredFile = 'scripts/build_highlights.py'

function GLog($msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
    try { Add-Content -Path $LogFile -Value $line -Encoding utf8 } catch {}
}

Set-Location $Repo

if ($Stage -eq 'pre') {
    # ガード1（事前）: remote が想定リポか
    $prev = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    $url = (& $Git remote get-url origin 2>&1 | Out-String).Trim()
    $ErrorActionPreference = $prev
    if ($url -notlike "*$ExpectedRepo*") {
        GLog ("ガード1: remoteが想定と異なる。旧URLの可能性。pullを中止した（origin=[{0}] / 想定=[{1}]）" -f $url, $ExpectedRepo)
        exit 1
    }
    GLog ("ガード1: remote検証OK（origin=[{0}] に想定名[{1}]を含む）" -f $url, $ExpectedRepo)
    exit 0
}
else {
    # ガード2（事後）: pull後に必須ファイルが消えていないか（ガード1すり抜け時の保険）
    $target = Join-Path $Repo $RequiredFile
    if (-not (Test-Path -LiteralPath $target)) {
        GLog ("ガード2: pull後に必須ファイル({0})が消失。作業ツリーが破壊された可能性。処理を中止（自動復旧はしない）" -f $RequiredFile)
        exit 1
    }
    GLog ("ガード2: 必須ファイル({0})の存在を確認。作業ツリー健全" -f $RequiredFile)
    exit 0
}
