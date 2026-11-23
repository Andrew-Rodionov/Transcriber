param(
    [string]$ProjectDirectory = $PSScriptRoot,
    [string]$DesktopDirectory = [Environment]::GetFolderPath('DesktopDirectory')
)
$ErrorActionPreference = 'Stop'
if (-not $DesktopDirectory -or -not (Test-Path -LiteralPath $DesktopDirectory -PathType Container)) {
    throw 'Windows desktop folder is unavailable.'
}
$shell = New-Object -ComObject WScript.Shell
$shortcutPath = Join-Path $DesktopDirectory 'T-BCM Desktop.lnk'
$shortcut = $shell.CreateShortcut($shortcutPath)
# pythonw starts the same application as Start-desktop.bat without a console.
$shortcut.TargetPath = Join-Path $ProjectDirectory '.venv-desktop\Scripts\pythonw.exe'
$shortcut.Arguments = '"' + (Join-Path $ProjectDirectory 'desktop_main.py') + '"'
$shortcut.WorkingDirectory = $ProjectDirectory
$shortcut.Description = 'T-BCM desktop (Start-desktop.bat)'
$shortcut.IconLocation = (Join-Path $env:SystemRoot 'System32\telephon.cpl') + ',0'
$shortcut.WindowStyle = 1
$shortcut.Save()
