' runHidden.vbs
' 窓を出さずに PowerShell スクリプトを起動し、その終了コードをそのまま返す。
' conhost.exe --headless 経由だと、子の終了コードが失われ、タスクスケジューラの「前回の結果」が常に 0 になる
' （2026-11-19 実測：conhost 直・conhost+cmd とも rc=0、wscript 経由は rc=1 が取れる）。
' 使い方: wscript.exe //B //Nologo runHidden.vbs "<ps1のフルパス>"
Set sh = CreateObject("WScript.Shell")
If WScript.Arguments.Count < 1 Then WScript.Quit 2
cmd = "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File """ & WScript.Arguments(0) & """"
WScript.Quit sh.Run(cmd, 0, True)
