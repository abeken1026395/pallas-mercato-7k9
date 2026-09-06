# dailyRacerSchedule.ps1
# 選手の出場予定を公式サイトから全件取得 → 配布物を再生成 → 変更があればコミット＆push。
# Windowsタスクスケジューラから毎日1回 02:00 に実行される想定。
#
# 方針:
#   - dailyMotorUsage.ps1 と同じ型。失敗してもPCの他作業を止めない。
#   - main以外・作業ツリーが汚れている場合は何もせず退避（ユーザー作業の巻き込み回避）。
#   - 取得は約70分かかる。MultipleInstances=IgnoreNew とロックで二重起動を防ぐ。
#   - 公式サイトへの負荷を抑えるため並列は4。8にすれば約35分だが、急ぐ理由がない。
#   - 正本 data/racerSchedule.json は全節を持つ。配布物 docs/data/racerSchedule.json は
#     buildRacerSchedule.py が先頭2節に絞って作る。両方をコミット対象にする。
#   - 生成時刻だけが変わる差分は捨てる（空コミットを作らない）。

$ErrorActionPreference = 'Stop'

$Repo = 'C:\Users\USER\boatrace'
$Py   = 'C:\Users\USER\AppData\Local\Python\pythoncore-3.14-64\python.exe'
$Git  = 'C:\Program Files\Git\cmd\git.exe'
$Ps    = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$Guard = 'C:\Users\USER\boatrace\scripts\checkRepoGuard.ps1'

$Workers   = 4
$Minutes   = 150   # 4並列なら約70分。詰まった日でも打ち切れるよう余裕を持たせる
$LogDir    = Join-Path $Repo 'scripts\logs'
$LogFile   = Join-Path $LogDir ("dailyRacerSchedule_{0}.log" -f (Get-Date -Format 'yyyyMMdd'))
$LockFile  = Join-Path $LogDir '.dailyRacerSchedule.lock'
$TargetSrc = 'data/racerSchedule.json'
$TargetDst = 'docs/data/racerSchedule.json'

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }

function Log($msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
    Add-Content -Path $LogFile -Value $line -Encoding utf8
}

# PS5.1 は native の stderr を ErrorRecord に化けさせる。
# ErrorActionPreference='Stop' 下では exit 0 でも終了エラーになるため、
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
    $env:PYTHONUTF8 = '1'
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

    # --- 0.5) 最新originへ同期 -------------------------------------------
    Invoke-Step 'ガード1(remote検証)' { & $Ps -NoProfile -ExecutionPolicy Bypass -File $Guard -Stage pre -Repo $Repo -LogFile $LogFile -Git $Git } | Out-Null
    try {
        Invoke-Step 'git pull --rebase (開始時同期)' { & $Git pull --rebase origin main } | Out-Null
    } catch {
        Invoke-Native { & $Git rebase --abort } | Out-Null
        throw "開始時 git pull --rebase が衝突。中止した（手動確認が必要）"
    }
    Invoke-Step 'ガード2(worktree健全性)' { & $Ps -NoProfile -ExecutionPolicy Bypass -File $Guard -Stage post -Repo $Repo -LogFile $LogFile } | Out-Null

    # --- 1) 出場予定を全件取得（正本を更新） -----------------------------
    Log ("取得開始: workers={0} minutes={1}" -f $Workers, $Minutes)
    Invoke-Step 'fetchRacerSchedule.py' { & $Py scripts\fetchRacerSchedule.py --minutes $Minutes --workers $Workers } | Out-Null

    # --- 2) 配布物を再生成 -----------------------------------------------
    # 未知の class を見つけると非0で止まる。黙って丸めない設計なのでここで失敗させる。
    Invoke-Step 'buildRacerSchedule.py' { & $Py scripts\buildRacerSchedule.py } | Out-Null

    # --- 3) 変更判定 ------------------------------------------------------
    # 生成時刻・取得時刻だけの差分は捨てる（実データが変わった時だけコミットする）。
    $verdict = (@'
import json, subprocess, sys
git = sys.argv[1]
drop = ("generated", "取得時刻", "生成時刻")
def norm(text):
    d = json.loads(text)
    for k in drop:
        d.pop(k, None)
    return json.dumps(d, sort_keys=True, ensure_ascii=False)
changed = False
for target in sys.argv[2:]:
    try:
        old = subprocess.run([git, "show", "HEAD:" + target], capture_output=True, check=True).stdout.decode("utf-8")
    except Exception:
        changed = True
        break
    with open(target, encoding="utf-8") as f:
        if norm(old) != norm(f.read()):
            changed = True
            break
print("CHANGED" if changed else "SAME")
'@ | & $Py - $Git $TargetSrc $TargetDst) | Select-Object -Last 1

    if ($verdict -eq 'SAME') {
        & $Git checkout -- $TargetSrc
        & $Git checkout -- $TargetDst
        Log "実データ変更なし（予定に動きなし）→ 対象外に戻す"
        exit 0
    }
    Log "実データ変更あり → コミット対象"

    # --- 4) コミット ------------------------------------------------------
    Invoke-Step 'git add' { & $Git add $TargetSrc $TargetDst } | Out-Null
    Invoke-Step 'git commit' { & $Git commit -m 'auto: 出場予定を更新 (data/racerSchedule.json, docs/data/racerSchedule.json)' } | Out-Null

    # --- 5) rebase してから push -----------------------------------------
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
    Log "※ 失敗のまま終了。次回実行で再試行される"
    exit 1
}
finally {
    Remove-Item $LockFile -Force -ErrorAction SilentlyContinue
    Get-ChildItem $LogDir -Filter 'dailyRacerSchedule_*.log' -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } |
        Remove-Item -Force -ErrorAction SilentlyContinue
}
