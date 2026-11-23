@echo off
if /i "%~1"=="--hidden" goto launch
start "" wscript.exe "%~dp0Launch-desktop.vbs"
exit /b

:launch
if not exist "%~dp0.venv-desktop\Scripts\pythonw.exe" (
    wscript.exe "%~dp0Launch-desktop.vbs" --missing
    exit /b 1
)
start "" /D "%~dp0" "%~dp0.venv-desktop\Scripts\pythonw.exe" "%~dp0desktop_main.py"
exit /b
