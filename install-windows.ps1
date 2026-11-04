$ErrorActionPreference = 'Stop'

$Source = Split-Path -Parent $MyInvocation.MyCommand.Path
$Install = Join-Path $env:LOCALAPPDATA 'Programs\VANTA'
$StartMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'

New-Item -ItemType Directory -Force -Path $Install, $StartMenu | Out-Null
& robocopy $Source $Install /E /R:1 /W:1 /XD .git node_modules __pycache__ .venv /XF *.rpm
if ($LASTEXITCODE -ge 8) { throw "Copying VANTA files failed (robocopy exit $LASTEXITCODE)." }

$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) { throw 'Install Python 3.10+ from python.org and enable the Python launcher, then rerun this script.' }
& $Python.Source -m venv (Join-Path $Install '.venv')
$VenvPython = Join-Path $Install '.venv\Scripts\python.exe'
& $VenvPython -m pip install -r (Join-Path $Install 'requirements-windows.txt')

$ShortcutPath = Join-Path $StartMenu 'VANTA Competition Tracker.lnk'
$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = Join-Path $Install '.venv\Scripts\pythonw.exe'
$Shortcut.Arguments = '"' + (Join-Path $Install 'desktop.py') + '"'
$Shortcut.WorkingDirectory = $Install
$Shortcut.Description = 'Track competitions and registration deadlines'
$Shortcut.Save()

Write-Host "Installed VANTA. Open it from the Start menu: $ShortcutPath"
