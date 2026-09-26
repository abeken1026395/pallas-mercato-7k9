# registerCodeWatcher.ps1
# codeWatcher.ps1 を5分ごとに走らせるタスクを登録する。再実行で上書き更新。
#
# 見張り本体は C:\Users\USER\codeWatcher\ にコピーしてから登録する。
# リポジトリの作業ツリーが別ブランチにあっても見張りが消えないようにするため（racerSchedule の空振りと同じ理由）。
# 見張りを更新したら、このスクリプトをもう一度実行する。
#
# ログオン種別は registerWriteKansenkiLocal.ps1 と同じ理由で Interactive / Limited
# （claude の OAuth 認証情報と Git Credential Manager がユーザープロファイル配下にあるため）。
# WakeToRun は付けない（5分ごとにスリープを解除させない）。
# 文字コード: このファイルは UTF-8 BOM 付きで保存すること。

$ErrorActionPreference = 'Stop'

$TaskName = 'boatrace-codeWatcher'
$Home2    = 'C:\Users\USER\codeWatcher'
$Src      = Join-Path $PSScriptRoot 'codeWatcher.ps1'
$Script   = Join-Path $Home2 'codeWatcher.ps1'
$PwshExe  = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"

if (-not (Test-Path $Src)) { throw "codeWatcher.ps1 が見つからない: $Src" }
if (-not (Test-Path $Home2)) { New-Item -ItemType Directory -Path $Home2 -Force | Out-Null }
Copy-Item -Path $Src -Destination $Script -Force

$action = New-ScheduledTaskAction -Execute $PwshExe `
    -Argument ('-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}"' -f $Script)

$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 5) `
    -RepetitionDuration (New-TimeSpan -Days 3650)

$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal `
    -Description '統括チャットが codeShikyu に置いた支給物（kick.txt あり）をローカルCodeで無人実行する（5分ごと）' `
    -Force | Out-Null

"登録しました: $TaskName（本体 $Script）"
Get-ScheduledTask -TaskName $TaskName | Select-Object TaskName, State
