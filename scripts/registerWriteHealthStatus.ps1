# registerWriteHealthStatus.ps1
# writeHealthStatusLocal.ps1 を「毎日 JST 8:00 / 14:00 / 22:00」に走らせるタスクを登録する。
# 再実行で上書き更新。
#
# ログオン種別は registerWriteKansenkiLocal.ps1 と同じ理由で Interactive / Limited。
# git push は Git Credential Manager の資格情報（ユーザーDPAPI保護）を使うため、
# "ユーザーがログオンしていなくても実行" にすると push が失敗しうる。

$ErrorActionPreference = 'Stop'

$TaskName = 'boatrace-writeHealthStatus'
$Script   = 'C:\Users\USER\boatrace\scripts\writeHealthStatusLocal.ps1'
$PwshExe  = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"

$action = New-ScheduledTaskAction -Execute $PwshExe `
    -Argument ('-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{0}"' -f $Script)

$triggers = @(
    (New-ScheduledTaskTrigger -Daily -At '08:00'),
    (New-ScheduledTaskTrigger -Daily -At '14:00'),
    (New-ScheduledTaskTrigger -Daily -At '22:00')
)

$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -WakeToRun `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15)

$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $triggers `
    -Settings $settings -Principal $principal `
    -Description 'リポジトリの健康状態を点検して health/status.json を更新・push する（1日3回）' `
    -Force | Out-Null

"登録しました: $TaskName"
Get-ScheduledTask -TaskName $TaskName |
    Select-Object TaskName, State, @{n='Triggers';e={ ($_.Triggers | ForEach-Object { $_.StartBoundary }) -join ' / ' }}
