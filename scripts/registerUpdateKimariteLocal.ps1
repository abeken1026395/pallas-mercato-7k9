# registerUpdateKimariteLocal.ps1
# updateKimariteLocal.ps1 を「毎月 2日・16日 JST 6:30」に走らせるタスクを登録する。再実行で上書き更新。
#
# 実行時刻について:
#   既存のローカルタスクと重ならないようずらしてある。
#     05:30 boatrace-writeKansenkiLocal（観戦記の執筆）
#     06:00 boatrace-dailyMotorUsage  （Kファイル差分収集）
#     06:30 boatrace-updateKimarite   （これ。決まり手CSV・月2回）
#   updateKimariteLocal.ps1 は 183日ぶんを mbrace から取り直すため 30分前後かかる。
#   dailyMotorUsage の後ろに置き、両者がKファイル取得で競合しないようにしている。
#
# 実行日について:
#   Actions 側の updateKimarite.yml は cron "23 19 1,15 * *"（UTC）＝ JST 毎月2日・16日 04:23 だった。
#   移設後も同じ「2日・16日」を踏襲する（6ヶ月窓の集計なので月2回でじゅうぶん）。
#
# ログオン種別について（registerDailyMotorUsage.ps1 と同じ理由・重要）:
#   git push は Git Credential Manager が Windows資格情報マネージャーに持つ資格情報を使う。
#   これはユーザーのDPAPIで保護されているため、"ユーザーがログオンしていなくても実行" にすると
#   資格情報を復号できず push が失敗しうる。そのため RunLevel=LeastPrivilege かつ
#   LogonType=InteractiveToken（= ログオン時のみ実行）で登録する。
#   スリープからの起復は WakeToRun で担保する。
#
# なぜ XML 登録なのか:
#   「毎月の指定日」トリガは New-ScheduledTaskTrigger では作れない。
#   CIM の MSFT_TaskMonthlyTrigger を New-CimInstance -ClientOnly で組む方法は
#   Register-ScheduledTask が 0x80070057（パラメーターが正しくありません）で拒否するため使えない。
#   タスクXMLを直接渡す方式なら日付を <Day> で明示でき、確実に登録できる。

$ErrorActionPreference = 'Stop'

$TaskName = 'boatrace-updateKimarite'
$Script   = 'C:\Users\USER\boatrace\scripts\updateKimariteLocal.ps1'
$PwshExe  = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"

$RunDays = @(2, 16)      # 実行する日（毎月）
$RunTime = '06:30'

if (-not (Test-Path $Script)) { throw "対象スクリプトが無い: $Script" }

$hh, $mm = $RunTime -split ':'
$startBoundary = (Get-Date -Hour ([int]$hh) -Minute ([int]$mm) -Second 0).ToString('yyyy-MM-ddTHH:mm:ss')

$dayNodes = ($RunDays | ForEach-Object { "          <Day>$_</Day>" }) -join "`n"
# $args は PowerShell の自動変数なので使わない（$taskArgs にする）
$taskArgs = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{0}"' -f $Script
$user     = "$env:USERDOMAIN\$env:USERNAME"
$desc     = 'mbrace Kファイル183日集計 → 検証4項目（行数/列構成/激減/取得率）を通ったものだけ docs/players/racerKimarite.csv へ配置 → 変更があればcommit&push'

# XML へ埋める値は必ずエスケープする。
# 説明文の "commit&push" の & を生のまま入れると
# Register-ScheduledTask が「The task XML is malformed」で拒否する。
function Esc([string]$s) { return [System.Security.SecurityElement]::Escape($s) }
$descX     = Esc $desc
$userX     = Esc $user
$taskArgsX = Esc $taskArgs
$pwshX     = Esc $PwshExe

$xml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>$descX</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>$startBoundary</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByMonth>
        <DaysOfMonth>
$dayNodes
        </DaysOfMonth>
        <Months>
          <January /><February /><March /><April /><May /><June />
          <July /><August /><September /><October /><November /><December />
        </Months>
      </ScheduleByMonth>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>$userX</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>true</WakeToRun>
    <ExecutionTimeLimit>PT2H</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>$pwshX</Command>
      <Arguments>$taskArgsX</Arguments>
    </Exec>
  </Actions>
</Task>
"@

Register-ScheduledTask -TaskName $TaskName -Xml $xml -Force | Out-Null

"登録しました: $TaskName（毎月 {0} 日 {1}）" -f ($RunDays -join '・'), $RunTime

# 登録結果の確認（実際に登録された日付をXMLから読み戻して見せる）
$registered = [xml](Export-ScheduledTask -TaskName $TaskName)
$regDays = $registered.Task.Triggers.CalendarTrigger.ScheduleByMonth.DaysOfMonth.Day
"登録された実行日: {0} 日 / 開始時刻: {1}" -f ($regDays -join '・'),
    $registered.Task.Triggers.CalendarTrigger.StartBoundary
Get-ScheduledTaskInfo -TaskName $TaskName |
    Select-Object TaskName, NextRunTime, LastRunTime, LastTaskResult
