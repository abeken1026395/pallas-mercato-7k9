# updateKimariteLocal.ps1
# 決まり手CSV（docs/players/racerKimarite.csv）をローカルPCで更新する。
#   scrapeKimarite.py（mbrace Kファイル・直近183日集計）→ 検証 → 配置 → commit&push
# Windowsタスクスケジューラから毎月2日・16日に実行される想定（登録: scripts/registerUpdateKimariteLocal.ps1）。
#
# なぜローカルなのか:
#   mbrace(www1.mbrace.or.jp) は GitHub Actions のランナーIPから遮断されている。
#   updateKimarite.yml は 2026-07-16 実行分から失敗し続けていたため、正規経路をここへ移した。
#   Actions 側は workflow_dispatch のみ残してある（lhasa が入るLinuxでは動くため非常口として温存）。
#
# 方針（dailyMotorUsage.ps1 と同じ型）:
#   - 失敗してもPCの他作業を止めない。全例外はログに残して非0で静かに終了する。
#   - ユーザーの作業を巻き込まない。main以外・作業ツリーが汚れている場合は何もせず退避。
#   - 破壊防止ガードを pull 前後で呼ぶ。
#
# ★安全装置（このラッパー固有・重要）:
#   scrapeKimarite.py:280 は「CSVを書いてから :293 で races==0 を判定する」作りになっており、
#   全日取得に失敗すると既存の racerKimarite.csv をヘッダ1行だけで上書きしてから異常終了する。
#   本体は直さない方針のため、ラッパー側で以下を担保する:
#     (a) scrapeKimarite.py の出力先は必ず作業用一時ディレクトリ。docs/ には直接書かせない。
#     (b) 配置前に4項目を検証し、通ったものだけを docs/ へコピーする。
#     (c) 検証に落ちたら配置しない・既存ファイルはそのまま・ERRORを残して非0終了。
#   ＝ build_highlights.py:946-949 の「検証してから書く（既存を壊さず非ゼロ終了）」と同じ型。

$ErrorActionPreference = 'Stop'

$Repo = 'C:\Users\USER\boatrace'
# 絶対パス固定: タスクスケジューラのPATHは対話シェルと異なる。
# py.exe は WindowsApps のアプリ実行エイリアスで非対話だと不安定なため実体を直に指す。
$Py    = 'C:\Users\USER\AppData\Local\Python\pythoncore-3.14-64\python.exe'
$Git   = 'C:\Program Files\Git\cmd\git.exe'
$Ps    = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"  # 破壊防止ガード呼び出し用
$Guard = 'C:\Users\USER\boatrace\scripts\checkRepoGuard.ps1'               # ガード本体（pull前後で呼ぶ）

$Days   = '183'   # scrapeKimarite.py の既定と同じ集計窓
$Sleep  = '1.0'   # 公式サーバ負荷軽減。既定と同じ
$Target = 'docs/players/racerKimarite.csv'

$LogDir   = Join-Path $Repo 'scripts\logs'
$LogFile  = Join-Path $LogDir ("updateKimarite_{0}.log" -f (Get-Date -Format 'yyyyMMdd'))
$LockFile = Join-Path $LogDir '.updateKimarite.lock'

# 生成物の一時置き場。docs/ に直接書かせないための隔離先。
$WorkDir = Join-Path $env:TEMP 'boatrace-kimarite'
$NewCsv  = Join-Path $WorkDir 'racerKimarite.new.csv'

# --- 検証しきい値 --------------------------------------------------------
$MinDataRows  = 10     # データ行数がこれ未満＝ヘッダのみ相当とみなす
$MinRatioPrev = 0.5    # 既存行数に対しこの比率を下回ったら異常（集計窓の前進による多少の増減は正常）
$MinFetchRate = 0.90   # 取得率がこれ未満なら異常。90〜99%は配置するがWARNを出す

# --- 最終行に出すサマリ（異常時も必ず出す） ------------------------------
$script:Placed      = '未実施'
$script:FetchedInfo = '-'
$script:DataRows    = '-'
$script:Delta       = '-'

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }

function Log($msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
    Add-Content -Path $LogFile -Value $line -Encoding utf8
}

# ネイティブコマンドの実行と出力捕捉。
# PS5.1 では native の stderr を 2>&1 すると各行が ErrorRecord に化け、
# ErrorActionPreference='Stop' 下では exit 0 でも終了エラーになる。
# そのため捕捉中だけ Continue に落とし、成否は $LASTEXITCODE だけで判定する。
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

# CSVの形（ヘッダ・列数・データ行数）を返す。無ければ $null。
function Get-CsvShape([string]$path) {
    if (-not (Test-Path $path)) { return $null }
    $lines = @([IO.File]::ReadAllLines($path, [Text.Encoding]::UTF8) |
               Where-Object { $_.Trim() -ne '' })
    if ($lines.Count -eq 0) { return $null }
    return [pscustomobject]@{
        Header   = $lines[0]
        Cols     = ($lines[0] -split ',').Count
        DataRows = $lines.Count - 1
    }
}

