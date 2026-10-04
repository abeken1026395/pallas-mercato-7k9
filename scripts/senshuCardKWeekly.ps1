# senshuCardKWeekly.ps1
# 選手カード：Kファイルの新しい日を data/senshuCard/kExtra.csv に足して push する（週1回）。
# push すると Actions の updateSenshuCard.yml が集計・検査・書き出しをする。
# 登録: scripts/registerSenshuCardKWeekly.ps1（毎週月曜 6:40。dailyMotorUsage の 6:00 の後）
#
# 方針（dailyMotorUsage.ps1 と同じ）:
#   - mbrace は Actions から取れないため、Kファイルの取得はこの PC で行う。
#   - main 以外・作業ツリーが汚れているときは何もせず退避（exit 3）。
#   - 変わったときだけコミット。add するのは kExtra.csv だけ（.lzh はコミットしない）。

$ErrorActionPreference = 'Stop'

$Repo = if ($env:BOATRACE_LOCAL_REPO) { $env:BOATRACE_LOCAL_REPO } else { 'C:\Users\USER\boatrace' }
$Py  = 'C:\Users\USER\AppData\Local\Python\pythoncore-3.14-64\python.exe'
$Git = 'C:\Program Files\Git\cmd\git.exe'
$Ps    = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$Guard = Join-Path $Repo 'scripts\checkRepoGuard.ps1'

$LookbackDays = 21   # 取りこぼし吸収。既にある日は fetchKfiles が取り直さない
$LogDir   = Join-Path $Repo 'scripts\logs'
$LogFile  = Join-Path $LogDir ("senshuCardKWeekly_{0}.log" -f (Get-Date -Format 'yyyyMMdd'))
$LockFile = Join-Path $LogDir '.senshuCardKWeekly.lock'
$Target   = 'data/senshuCard/kExtra.csv'

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }

function Log($msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
    Add-Content -Path $LogFile -Value $line -Encoding utf8
}

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

if (Test-Path $LockFile) {
    $old = Get-Content $LockFile -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($old -and (Get-Process -Id $old -ErrorAction SilentlyContinue)) {
        Log ("先行プロセス(PID {0})が実行中のため中止" -f $old)
        exit 0
    }
    Log "残存ロックを検出（前回が異常終了）。奪取して続行"
    Remove-Item $LockFile -Force -ErrorAction SilentlyContinue
}
Set-Content -Path $LockFile -Value $PID -Encoding ascii

try {
    Set-Location $Repo
    $env:PYTHONIOENCODING = 'utf-8'
    Log "=== 開始 ==="

    $branch = & $Git rev-parse --abbrev-ref HEAD
    if ($branch -ne 'main') {
        Log ("[退避] 理由=main 以外のブランチ '{0}'。何もせず終了" -f $branch)
        exit 3
    }
    $dirty = & $Git status --porcelain --untracked-files=no
    if ($dirty) {
        Log ("[退避] 理由=作業ツリーに未コミット変更。何もせず終了:`n{0}" -f ($dirty | Out-String).TrimEnd())
        exit 3
    }

    Invoke-Step 'ガード1(remote検証)' { & $Ps -NoProfile -ExecutionPolicy Bypass -File $Guard -Stage pre -Repo $Repo -LogFile $LogFile -Git $Git } | Out-Null
    try {
        Invoke-Step 'git pull --rebase (開始時同期)' { & $Git pull --rebase origin main } | Out-Null
    } catch {
        Invoke-Native { & $Git rebase --abort } | Out-Null
        throw "開始時 git pull --rebase が衝突。中止した（手動確認が必要）"
    }
    Invoke-Step 'ガード2(worktree健全性)' { & $Ps -NoProfile -ExecutionPolicy Bypass -File $Guard -Stage post -Repo $Repo -LogFile $LogFile } | Out-Null

    # 1) Kファイル収集（欠けた日は欠けたまま続ける）
    $env:START = (Get-Date).AddDays(-$LookbackDays).ToString('yyyyMMdd')
    $env:END   = (Get-Date).AddDays(-1).ToString('yyyyMMdd')
    Log ("Kファイル収集: {0} 〜 {1}" -f $env:START, $env:END)
    $fetchOut = Invoke-Native { & $Py scripts\fetchKfiles.py }
    Log ("fetchKfiles.py:`n{0}" -f $fetchOut.TrimEnd())
    if ($LASTEXITCODE -ne 0) { Log "※ 取得できない日があった（欠損のまま継続）" }

    # 2) kExtra.csv に足す（今日の2日前まで・results がある日だけ）
    Invoke-Step 'kExtraUpdate.py' { & $Py scripts\senshuCard\kExtraUpdate.py } | Out-Null

    $changed = & $Git status --porcelain $Target
    if (-not $changed) {
        Log "変更なし。コミットせず正常終了"
        exit 0
    }

    Invoke-Step 'git add' { & $Git add $Target } | Out-Null
    Invoke-Step 'git commit' { & $Git commit -m 'auto: 選手カード Kファイルの追記 (data/senshuCard/kExtra.csv)' } | Out-Null
    try {
        Invoke-Step 'git pull --rebase' { & $Git pull --rebase origin main } | Out-Null
    } catch {
        Invoke-Native { & $Git rebase --abort } | Out-Null
        throw "git pull --rebase が衝突。rebase を中止した（ローカルのコミットは残存。手動確認が必要）"
    }
    Invoke-Step 'git push' { & $Git push origin main } | Out-Null
    Log ("=== 完了: {0} を push ===" -f (& $Git rev-parse --short HEAD))
    exit 0
}
catch {
    Log ("ERROR: {0}" -f $_.Exception.Message)
    exit 1
}
finally {
    Remove-Item $LockFile -Force -ErrorAction SilentlyContinue
    Get-ChildItem $LogDir -Filter 'senshuCardKWeekly_*.log' -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-60) } |
        Remove-Item -Force -ErrorAction SilentlyContinue
}
