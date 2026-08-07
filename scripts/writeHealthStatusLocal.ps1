# writeHealthStatusLocal.ps1
# health/status.json を生成して push する（1日3回・タスクスケジューラから実行）。
#
# なぜローカルで動かすか:
#   Actions が詰まると Actions 側の警報も一緒に詰まる。2026-08-07 に、cron 07:37 の
#   観戦記警報が 10:37 に起票された（3時間遅延）。監視は監視対象と別の場所で回す。
#
# 出力先 health/ は docs/ の外。Pages のデプロイを起動させないため。
# 文字コード: このファイルは UTF-8 BOM 付きで保存すること（BOM無しだと PS5.1 が cp932 と誤解釈する）。

$ErrorActionPreference = 'Continue'   # git は stderr に通常出力を出す。成否は $LASTEXITCODE で見る。

$Repo = 'C:\Users\USER\boatrace'
$Py   = 'C:\Users\USER\AppData\Local\Python\pythoncore-3.14-64\python.exe'
$Git  = 'C:\Program Files\Git\cmd\git.exe'

Set-Location $Repo

& $Git fetch origin main | Out-Null

& $Py scripts\writeHealthStatus.py
if ($LASTEXITCODE -ne 0) {
    Write-Output "writeHealthStatus.py が失敗 (exit $LASTEXITCODE)"
    exit 1
}

& $Git add health/status.json
& $Git diff --staged --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Output "no changes"
    exit 0
}

& $Git commit -m ("health: status.json 更新 {0}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm')) | Out-Null

# push競合(cannot lock ref)は短いランダム待機でリトライする。
for ($i = 1; $i -le 6; $i++) {
    & $Git fetch origin main | Out-Null
    & $Git rebase -X theirs origin/main | Out-Null
    if ($LASTEXITCODE -eq 0) {
        & $Git push origin HEAD:main | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Output "pushed (try $i)"
            exit 0
        }
    } else {
        & $Git rebase --abort 2>$null | Out-Null
    }
    Start-Sleep -Seconds (Get-Random -Minimum 3 -Maximum 9)
}

Write-Output "push retries exhausted"
exit 1
