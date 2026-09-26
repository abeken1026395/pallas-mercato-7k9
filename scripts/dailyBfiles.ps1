# dailyBfiles.ps1
# Bファイル（番組表）の差分取得 → 級別の履歴を作り直す → docs/data/rankHistory.json の選手データが変わった日だけ commit & push。
# Windowsタスクスケジューラから毎日 6:40 に実行される想定（登録: scripts/registerDailyBfiles.ps1）。
# 6:00 の dailyMotorUsage.ps1 と同じ作業ツリーを使うため、時刻をずらしている。
#
# 方針（dailyMotorUsage.ps1 と同じ形）:
#   - 失敗してもPCの他作業を止めない。全例外はログに残して非0で静かに終了する。
#   - main 以外・作業ツリーが汚れている場合は何もせず退避（exit 3）。
#   - 取得と解析は C:\Users\USER\bfiles の Python で行う（mbrace は Actions から遮断のためローカル専用）。
#     fetchBDaily.py -> parseBfiles.py -> buildRankHistoryDaily.py の順。
#   - 生成物はいったん一時ファイルに書き、「生成」欄を除いて HEAD と比べる。
#     選手データが同じなら作業ツリーに一切書かない。違うときだけ差し替えて commit & push する。
#   - -NoPush を付けると、比べるところまでで止める（作業ツリーには書かない）。手動の試運転用。
param([switch]$NoPush)

$ErrorActionPreference = 'Stop'

# BOATRACE_LOCAL_REPO は検証用の上書き（本番のタスクでは未設定）。
$Repo = if ($env:BOATRACE_LOCAL_REPO) { $env:BOATRACE_LOCAL_REPO } else { 'C:\Users\USER\boatrace' }
$BDir = 'C:\Users\USER\bfiles'
# 絶対パス固定: タスクスケジューラのPATHは対話シェルと異なる。
$Py  = 'C:\Users\USER\AppData\Local\Python\pythoncore-3.14-64\python.exe'
$Git = 'C:\Program Files\Git\cmd\git.exe'
$Ps    = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"  # 破壊防止ガード呼び出し用
$Guard = Join-Path $Repo 'scripts\checkRepoGuard.ps1'                     # ガード本体（pull前後で呼ぶ）

$LogDir   = Join-Path $Repo 'scripts\logs'
$LogFile  = Join-Path $LogDir ("dailyBfiles_{0}.log" -f (Get-Date -Format 'yyyyMMdd'))
$LockFile = Join-Path $LogDir '.dailyBfiles.lock'
$Target   = 'docs/data/rankHistory.json'
$TmpOut   = Join-Path $env:TEMP 'rankHistoryDaily.json'

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }

function Log($msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
    Add-Content -Path $LogFile -Value $line -Encoding utf8
}

