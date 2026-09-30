# registerDispatchNightly.ps1
# dispatchNightly.ps1 を毎日 18:05 / 20:05 / 22:05 に走らせるタスクを登録する。再実行で上書き更新。
#
# 本体は C:\Users\USER\dispatchNightly\ にコピーしてから登録する（codeWatcher と同じ理由：
# リポジトリの作業ツリーが別ブランチにあってもタスクが消えないようにする）。本体を更新したら再実行する。
#
# ログオン種別は Interactive / Limited（Git Credential Manager の認証がユーザープロファイル配下にあるため）。
# WakeToRun と StartWhenAvailable を付ける（寝ていても起こす・逃した回は起動後に走らせる）。
# 文字コード: このファイルは UTF-8 BOM 付きで保存すること。

$ErrorActionPreference = 'Stop'

$TaskName = 'boatrace-dispatchNightly'
$Home2    = 'C:\Users\USER\dispatchNightly'
$Src      = Join-Path $PSScriptRoot 'dispatchNightly.ps1'
$Script   = Join-Path $Home2 'dispatchNightly.ps1'
$PwshExe  = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"

if (-not (Test-Path $Src)) { throw "dispatchNightly.ps1 が見つからない: $Src" }
if (-not (Test-Path $Home2)) { New-Item -ItemType Directory -Path $Home2 -Force | Out-Null }
Copy-Item -Path $Src -Destination $Script -Force

$action = New-ScheduledTaskAction -Execute $PwshExe `
    -Argument ('-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}"' -f $Script)

$triggers = @(
    (New-ScheduledTaskTrigger -Daily -At '18:05'),
    (New-ScheduledTaskTrigger -Daily -At '20:05'),
    (New-ScheduledTaskTrigger -Daily -At '22:05')
)

$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -WakeToRun `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $triggers `
    -Settings $settings -Principal $principal `
    -Description '翌日の見どころを18時台に出すため、nightlyPipeline を GitHub に起動させる（18:05 / 20:05 / 22:05）' `
    -Force | Out-Null

"登録しました: $TaskName（本体 $Script）"
Get-ScheduledTask -TaskName $TaskName | Select-Object TaskName, State
