# dailyPartsBackfill.ps1
# motorParts.json の「モーターNo」空欄を K から後追い補填する（それだけをやる）。
#   → 補填があればコミット＆push。無ければ何も書かずに正常終了。
# Windowsタスクスケジューラから毎日 18:30 に実行される想定
# （登録: scripts/registerPartsBackfill.ps1）。
#
# なぜ dailyMotorUsage.ps1(06:00) から切り出すか:
#   補填は「Kファイル」と「beforeinfoの部品交換行」の両方が揃って初めて成立する。
#     - K は前日分が早朝に出る            → 06:00 で足りる
#     - beforeinfo は Actions が随時追記   → 実績の最終着地は JST 17:03〜17:18
#   06:00 の1本だけだと補填が常に beforeinfo より先に走り、最新1日分が
#   毎日およそ24時間ぶん空のまま残る（2026-07-31 に82件で観測）。
#
# dailyMotorUsage.ps1 側の backfill 呼び出しは削除していない。二段構えにする:
#   18:30 … 当日着地ぶんを埋める（本命）
#   翌 06:00 … 18:30 までに間に合わなかったぶんを拾う（保険）
#   Actions の遅延実績は3日ぶんしか見ていないため、より遅れる日に備える。
#   backfill は「空欄だけを埋める」冪等な処理なので、二重実行に害はない。
#
# 方針は dailyMotorUsage.ps1 と揃える:
#   - 失敗してもPCの他作業を止めない。全例外はログに残して非0で静かに終了する。
#   - main以外・作業ツリーが汚れている場合は何もせず退避（ユーザー作業を巻き込まない）。
#   - add するのは motorParts.json だけ。

$ErrorActionPreference = 'Stop'

$Repo = 'C:\Users\USER\boatrace'
# 絶対パス固定: タスクスケジューラのPATHは対話シェルと異なる。
$Py    = 'C:\Users\USER\AppData\Local\Python\pythoncore-3.14-64\python.exe'
$Git   = 'C:\Program Files\Git\cmd\git.exe'
$Ps    = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$Guard = 'C:\Users\USER\boatrace\scripts\checkRepoGuard.ps1'

$LogDir      = Join-Path $Repo 'scripts\logs'
$LogFile     = Join-Path $LogDir ("dailyPartsBackfill_{0}.log" -f (Get-Date -Format 'yyyyMMdd'))
$LockFile    = Join-Path $LogDir '.dailyPartsBackfill.lock'
$TargetParts = 'docs/data/motorParts.json'

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }

function Log($msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
    Add-Content -Path $LogFile -Value $line -Encoding utf8
}

# PS5.1 では native の stderr を 2>&1 すると各行が ErrorRecord に化け、
# ErrorActionPreference='Stop' 下では exit 0 でも終了エラーになる。
# 捕捉中だけ Continue に落とし、成否は $LASTEXITCODE だけで判定する。
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

# --- 同時実行防止 --------------------------------------------------------
# 06:00 の dailyMotorUsage と時刻は離れているが、手動実行との二重起動を防ぐ。
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
    $env:PYTHONIOENCODING = 'utf-8'   # ログの文字化け(cp932)防止
    Log "=== 開始 ==="

    # --- 安全確認: ユーザーの作業に触らない -----------------------------
    $branch = & $Git rev-parse --abbrev-ref HEAD
    if ($branch -ne 'main') {
        Log ("main ではなく '{0}' に居るため何もせず終了（ユーザー作業の巻き込み回避）" -f $branch)
        exit 0
    }
    $dirty = & $Git status --porcelain --untracked-files=no
    if ($dirty) {
        Log ("追跡ファイルに未コミット変更があるため何もせず終了:`n{0}" -f ($dirty | Out-String).TrimEnd())
        exit 0
    }

    # --- 最新originへ同期 ------------------------------------------------
    # motorParts.json は Actions側 fetchPartsExchange が随時追記するため、
    # 最新状態に対して補填する。ここを飛ばすと当日ぶんが手元に無い。
    Invoke-Step 'ガード1(remote検証)' { & $Ps -NoProfile -ExecutionPolicy Bypass -File $Guard -Stage pre -Repo $Repo -LogFile $LogFile -Git $Git } | Out-Null
    try {
        Invoke-Step 'git pull --rebase (開始時同期)' { & $Git pull --rebase origin main } | Out-Null
    } catch {
        Invoke-Native { & $Git rebase --abort } | Out-Null
        throw "開始時 git pull --rebase が衝突。中止した（手動確認が必要）"
    }
    Invoke-Step 'ガード2(worktree健全性)' { & $Ps -NoProfile -ExecutionPolicy Bypass -File $Guard -Stage post -Repo $Repo -LogFile $LogFile } | Out-Null

    # --- 補填 -------------------------------------------------------------
    # 空 "モーターNo" のみを埋める。K が無い日は埋めずに残す（創作しない）。
    Invoke-Step 'backfillMotorPartsMotorNo.py' { & $Py scripts\backfillMotorPartsMotorNo.py } | Out-Null

    # backfill は補填時のみ書く・updated等は触らない
    # → 素の差分があれば補填が起きた、という判定でよい
    $partsDirty = & $Git status --porcelain $TargetParts
    if (-not $partsDirty) {
        Log "補填なし（空欄0 または該当K無し）。コミットせず正常終了"
        exit 0
    }

    Invoke-Step 'git add' { & $Git add $TargetParts } | Out-Null
    Invoke-Step 'git commit' { & $Git commit -m 'auto: motorParts モーターNo補填' } | Out-Null

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
    Log "※ 失敗のまま終了。翌 06:00 の dailyMotorUsage 側 backfill が保険になる"
    exit 1
}
finally {
    Remove-Item $LockFile -Force -ErrorAction SilentlyContinue
    Get-ChildItem $LogDir -Filter 'dailyPartsBackfill_*.log' -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } |
        Remove-Item -Force -ErrorAction SilentlyContinue
}