# ネイティブコマンドの実行と出力捕捉（dailyMotorUsage.ps1 と同じ）。
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
    # Python の UTF-8 出力をログで文字化けさせない（コンソールが無い環境では失敗するので握りつぶす）
    try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
    Log ("=== 開始 === NoPush={0}" -f [bool]$NoPush)

    # --- 安全確認: ユーザーの作業に触らない -----------------------------
    $branch = & $Git rev-parse --abbrev-ref HEAD
    if ($branch -ne 'main') {
        Log ("[退避] 理由=main 以外のブランチ '{0}'（ユーザー作業の巻き込み回避）。何もせず終了" -f $branch)
        exit 3
    }
    $dirty = & $Git status --porcelain --untracked-files=no
    if ($dirty) {
        Log ("[退避] 理由=作業ツリーに未コミット変更（ユーザー作業の巻き込み回避）。何もせず終了:`n{0}" -f ($dirty | Out-String).TrimEnd())
        exit 3
    }

    # --- 最新originへ同期（ガード1 → pull → ガード2） ---------------------
    Invoke-Step 'ガード1(remote検証)' { & $Ps -NoProfile -ExecutionPolicy Bypass -File $Guard -Stage pre -Repo $Repo -LogFile $LogFile -Git $Git } | Out-Null
    try {
        Invoke-Step 'git pull --rebase (開始時同期)' { & $Git pull --rebase origin main } | Out-Null
    } catch {
        Invoke-Native { & $Git rebase --abort } | Out-Null
        throw "開始時 git pull --rebase が衝突。中止した（手動確認が必要）"
    }
    Invoke-Step 'ガード2(worktree健全性)' { & $Ps -NoProfile -ExecutionPolicy Bypass -File $Guard -Stage post -Repo $Repo -LogFile $LogFile } | Out-Null

    # --- 1) Bファイル差分取得 --------------------------------------------
    # 取得できない日があっても解析は続ける（その日は次回以降に取り直す）
    $fetchOut = Invoke-Native { & $Py (Join-Path $BDir 'fetchBDaily.py') }
    Log ("fetchBDaily.py:`n{0}" -f $fetchOut.TrimEnd())
    if ($LASTEXITCODE -ne 0) { Log "※ 取得できない日があった（次回に取り直す。解析は続ける）" }

    # --- 2) 全ファイルの解析 ----------------------------------------------
    Invoke-Step 'parseBfiles.py' { & $Py (Join-Path $BDir 'parseBfiles.py') } | Out-Null
    $stat = Get-Content (Join-Path $BDir 'parseStat.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    Log ("parseStat: files={0} parsed={1} failed={2} racers={3}" -f $stat.files, $stat.parsed, $stat.failed, $stat.racers)
    if ($stat.failed -ne 0) { Log "※ 読めないファイルがある（その日を飛ばして履歴を作る）" }

    # --- 3) 現役分の書き出し（一時ファイル） ------------------------------
    if (Test-Path $TmpOut) { Remove-Item $TmpOut -Force }
    Invoke-Step 'buildRankHistoryDaily.py' { & $Py (Join-Path $BDir 'buildRankHistoryDaily.py') $TmpOut } | Out-Null

    # --- 4) 「生成」欄を除いて HEAD と比べる ------------------------------
    # 標準入力に渡すため ASCII だけで書く（PS 5.1 はパイプを ASCII で渡す）。キーは \u エスケープ
    $verdict = (@'
import json, subprocess, sys
git, target, tmp = sys.argv[1], sys.argv[2], sys.argv[3]
GEN, RACERS, SPAN = "\u751f\u6210", "\u9078\u624b", "\u671f\u9593"
new = json.load(open(tmp, encoding="utf-8"))
try:
    old = json.loads(subprocess.run([git, "show", "HEAD:" + target], capture_output=True, check=True).stdout.decode("utf-8"))
except Exception:
    print("CHANGED not in HEAD"); sys.exit(0)
old.pop(GEN, None)
new.pop(GEN, None)
if old == new:
    print("SAME")
else:
    o, n = old.get(RACERS, {}), new.get(RACERS, {})
    diff = sorted(t for t in set(o) | set(n) if o.get(t) != n.get(t))
    print("CHANGED racers {0} / span {1} -> {2} / e.g. {3}".format(len(diff), ascii(old.get(SPAN)), ascii(new.get(SPAN)), " ".join(diff[:10])))
'@ | & $Py - $Git $Target $TmpOut) | Select-Object -Last 1

    if ($verdict -eq 'SAME') {
        Log "rankHistory: 選手データ変更なし → 作業ツリーに書かず正常終了"
        exit 0
    }
    if (-not ($verdict -like 'CHANGED*')) { throw ("比較に失敗: {0}" -f $verdict) }
    Log ("rankHistory: {0}" -f $verdict)

    if ($NoPush) {
        Log "NoPush のため作業ツリーへの書き込み・commit はしない。正常終了"
        exit 0
    }

    # --- 5) 差し替えてコミット -------------------------------------------
    Copy-Item $TmpOut (Join-Path $Repo $Target) -Force
    Invoke-Step 'git add' { & $Git add $Target } | Out-Null
    Invoke-Step 'git commit' { & $Git commit -m 'auto: daily B更新 (docs/data/rankHistory.json)' } | Out-Null

    # --- 6) 他の自動処理と衝突しないよう rebase してから push -----------
    try {
        Invoke-Step 'git pull --rebase' { & $Git pull --rebase origin main } | Out-Null
    } catch {
        Invoke-Native { & $Git rebase --abort } | Out-Null
        throw "git pull --rebase が衝突。rebase を中止した（ローカルのコミットは残存。手動確認が必要）"
    }
    Invoke-Step 'git push' { & $Git push origin main } | Out-Null

    Log ("=== 完了: {0} を push（{1}）===" -f (& $Git rev-parse --short HEAD), $Target)
    exit 0
}
catch {
    Log ("ERROR: {0}" -f $_.Exception.Message)
    Log "※ 失敗のまま終了。次回実行で再試行される"
    exit 1
}
finally {
    Remove-Item $LockFile -Force -ErrorAction SilentlyContinue
    Remove-Item $TmpOut -Force -ErrorAction SilentlyContinue
    # ログは30日で剪定（無限に溜めない）
    Get-ChildItem $LogDir -Filter 'dailyBfiles_*.log' -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } |
        Remove-Item -Force -ErrorAction SilentlyContinue
}
