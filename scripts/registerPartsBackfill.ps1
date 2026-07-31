# registerPartsBackfill.ps1
# dailyPartsBackfill.ps1 を「毎日 JST 18:30」に走らせるタスクを登録する。
# 再実行すれば設定を上書き更新する。
#
# なぜ 18:30 か:
#   beforeinfo収集(Actions)のコミット着地実績 … 07/29 17:12 / 07/30 17:03 / 07/31 17:18
#   cron は JST 6:07/10:07/14:07 だが、GitHubのスケジュール遅延で実際は1.5〜3.8時間遅れる。
#   実績の最遅 17:18 に約1時間の余裕を足して 18:30 とする。
#   これより早いと当日ぶんを取りこぼすが、その場合も翌 06:00 の
#   dailyMotorUsage.ps1 側 backfill が保険として拾う（二段構え）。
#
# ログオン種別について（dailyMotorUsage と同じ理由で Interactive）:
#   push は Git Credential Manager が Windows資格情報マネージャーに持つ資格情報を使う。
#   これはユーザーのDPAPIで保護されているため、"ユーザーがログオンしていなくても実行する" にすると
#   資格情報を復号できず push が失敗しうる。そのため -RunLevel Limited かつ対話ログオンで登録し、
#   スリープからの起復は WakeToRun で担保する。

$ErrorActionPreference = 'Stop'

$TaskName = 'boatrace-dailyPartsBackfill'
$Script   = 'C:\Users\USER\boatrace\scripts\dailyPartsBackfill.ps1'
$PwshExe  = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"

$action = New-ScheduledTaskAction -Execute $PwshExe `
    -Argument ('-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{0}"' -f $Script)

$trigger = New-ScheduledTaskTrigger -Daily -At '18:30'

$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -WakeToRun `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal `
    -Description 'motorParts.json モーターNo空欄をKから補填 → 補填があればcommit&push（beforeinfo着地後の18:30。翌6:00のdailyMotorUsageが保険）' `
    -Force | Out-Null

"登録しました: $TaskName"
Get-ScheduledTask -TaskName $TaskName |
    Select-Object TaskName, State, @{n='Trigger';e={ $_.Triggers[0].StartBoundary }}
