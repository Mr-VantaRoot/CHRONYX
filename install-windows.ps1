$ErrorActionPreference = 'Stop'

$Source = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonCommand = Get-Command python -ErrorAction SilentlyContinue
$PythonPrefix = @()
if (-not $PythonCommand) {
    $PythonCommand = Get-Command py -ErrorAction SilentlyContinue
    if ($PythonCommand) { $PythonPrefix = @('-3') }
}
if (-not $PythonCommand) {
    throw 'Python is not installed. Install Python 3.10 or newer from https://www.python.org/downloads/windows/ and rerun this installer.'
}

$VersionText = & $PythonCommand.Source @PythonPrefix -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])' 2>$null
if ($LASTEXITCODE -ne 0 -or -not $VersionText) {
    throw 'Python was found but could not be started. Repair the Python installation or enable the Python launcher, then rerun this installer.'
}
try { $PythonVersion = [version]($VersionText.Trim()) }
catch { throw "Python reported an invalid version: $VersionText" }
if ($PythonVersion -lt [version]'3.10') {
    throw "Python $PythonVersion is too old. CHRONYX requires Python 3.10 or newer. Install a current Python release and rerun this installer."
}

$WebViewRoots = @(
    'HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients',
    'HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients',
    'HKCU:\SOFTWARE\Microsoft\EdgeUpdate\Clients'
)
$WebViewVersion = $null
foreach ($Root in $WebViewRoots) {
    if (-not (Test-Path -LiteralPath $Root)) { continue }
    foreach ($Client in (Get-ChildItem -LiteralPath $Root -ErrorAction SilentlyContinue)) {
        try {
            $Values = Get-ItemProperty -LiteralPath $Client.PSPath -ErrorAction Stop
            if ($Values.name -match 'WebView2 Runtime' -and $Values.pv -and $Values.pv -ne '0.0.0.0') {
                $WebViewVersion = $Values.pv
                break
            }
        } catch { }
    }
    if ($WebViewVersion) { break }
}
if (-not $WebViewVersion) {
    $ProgramRoots = @($env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:LOCALAPPDATA) | Where-Object { $_ }
    foreach ($ProgramRoot in $ProgramRoots) {
        $RuntimeFolder = Join-Path $ProgramRoot 'Microsoft\EdgeWebView\Application'
        if (Test-Path -LiteralPath $RuntimeFolder) {
            $Runtime = Get-ChildItem -LiteralPath $RuntimeFolder -Directory -ErrorAction SilentlyContinue |
                Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'msedgewebview2.exe') } |
                Select-Object -First 1
            if ($Runtime) { $WebViewVersion = $Runtime.Name; break }
        }
    }
}
if (-not $WebViewVersion) {
    throw 'Microsoft Edge WebView2 Runtime is missing. Install the Evergreen Runtime from https://developer.microsoft.com/microsoft-edge/webview2/ and rerun this installer.'
}

if (-not $env:LOCALAPPDATA -or -not $env:APPDATA) {
    throw 'Windows did not provide LOCALAPPDATA and APPDATA. Sign in to a normal desktop account and rerun this installer.'
}

$InstallParent = Join-Path $env:LOCALAPPDATA 'Programs'
$Install = Join-Path $InstallParent 'VANTA'
$Staging = Join-Path $InstallParent ".VANTA-stage-$PID"
$Previous = Join-Path $InstallParent ".VANTA-previous-$PID"
$StartMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
$ShortcutPath = Join-Path $StartMenu 'VANTA Competition Tracker.lnk'
$UninstallShortcutPath = Join-Path $StartMenu 'Uninstall VANTA Competition Tracker.lnk'
$ShortcutStage = Join-Path $StartMenu ".VANTA-shortcut-$PID.lnk"
$UninstallShortcutStage = Join-Path $StartMenu ".VANTA-uninstall-$PID.lnk"
$PreviousShortcut = Join-Path $StartMenu ".VANTA-shortcut-previous-$PID.lnk"
$PreviousUninstallShortcut = Join-Path $StartMenu ".VANTA-uninstall-previous-$PID.lnk"
$OldMoved = $false
$NewMoved = $false
$OldShortcutMoved = $false
$OldUninstallShortcutMoved = $false
$NewShortcutMoved = $false
$NewUninstallShortcutMoved = $false
$Committed = $false

