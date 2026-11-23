Option Explicit
Dim shell, fso, folder, command
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
If Not fso.FileExists(folder & "\.venv-desktop\Scripts\pythonw.exe") Or WScript.Arguments.Count > 0 Then
    MsgBox "T-BCM is not installed. Run Start.bat in the project folder first.", vbExclamation, "T-BCM"
    WScript.Quit 1
End If
' Run the desktop batch file with its console hidden, including from the shortcut.
command = "cmd.exe /d /s /c " & Chr(34) & Chr(34) & folder & "\Start-desktop.bat" & Chr(34) & " --hidden" & Chr(34)
shell.Run command, 0, False
