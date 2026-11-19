# writeHealthStatusLocal.ps1
# health/status.json を生成して push する（1日3回・タスクスケジューラから実行）。
#
# なぜローカルで動かすか:
#   Actions が詰まると Actions 側の警報も一緒に詰まる。2026-08-07 に、cron 07:37 の
#   観戦記警報が 10:37 に起票された（3時間遅延）。監視は監視対象と別の場所で回す。
#
# 作業フォルダのブランチ・作業ツリー・インデックスには一切触らない（2026-11-19 けん裁定 A）。
#   以前は今いるブランチの上でコミットして origin/main に付け替え、HEAD を main に push していたため、
#   作業ブランチの未検収コミットが main に入った（11-14 14:00・11-19 08:00）。
#   今は status.json を一時ファイルに書き、origin/main の上に status.json だけを替えた
#   コミットを一時インデックスで作って、そのコミットを main に push する。
#
# 出力先 health/ は docs/ の外。Pages のデプロイを起動させないため。
# 文字コード: このファイルは UTF-8 BOM 付きで保存すること（BOM無しだと PS5.1 が cp932 と誤解釈する）。

$ErrorActionPreference = 'Continue'   # git は stderr に通常出力を出す。成否は $LASTEXITCODE で見る。

$Repo = 'C:\Users\USER\boatrace'
$Py   = 'C:\Users\USER\AppData\Local\Python\pythoncore-3.14-64\python.exe'
$Git  = 'C:\Program Files\Git\cmd\git.exe'
$Path = 'health/status.json'
$Out  = Join-Path $env:TEMP 'boatraceHealthStatus.json'
$Idx  = Join-Path $env:TEMP 'boatraceHealthIndex'

Set-Location $Repo

& $Git fetch origin main | Out-Null

# 生成スクリプトも作業フォルダのブランチの版ではなく origin/main の版を一時フォルダへ取り出して動かす。
$PyTmp = Join-Path $env:TEMP 'boatraceHealthStatus.py'
if (Test-Path $PyTmp) { Remove-Item $PyTmp -Force }
& $Py -c "import subprocess,sys;open(sys.argv[1],'wb').write(subprocess.run(['git','show','origin/main:scripts/writeHealthStatus.py'],capture_output=True,check=True).stdout)" $PyTmp
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $PyTmp)) {
    Write-Output "origin/main から writeHealthStatus.py を取り出せない"
    exit 1
}

if (Test-Path $Out) { Remove-Item $Out -Force }
$env:HEALTH_OUT  = $Out
$env:HEALTH_ROOT = $Repo
& $Py $PyTmp
$rc = $LASTEXITCODE
Remove-Item Env:HEALTH_OUT -ErrorAction SilentlyContinue
Remove-Item Env:HEALTH_ROOT -ErrorAction SilentlyContinue
if ($rc -ne 0 -or -not (Test-Path $Out)) {
    Write-Output "writeHealthStatus.py が失敗 (exit $rc)"
    exit 1
}

$blob = (& $Git hash-object -w --no-filters $Out | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or -not $blob) {
    Write-Output "hash-object が失敗"
    exit 1
}
$msg = "health: status.json 更新 {0}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm')

# push競合(non-fast-forward / cannot lock ref)は、取り直した origin/main の上で作り直してリトライする。
for ($i = 1; $i -le 6; $i++) {
    & $Git fetch origin main | Out-Null
    $base = (& $Git rev-parse origin/main | Out-String).Trim()
    $old  = (& $Git rev-parse ("{0}:{1}" -f $base, $Path) 2>$null | Out-String).Trim()
    if ($old -eq $blob) {
        Write-Output "no changes"
        exit 0
    }

    if (Test-Path $Idx) { Remove-Item $Idx -Force }
    $env:GIT_INDEX_FILE = $Idx
    & $Git read-tree $base | Out-Null
    $ok = ($LASTEXITCODE -eq 0)
    if ($ok) {
        & $Git update-index --add --cacheinfo ("100644,{0},{1}" -f $blob, $Path) | Out-Null
        $ok = ($LASTEXITCODE -eq 0)
    }
    $tree = ''
    if ($ok) {
        $tree = (& $Git write-tree | Out-String).Trim()
        $ok = ($LASTEXITCODE -eq 0 -and $tree)
    }
    Remove-Item Env:GIT_INDEX_FILE -ErrorAction SilentlyContinue
    if (Test-Path $Idx) { Remove-Item $Idx -Force }
    if (-not $ok) {
        Write-Output "一時インデックスでの組み立てが失敗 (try $i)"
        exit 1
    }

    $commit = (& $Git commit-tree $tree -p $base -m $msg | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $commit) {
        Write-Output "commit-tree が失敗 (try $i)"
        exit 1
    }

    & $Git push origin ("{0}:refs/heads/main" -f $commit) | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Output "pushed $commit (try $i)"
        exit 0
    }
    Start-Sleep -Seconds (Get-Random -Minimum 3 -Maximum 9)
}

Write-Output "push retries exhausted"
exit 1