# --- 同時実行防止 --------------------------------------------------------
# タスク側でも MultipleInstances=IgnoreNew を設定済み。手動実行との二重起動もここで防ぐ。
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
        $script:Placed = 'なし(main以外)'
        exit 0
    }
    $dirty = & $Git status --porcelain --untracked-files=no
    if ($dirty) {
        Log ("追跡ファイルに未コミット変更があるため何もせず終了:`n{0}" -f ($dirty | Out-String).TrimEnd())
        $script:Placed = 'なし(作業ツリーが汚れている)'
        exit 0
    }

    # --- 0.5) 最新originへ同期 -------------------------------------------
    # 破壊防止ガード1（pull前）: remoteが想定リポか検証。旧URL(空リポ)なら非0で中断。
    Invoke-Step 'ガード1(remote検証)' { & $Ps -NoProfile -ExecutionPolicy Bypass -File $Guard -Stage pre -Repo $Repo -LogFile $LogFile -Git $Git } | Out-Null
    try {
        Invoke-Step 'git pull --rebase (開始時同期)' { & $Git pull --rebase origin main } | Out-Null
    } catch {
        Invoke-Native { & $Git rebase --abort } | Out-Null
        throw "開始時 git pull --rebase が衝突。中止した（手動確認が必要）"
    }
    # 破壊防止ガード2（pull直後）: 必須ファイル消失＝作業ツリー破壊なら非0で中断（自動復旧しない）。
    Invoke-Step 'ガード2(worktree健全性)' { & $Ps -NoProfile -ExecutionPolicy Bypass -File $Guard -Stage post -Repo $Repo -LogFile $LogFile } | Out-Null

    # --- 1) 収集（出力先は一時ディレクトリ。docs/ には書かせない） -------
    if (Test-Path $WorkDir) { Remove-Item $WorkDir -Recurse -Force -ErrorAction SilentlyContinue }
    New-Item -ItemType Directory -Path $WorkDir -Force | Out-Null

    $prev = Get-CsvShape (Join-Path $Repo $Target)
    if ($prev) {
        Log ("既存CSV: データ行数={0} 列数={1}" -f $prev.DataRows, $prev.Cols)
    } else {
        Log "既存CSV: 無し（初回扱い。行数比較はスキップする）"
    }

    $env:KIMARITE_DAYS  = $Days
    $env:KIMARITE_SLEEP = $Sleep
    $env:KIMARITE_OUT   = $NewCsv
    Log ("scrapeKimarite.py 開始（DAYS={0} SLEEP={1} OUT={2}）" -f $Days, $Sleep, $NewCsv)
    $t0 = Get-Date
    # 取得失敗日があっても集計は続く（欠けた日は欠いたまま＝補完しない方針）。
    # 全滅時は本体が非0で落ちるが、その場合でも壊れるのは $NewCsv であって docs/ ではない。
    # PS5.1 はネイティブ出力を [Console]::OutputEncoding で復号する。タスクスケジューラ
    # 実行時の既定は OEM(cp932) のため、PYTHONIOENCODING=utf-8 の出力が文字化けし
    # (検証4) の正規表現が外れる。この呼び出しの間だけ読み取りを UTF-8 に合わせる。
    $savedEnc = [Console]::OutputEncoding
    [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
    try   { $scrapeOut = Invoke-Native { & $Py scripts\scrapeKimarite.py } }
    finally { [Console]::OutputEncoding = $savedEnc }
    $scrapeRc  = $LASTEXITCODE
    $elapsed   = [int]((Get-Date) - $t0).TotalSeconds
    Log ("scrapeKimarite.py 終了 rc={0} 所要={1}秒:`n{2}" -f $scrapeRc, $elapsed, $scrapeOut.TrimEnd())

    if ($scrapeRc -ne 0) {
        throw ("scrapeKimarite.py が非0終了 (exit {0})。配置しない（既存CSVは不変）" -f $scrapeRc)
    }

    # --- 2) 配置前の検証（4項目）----------------------------------------
    # (検証1) 生成物が在るか
    if (-not (Test-Path $NewCsv)) {
        throw "生成物が無い: $NewCsv。配置しない（既存CSVは不変）"
    }
    $new = Get-CsvShape $NewCsv
    if (-not $new) {
        throw "生成物が空: $NewCsv。配置しない（既存CSVは不変）"
    }
    $script:DataRows = $new.DataRows

    # (検証2) ヘッダのみを弾く（データ行数が2桁以上あること）
    if ($new.DataRows -lt $MinDataRows) {
        throw ("検証NG: データ行数 {0} が下限 {1} 未満（ヘッダのみ相当）。配置しない（既存CSVは不変）" -f $new.DataRows, $MinDataRows)
    }

    # (検証3) 列構成が既存と一致すること
    if ($prev) {
        if ($new.Cols -ne $prev.Cols) {
            throw ("検証NG: 列数が不一致 新={0} 既存={1}。配置しない（既存CSVは不変）" -f $new.Cols, $prev.Cols)
        }
        if ($new.Header -ne $prev.Header) {
            Log ("検証NG詳細: 新ヘッダ={0}" -f $new.Header)
            Log ("検証NG詳細: 既存ヘッダ={0}" -f $prev.Header)
            throw "検証NG: ヘッダ（列名）が既存と一致しない。配置しない（既存CSVは不変）"
        }
        # (検証3b) 極端な減少を弾く（集計窓の前進による多少の増減は正常）
        $floor = [int][Math]::Floor($prev.DataRows * $MinRatioPrev)
        if ($new.DataRows -lt $floor) {
            throw ("検証NG: データ行数が激減 新={0} 既存={1} 下限={2}（既存の{3}倍）。配置しない（既存CSVは不変）" -f $new.DataRows, $prev.DataRows, $floor, $MinRatioPrev)
        }
        $script:Delta = "{0:+#;-#;0}" -f ($new.DataRows - $prev.DataRows)
    } else {
        $script:Delta = 'n/a(初回)'
    }

    # (検証4) 取得日数（部分的失敗の検知）
    # 行数チェックは全滅を捕まえるが部分失敗をすり抜ける。
    # 183日中100日失敗しても選手数は半分を超えるため、劣化CSVが静かに配置されてしまう。
    $okDays  = $null
    $reqDays = $null
    $m = [regex]::Match($scrapeOut, '取得できた日数\s*[:：]\s*(\d+)\s*/\s*(\d+)')
    if ($m.Success) {
        $okDays  = [int]$m.Groups[1].Value
        $reqDays = [int]$m.Groups[2].Value
    }
    if ($null -eq $okDays -or $reqDays -le 0) {
        throw "検証NG: サマリから取得日数を抽出できなかった。配置しない（既存CSVは不変）"
    }
    $rate = $okDays / $reqDays
    $missed = $reqDays - $okDays
    $script:FetchedInfo = "{0}/{1}({2:P1})" -f $okDays, $reqDays, $rate

    if ($rate -lt $MinFetchRate) {
        throw ("検証NG: 取得率 {0:P1}（{1}/{2}・欠測{3}日）が下限 {4:P0} 未満。配置しない（既存CSVは不変）" -f $rate, $okDays, $reqDays, $missed, $MinFetchRate)
    }
    if ($okDays -lt $reqDays) {
        Log ("WARN: 取得率 {0:P1}（{1}/{2}）。取得できなかった日数 = {3}日。欠けたまま配置する（補完・推測はしない）" -f $rate, $okDays, $reqDays, $missed)
    }

    Log ("検証OK: データ行数={0} 列数={1} 取得日数={2}" -f $new.DataRows, $new.Cols, $script:FetchedInfo)

    # --- 3) 配置（検証を通ったものだけ docs/ へ）-------------------------
    Copy-Item -Path $NewCsv -Destination (Join-Path $Repo $Target) -Force
    $script:Placed = 'あり'
    Log ("配置: {0} → {1}" -f $NewCsv, $Target)

    # --- 4) 変更判定 -----------------------------------------------------
    $dirtyTarget = & $Git status --porcelain $Target
    if (-not $dirtyTarget) {
        Log "内容に変更なし。コミットせず正常終了"
        $script:Placed = 'あり(差分なし)'
        exit 0
    }

    # --- 5) コミット -----------------------------------------------------
    Invoke-Step 'git add' { & $Git add $Target } | Out-Null
    $msg = 'auto: update kimarite (racerKimarite.csv)'
    Invoke-Step 'git commit' { & $Git commit -m $msg } | Out-Null

    # --- 6) 他の自動処理と衝突しないよう rebase してから push -----------
    try {
        Invoke-Step 'git pull --rebase' { & $Git pull --rebase origin main } | Out-Null
    } catch {
        # 衝突を放置するとリポジトリがrebase途中で固まりユーザー作業を壊す
        Invoke-Native { & $Git rebase --abort } | Out-Null
        throw "git pull --rebase が衝突。rebase を中止した（ローカルのコミットは残存。手動確認が必要）"
    }
    Invoke-Step 'git push' { & $Git push origin main } | Out-Null

    Log ("=== 完了: {0} を push ===" -f (& $Git rev-parse --short HEAD))
    exit 0
}
catch {
    Log ("ERROR: {0}" -f $_.Exception.Message)
    Log "※ 失敗のまま終了。既存CSVは変更していない。次回実行で再試行される"
    if ($script:Placed -eq '未実施') { $script:Placed = 'なし(検証NG)' }
    exit 1
}
finally {
    # 異常時も必ず最終行に出す。ログを開いた人間が1行で状況を掴めるようにする。
    Log ("[RESULT] 配置={0} / 取得日数={1} / データ行数={2} / 前回からの増減={3}" -f `
         $script:Placed, $script:FetchedInfo, $script:DataRows, $script:Delta)

    Remove-Item $LockFile -Force -ErrorAction SilentlyContinue
    Remove-Item $WorkDir -Recurse -Force -ErrorAction SilentlyContinue
    # ログは30日で剪定（無限に溜めない）
    Get-ChildItem $LogDir -Filter 'updateKimarite_*.log' -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } |
        Remove-Item -Force -ErrorAction SilentlyContinue
}
