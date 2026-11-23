$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$project = $PSScriptRoot
$dataDir = Join-Path $project '.desktop-data'
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
$logPath = Join-Path $dataDir 'install.log'
$form = New-Object System.Windows.Forms.Form
$form.Text = 'T-BCM'
$form.Size = New-Object System.Drawing.Size(590, 160)
$form.StartPosition = 'CenterScreen'
$form.ControlBox = $false
$label = New-Object System.Windows.Forms.Label
$label.Location = New-Object System.Drawing.Point(20, 20)
$label.Size = New-Object System.Drawing.Size(540, 75)
$form.Controls.Add($label)

function Status([string]$message) {
    $label.Text = $message
    [System.Windows.Forms.Application]::DoEvents()
}

function Run-Hidden([string]$exe, [string[]]$arguments) {
    # All arguments are single values, including paths containing spaces.
    $quoted = $arguments | ForEach-Object { '"' + $_.Replace('"', '\"') + '"' }
    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = $exe
    $info.Arguments = $quoted -join ' '
    $info.WorkingDirectory = $project
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $info
    [void]$proc.Start()
    $stdout = $proc.StandardOutput.ReadToEndAsync()
    $stderr = $proc.StandardError.ReadToEndAsync()
    while (-not $proc.WaitForExit(100)) { [System.Windows.Forms.Application]::DoEvents() }
    $stdout.Result | Add-Content -LiteralPath $logPath -Encoding UTF8
    $stderr.Result | Add-Content -LiteralPath $logPath -Encoding UTF8
    if ($proc.ExitCode -ne 0) { throw "Installation command failed ($($proc.ExitCode)). See $logPath" }
    $proc.Dispose()
}

$lockStream = $null
try {
    try {
        $lockStream = [System.IO.File]::Open((Join-Path $dataDir 'install.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    } catch {
        [System.Windows.Forms.MessageBox]::Show('T-BCM setup is already running.', 'T-BCM') | Out-Null
        exit
    }
    $form.Show()
    Status 'Preparing T-BCM. First setup downloads Python and dependencies (several GB). Please wait.'
    $uv = Join-Path $dataDir 'uv.exe'
    $venv = Join-Path $project '.venv-desktop'
    $python = Join-Path $venv 'Scripts\python.exe'
    $pythonw = Join-Path $venv 'Scripts\pythonw.exe'
    $requirements = Join-Path $project 'requirements.txt'
    $hash = (Get-FileHash -LiteralPath $requirements -Algorithm SHA256).Hash
    $stamp = Join-Path $dataDir 'requirements.sha256'
    if (-not (Test-Path -LiteralPath $uv)) {
        Status 'Downloading uv package manager...'
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $archive = Join-Path $dataDir 'uv.zip'
        $uvVersion = '0.12.15'
        Invoke-WebRequest -UseBasicParsing -Uri "https://github.com/astral-sh/uv/releases/download/$uvVersion/uv-x86_64-pc-windows-msvc.zip" -OutFile $archive
        Expand-Archive -LiteralPath $archive -DestinationPath $dataDir -Force
    }
    # uv's Python distributions include Tk on Windows; no admin installation or PATH changes.
    $env:UV_PYTHON_INSTALL_DIR = Join-Path $dataDir 'python'
    $env:UV_CACHE_DIR = Join-Path $dataDir 'uv-cache'
    $env:UV_SYSTEM_CERTS = 'true'
    $createdEnvironment = $false
    if (-not (Test-Path -LiteralPath $pythonw)) {
        Status 'Installing local Python 3.12...'
        Run-Hidden $uv @('python', 'install', '3.12', '--no-bin', '--no-registry')
        Run-Hidden $uv @('venv', '--python', '3.12', '--managed-python', $venv)
        $createdEnvironment = $true
    }
    $installedHash = if (Test-Path -LiteralPath $stamp) { (Get-Content -LiteralPath $stamp -Raw).Trim() } else { '' }
    if ($installedHash -ne $hash -or $createdEnvironment) {
        Status 'Installing speech libraries. This can take a long time; details are in .desktop-data/install.log.'
        Run-Hidden $uv @('pip', 'install', '--python', $python, '--index-strategy', 'unsafe-best-match', '-r', $requirements)
        Run-Hidden $python @('-c', 'import tkinter, whisperx, torch, docx, imageio_ffmpeg; from whisperx.diarize import DiarizationPipeline; from whisperx.asr import load_model; from whisperx.alignment import load_align_model')
        Set-Content -LiteralPath $stamp -Value $hash -Encoding ASCII
    }
    Status 'Creating desktop shortcut...'
    & (Join-Path $project 'create-shortcut.ps1') -ProjectDirectory $project
    Status 'Starting application. Next time use the T-BCM Desktop shortcut.'
    Start-Process -FilePath $pythonw -ArgumentList @(('"' + (Join-Path $project 'desktop_main.py') + '"')) -WorkingDirectory $project -WindowStyle Hidden
} catch {
    $_ | Out-String | Add-Content -LiteralPath $logPath -Encoding UTF8
    [System.Windows.Forms.MessageBox]::Show("Could not start T-BCM.`n$($_.Exception.Message)`n`nCheck your internet connection and run Start again.`nLog: $logPath", 'T-BCM') | Out-Null
} finally {
    if ($lockStream) { $lockStream.Dispose() }
    $form.Dispose()
}
