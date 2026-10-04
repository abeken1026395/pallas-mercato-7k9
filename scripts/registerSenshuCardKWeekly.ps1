# registerSenshuCardKWeekly.ps1
# senshuCardKWeekly.ps1 を「毎週月曜 6:40」に走らせるタスクを登録する。再実行すれば上書き更新する。
# ログオン種別は registerDailyMotorUsage.ps1 と同じ（push の資格情報のため対話ログオン）。

$ErrorActionPreference = 'Stop'

$TaskName = 'boatrace-senshuCardKWeekly'
$Script   = 'C:\Users\USER\boatrace\scripts\senshuCardKWeekly.ps1'
$PwshExe  = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"

$action = New-ScheduledTaskAction -Execute $PwshExe `
    -Argument ('-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{0}"' -f $Script)

$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At '06:40'

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
    -Description '選手カード：mbrace Kファイル → data/senshuCard/kExtra.csv に追記 → 変更があればcommit&push' `
    -Force | Out-Null

"登録しました: $TaskName"
Get-ScheduledTask -TaskName $TaskName |
    Select-Object TaskName, State, @{n='Trigger';e={ $_.Triggers[0].StartBoundary }}
