# registerAuthPrecheck.ps1
# authPrecheck.ps1 を毎日 17:30 に走らせるタスクを登録する。再実行で上書き更新。
# 窓を出さない起動。conhost --headless は子の終了コードを捨てるため、runHidden.vbs（wscript //B）経由にして
# 終了コードをタスクの「前回の結果」に載せる。
# ログオン種別は registerWriteKansenkiLocal.ps1 と同じ（Interactive / Limited）。
# 文字コード: このファイルは UTF-8 BOM 付きで保存すること。

$ErrorActionPreference = 'Stop'

$TaskName = 'boatrace-authPrecheck'
$Script   = Join-Path $PSScriptRoot 'authPrecheck.ps1'
$Vbs      = Join-Path $PSScriptRoot 'runHidden.vbs'
$Wscript  = "$env:SystemRoot\System32\wscript.exe"

$action = New-ScheduledTaskAction -Execute $Wscript `
    -Argument ('//B //Nologo "{0}" "{1}"' -f $Vbs, $Script)

$trigger = New-ScheduledTaskTrigger -Daily -At '17:30'

$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal `
    -Description '観戦記の claude 認証の事前チェック（毎日17:30・切れていたら Issue で知らせる）' `
    -Force | Out-Null

"登録しました: $TaskName"
Get-ScheduledTask -TaskName $TaskName | Select-Object TaskName, State
