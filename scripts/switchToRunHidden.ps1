# switchToRunHidden.ps1
# 登録済みタスクの操作（conhost.exe --headless で powershell -File <ps1>）を、
# wscript.exe //B //Nologo "<runHidden.vbs>" "<ps1>" に置き換える（終了コードを保つため）。
# トリガー・実行ユーザー・設定・説明は今の実物のまま。想定と違う形の操作なら何も変えず exit 2。
# 使い方: switchToRunHidden.ps1 -TaskName <名前> [-WhatIf]（-WhatIf は前後の操作を出すだけ）
# 文字コード: このファイルは UTF-8 BOM 付きで保存すること。
[CmdletBinding(SupportsShouldProcess = $true)]
param([Parameter(Mandatory = $true)][string]$TaskName)

$ErrorActionPreference = 'Stop'
$Vbs = Join-Path $PSScriptRoot 'runHidden.vbs'

function Mask([string]$s) {
    # 秘密らしい文字列（token/secret/password/key の値、長い英数字列）を伏せる
    $s = [regex]::Replace($s, '(?i)(token|secret|password|passwd|key)(\s*[=:]\s*)\S+', '$1$2***')
    return [regex]::Replace($s, '[A-Za-z0-9_\-]{32,}', '***')
}

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
$acts = @($task.Actions)
if ($acts.Count -ne 1) { Write-Output ("想定外: 操作が {0} 個。何も変えない" -f $acts.Count); exit 2 }
$a = $acts[0]
$exe = [string]$a.Execute
$arg = [string]$a.Arguments
if ($exe -notmatch '(?i)conhost\.exe"?$' -or $arg -notmatch '(?i)--headless' -or $arg -notmatch '(?i)powershell') {
    Write-Output ("想定外の形: {0} {1}。何も変えない" -f $exe, (Mask $arg)); exit 2
}
$m = [regex]::Match($arg, '(?i)-File\s+(?:"([^"]+)"|(\S+))')
if (-not $m.Success) { Write-Output '想定外: -File が見つからない。何も変えない'; exit 2 }
$ps1 = if ($m.Groups[1].Success) { $m.Groups[1].Value } else { $m.Groups[2].Value }

$newExe = 'wscript.exe'
$newArg = '//B //Nologo "{0}" "{1}"' -f $Vbs, $ps1
Write-Output ("前: {0} {1}" -f $exe, (Mask $arg))
Write-Output ("後: {0} {1}" -f $newExe, (Mask $newArg))

if ($PSCmdlet.ShouldProcess($TaskName, '操作を wscript + runHidden.vbs に置き換える')) {
    if ($a.WorkingDirectory) {
        $new = New-ScheduledTaskAction -Execute $newExe -Argument $newArg -WorkingDirectory $a.WorkingDirectory
    } else {
        $new = New-ScheduledTaskAction -Execute $newExe -Argument $newArg
    }
    Set-ScheduledTask -TaskName $TaskName -Action $new | Out-Null
    Write-Output '更新した'
}
exit 0
