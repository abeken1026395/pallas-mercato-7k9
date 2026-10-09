# registerWriteKansenkiLocal.ps1
# writeKansenkiLocal.ps1 を「毎日 JST 18:40 から 23:40 まで の毎時（夕方便）と 1:00（本命）と 2:00・3:00・4:00（取り返し）」に走らせるタスクを登録する。再実行で上書き更新。
# 1:00 は 2026-09-30 けん裁定。2026-10-09 けん裁定「朝に執筆せず夜中にさせよう」で 5:30 の回をやめ、夜中の取り返しを毎時に足した。
# 取り返しの回は、それまでの回が書き終えていれば pubplan が「執筆済み」と判定して何もしない。書けなかった場・lint で
# 落ちた場・claude が起動に失敗した回の分だけを書き直す（9/16・9/27・10/08 の欠けは、取り返す回が無かったのが原因）。
# 夕方便は 2026-10-02 けん裁定（「出走表が取れた時点で執筆させて表示させたい」）。17時以降の回は翌日分を書き、
# 翌日の出走表と当日の結果がそろった場だけを書く（そろっていなければ何もせず正常終了）。
# 1:00 の回が素材待ち（最大 02:30）と執筆で長引くことがあるため、実行時間の上限を 4時間にする。
#
# ログオン種別について（registerDailyMotorUsage.ps1 と同じ理由・重要）:
#   git push は Git Credential Manager が Windows資格情報マネージャーに持つ資格情報（ユーザーDPAPI保護）を、
#   claude は Max プランの OAuth 認証情報（同じくユーザープロファイル配下）を使う。
#   "ユーザーがログオンしていなくても実行" にするとこれらを復号/参照できず push も claude も失敗しうる。
#   そのため -RunLevel Limited かつ対話ログオン（= ログオン時のみ実行）で登録する。
#   スリープからの起復は WakeToRun で担保する（完全シャットダウン/ログオフ中は動かない）。

$ErrorActionPreference = 'Stop'

$TaskName = 'boatrace-writeKansenkiLocal'
$Script   = 'C:\Users\USER\boatrace\scripts\writeKansenkiLocal.ps1'
$PwshExe  = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"

$action = New-ScheduledTaskAction -Execute $PwshExe `
    -Argument ('-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{0}"' -f $Script)

$trigger = @(
    (New-ScheduledTaskTrigger -Daily -At '18:40'),
    (New-ScheduledTaskTrigger -Daily -At '19:40'),
    (New-ScheduledTaskTrigger -Daily -At '20:40'),
    (New-ScheduledTaskTrigger -Daily -At '21:40'),
    (New-ScheduledTaskTrigger -Daily -At '22:40'),
    (New-ScheduledTaskTrigger -Daily -At '23:40'),
    (New-ScheduledTaskTrigger -Daily -At '01:00'),
    (New-ScheduledTaskTrigger -Daily -At '02:00'),
    (New-ScheduledTaskTrigger -Daily -At '03:00'),
    (New-ScheduledTaskTrigger -Daily -At '04:00')
)

$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -WakeToRun `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 4)

$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal `
    -Description '観戦記の自走をローカルで実行: source確定後、pubplanで未執筆場を判定→claude(Max/課金なし)で執筆→lint全場PASSのみcommit&push' `
    -Force | Out-Null

"登録しました: $TaskName"
Get-ScheduledTask -TaskName $TaskName |
    Select-Object TaskName, State, @{n='Trigger';e={ ($_.Triggers | ForEach-Object { $_.StartBoundary }) -join ' / ' }}
