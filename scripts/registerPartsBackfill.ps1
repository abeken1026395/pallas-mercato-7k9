# registerPartsBackfill.ps1
# dailyPartsBackfill.ps1 を「毎日 JST 09:00 と 18:30」の2回走らせるタスクを登録する。
# タスクは1本のまま、トリガだけ2つ持たせる。再実行すれば設定を上書き更新する。
#
# なぜ 09:00 + 18:30 か（2026-08-04 に実測で見直した）:
#   当初は 18:30 の1回だけにしていた。根拠は「beforeinfo収集(Actions)の
#   コミット着地実績 07/29 17:12 / 07/30 17:03 / 07/31 17:18」だったが、
#   これは測る対象を取り違えていた。17時台は「その日の最終便が落ちる時刻」で
#   あって、「新しい開催日の行が motorParts に生える時刻」ではない。
#
#   直近8日を git 履歴から実測した（各開催日の行が初めて出現した時刻・JST）:
#     20260727 → 07-28 07:41   20260728 → 07-29 07:38   20260729 → 07-30 07:34
#     20260730 → 07-31 07:38   20260731 → 08-01 07:44   20260801 → 08-02 07:33
#     20260802 → 08-03 07:30   20260803 → 08-04 07:39
#   例外なく翌朝の第1便で生え、幅は 07:30〜07:44 の14分に収まる。
#   第2便(14時台)・第3便(17〜18時台)は、その開催日の行数も空件数も変えない。
#   空件数が減るのはローカル補填のときだけ。
#
#   よって本命は 09:00。観測最遅 07:44 に対し約1時間15分の余裕があり、
#   行が生えてから埋まるまでの空白は約1.4時間になる（18:30 単独では約10.9時間）。
#   18:30 は回収枠として残す。GitHub のスケジュール遅延は 1.5〜3.8時間の実績が
#   あるため、第1便が 09:00 を超えて着地した日はここで拾う。
#   さらに翌 06:00 の dailyMotorUsage.ps1 側 backfill が三段目の保険になる。
#   backfill は空欄だけを埋める冪等な処理で、空振りしても害は無い
#   （差分が無ければコミットしない）。
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

# -Trigger は配列を受け付ける。タスクを2本に分けず、1本に2トリガを持たせる。
$trigger = @(
    (New-ScheduledTaskTrigger -Daily -At '09:00'),   # 本命: 第1便(07:30〜07:44)の直後
    (New-ScheduledTaskTrigger -Daily -At '18:30')    # 回収: 第1便が遅延した日ぶん
)

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
    -Description 'motorParts.json モーターNo空欄をKから補填 → 補填があればcommit&push（第1便着地後の09:00が本命・18:30が遅延回収。翌6:00のdailyMotorUsageが保険）' `
    -Force | Out-Null

"登録しました: $TaskName"
Get-ScheduledTask -TaskName $TaskName |
    Select-Object TaskName, State, @{n='Triggers';e={ ($_.Triggers | ForEach-Object { $_.StartBoundary }) -join ' / ' }}