try {
    New-Item -ItemType Directory -Force -Path $InstallParent, $StartMenu | Out-Null
    if (Test-Path -LiteralPath $Staging) { Remove-Item -LiteralPath $Staging -Recurse -Force }
    New-Item -ItemType Directory -Path $Staging | Out-Null

    & (Join-Path $env:SystemRoot 'System32\robocopy.exe') $Source $Staging /E /R:1 /W:1 /XD .git node_modules __pycache__ .venv /XF *.rpm *.sqlite3 *.sqlite3-wal *.sqlite3-shm
    $CopyResult = $LASTEXITCODE
    if ($CopyResult -ge 8) { throw "Copying application files failed (robocopy exit $CopyResult)." }

    $VenvPython = Join-Path $Staging '.venv\Scripts\python.exe'
    & $PythonCommand.Source @PythonPrefix -m venv (Join-Path $Staging '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Creating the private Python environment failed.' }
    if (-not (Test-Path -LiteralPath $VenvPython)) { throw 'Python reported success but the private environment executable is missing.' }

    & $VenvPython -m pip install --disable-pip-version-check -r (Join-Path $Staging 'requirements-windows.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Installing CHRONYX Python dependencies failed. Check your internet connection and Python package access, then rerun the installer.' }

    $Shell = New-Object -ComObject WScript.Shell
    $Shortcut = $Shell.CreateShortcut($ShortcutStage)
    $Shortcut.TargetPath = Join-Path $Install '.venv\Scripts\pythonw.exe'
    $Shortcut.Arguments = '"' + (Join-Path $Install 'desktop.py') + '"'
    $Shortcut.WorkingDirectory = $Install
    $Shortcut.Description = 'Track competitions and registration deadlines'
    $Shortcut.Save()

    $UninstallShortcut = $Shell.CreateShortcut($UninstallShortcutStage)
    $UninstallShortcut.TargetPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $UninstallShortcut.Arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + (Join-Path $Install 'uninstall-windows.ps1') + '"'
    $UninstallShortcut.WorkingDirectory = $Install
    $UninstallShortcut.Description = 'Remove CHRONYX application files; keep competition data'
    $UninstallShortcut.Save()

    if (Test-Path -LiteralPath $Install) {
        Move-Item -LiteralPath $Install -Destination $Previous
        $OldMoved = $true
    }
    Move-Item -LiteralPath $Staging -Destination $Install
    $NewMoved = $true
    if (Test-Path -LiteralPath $ShortcutPath) {
        Move-Item -LiteralPath $ShortcutPath -Destination $PreviousShortcut
        $OldShortcutMoved = $true
    }
    if (Test-Path -LiteralPath $UninstallShortcutPath) {
        Move-Item -LiteralPath $UninstallShortcutPath -Destination $PreviousUninstallShortcut
        $OldUninstallShortcutMoved = $true
    }
    Move-Item -LiteralPath $ShortcutStage -Destination $ShortcutPath -Force
    $NewShortcutMoved = $true
    Move-Item -LiteralPath $UninstallShortcutStage -Destination $UninstallShortcutPath -Force
    $NewUninstallShortcutMoved = $true
    $Committed = $true
    if ($OldMoved -and (Test-Path -LiteralPath $Previous)) {
        try { Remove-Item -LiteralPath $Previous -Recurse -Force }
        catch { Write-Warning "Installation succeeded, but the prior application files remain at $Previous" }
    }
    foreach ($OldShortcut in @($PreviousShortcut, $PreviousUninstallShortcut)) {
        if (Test-Path -LiteralPath $OldShortcut) {
            try { Remove-Item -LiteralPath $OldShortcut -Force }
            catch { Write-Warning "Installation succeeded, but a previous shortcut backup remains at $OldShortcut" }
        }
    }
    Write-Host "Installed CHRONYX for this user (Python $PythonVersion, WebView2 $WebViewVersion). Open VANTA Competition Tracker from the Start menu."
    Write-Host "Competition data remains in $env:APPDATA\VANTA."
}
catch {
    if (-not $Committed) {
        if ($NewShortcutMoved -and (Test-Path -LiteralPath $ShortcutPath)) { Remove-Item -LiteralPath $ShortcutPath -Force -ErrorAction SilentlyContinue }
        if ($NewUninstallShortcutMoved -and (Test-Path -LiteralPath $UninstallShortcutPath)) { Remove-Item -LiteralPath $UninstallShortcutPath -Force -ErrorAction SilentlyContinue }
        if ($OldShortcutMoved -and (Test-Path -LiteralPath $PreviousShortcut)) { Move-Item -LiteralPath $PreviousShortcut -Destination $ShortcutPath -Force -ErrorAction SilentlyContinue }
        if ($OldUninstallShortcutMoved -and (Test-Path -LiteralPath $PreviousUninstallShortcut)) { Move-Item -LiteralPath $PreviousUninstallShortcut -Destination $UninstallShortcutPath -Force -ErrorAction SilentlyContinue }
        if ($NewMoved -and (Test-Path -LiteralPath $Install)) { Remove-Item -LiteralPath $Install -Recurse -Force -ErrorAction SilentlyContinue }
        if ($OldMoved -and (Test-Path -LiteralPath $Previous)) { Move-Item -LiteralPath $Previous -Destination $Install -Force -ErrorAction SilentlyContinue }
    }
    throw
}
finally {
    foreach ($Path in @($Staging, $ShortcutStage, $UninstallShortcutStage)) {
        if (Test-Path -LiteralPath $Path) { Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction SilentlyContinue }
    }
}
