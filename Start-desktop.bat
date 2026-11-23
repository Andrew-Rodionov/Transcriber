@echo off
if not exist "%~dp0.venv-desktop\Scripts\pythonw.exe" (
    start "" powershell.exe -NoProfile -WindowStyle Hidden -Command "Add-Type -AssemblyName System.Windows.Forms; [void][System.Windows.Forms.MessageBox]::Show('Run Start.bat in the program folder to install T-BCM first.', 'T-BCM')"
    exit /b 1
)
start "" /D "%~dp0" "%~dp0.venv-desktop\Scripts\pythonw.exe" "%~dp0desktop_main.py"
exit /b
