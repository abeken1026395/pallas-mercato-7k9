# registerDailyBfiles.ps1
# dailyBfiles.ps1 を「毎日 JST 6:40」に走らせるタスクを登録する。再実行すれば設定を上書き更新する。
# 6:00 の boatrace-dailyMotorUsage（約6分）と同じ作業ツリーを使うため、6:40 にずらしている。
#
# ログオン種別は registerDailyMotorUsage.ps1 と同じ理由で、対話ログオン・RunLevel Limited・WakeToRun。

$ErrorActionPreference = 'Stop'

$TaskName = 'boatrace-dailyBfiles'
$Script   = 'C:\Users\USER\boatrace\scripts\dailyBfiles.ps1'
$PwshExe  = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"

$action = New-ScheduledTaskAction -Execute $PwshExe `
    -Argument ('-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{0}"' -f $Script)

$trigger = New-ScheduledTaskTrigger -Daily -At '06:40'

$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -WakeToRun `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)

$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal `
    -Description 'mbrace Bファイル差分取得 → 級別の履歴を再生成 → rankHistory.json の選手データが変わった日だけ commit&push' `
    -Force | Out-Null

"登録しました: $TaskName"
Get-ScheduledTask -TaskName $TaskName |
    Select-Object TaskName, State, @{n='Trigger';e={ $_.Triggers[0].StartBoundary }}
