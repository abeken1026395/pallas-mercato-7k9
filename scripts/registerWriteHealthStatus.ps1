# registerWriteHealthStatus.ps1
# writeHealthStatusLocal.ps1 を「毎日 JST 8:00 / 14:00 / 22:00」に走らせるタスクを登録する。
# 再実行で上書き更新。
#
# ログオン種別は registerWriteKansenkiLocal.ps1 と同じ理由で Interactive / Limited。
# git push は Git Credential Manager の資格情報（ユーザーDPAPI保護）を使うため、
# "ユーザーがログオンしていなくても実行" にすると push が失敗しうる。
#
# 本体は C:\Users\USER\healthStatus\ にコピーしてから登録する（2026-11-19）。
# 作業フォルダが別ブランチにあっても、ブランチに触らない新しい本体が動くようにするため。
# 本体を更新したら、このスクリプトをもう一度実行する。

$ErrorActionPreference = 'Stop'

$TaskName = 'boatrace-writeHealthStatus'
$Home2    = 'C:\Users\USER\healthStatus'
$Src      = Join-Path $PSScriptRoot 'writeHealthStatusLocal.ps1'
$Script   = Join-Path $Home2 'writeHealthStatusLocal.ps1'
$PwshExe  = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"

if (-not (Test-Path $Src)) { throw "writeHealthStatusLocal.ps1 が見つからない: $Src" }
if (-not (Test-Path $Home2)) { New-Item -ItemType Directory -Path $Home2 -Force | Out-Null }
Copy-Item -Path $Src -Destination $Script -Force

# 窓を出さない（2026-10-24 から PC のタスクは conhost --headless で起動している。claude/registerHeadless.md）
$ConhostExe = "$env:SystemRoot\System32\conhost.exe"
$action = New-ScheduledTaskAction -Execute $ConhostExe `
    -Argument ('--headless "{0}" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{1}"' -f $PwshExe, $Script)

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
