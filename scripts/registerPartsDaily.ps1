# registerPartsDaily.ps1
# fetchPartsDaily.py（前日分の部品交換を PC から取り、data/partsDaily/<開催日>.json を GitHub に置く）を
# 毎日 JST 07:10 と 13:10 に走らせるタスク boatrace-partsDaily を登録する。再実行で上書き更新。
#   07:10 が本命。13:10 は取り逃し（PC の起動遅れ・一時的な失敗）の回収。既に置いてあれば何もしない。
#   公式が前日分を返すのは翌日いっぱいなので、2回とも外れた日は欠ける（翌日の昼に統括が照合する）。
# 2026-11-22 けん裁定（公式が GitHub Actions からの直前情報を 403 で拒否しているため、取得を PC に移す）。
# ログオン種別は registerPartsBackfill.ps1 と同じ理由で Interactive / Limited（gh の資格情報を使うため）。
# 窓は出さない（-WindowStyle Hidden）。

$ErrorActionPreference = 'Stop'

$TaskName = 'boatrace-partsDaily'
$Script   = 'C:\Users\USER\partsDaily\fetchPartsDaily.py'
$PwshExe  = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"

if (-not (Test-Path $Script)) { throw "fetchPartsDaily.py が見つからない: $Script" }

$action = New-ScheduledTaskAction -Execute $PwshExe `
    -Argument ('-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -Command "python ''{0}''"' -f $Script) `
    -WorkingDirectory 'C:\Users\USER\partsDaily'

$trigger = @(
    (New-ScheduledTaskTrigger -Daily -At '07:10'),
    (New-ScheduledTaskTrigger -Daily -At '13:10')
)

$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -WakeToRun `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 90)

$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Force | Out-Null

Get-ScheduledTask -TaskName $TaskName | Select-Object TaskName, State
