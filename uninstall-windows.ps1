$ErrorActionPreference = 'Stop'

if (-not $env:LOCALAPPDATA -or -not $env:APPDATA) {
    throw 'Windows did not provide the expected per-user data directories.'
}

$Install = Join-Path $env:LOCALAPPDATA 'Programs\CHRONYX'
$StartMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
$Shortcuts = @(
    (Join-Path $StartMenu 'CHRONYX Competition Tracker.lnk'),
    (Join-Path $StartMenu 'Uninstall CHRONYX Competition Tracker.lnk')
)

if (Test-Path -LiteralPath $Install) {
    try { Remove-Item -LiteralPath $Install -Recurse -Force }
    catch { throw 'Could not remove application files. Close CHRONYX and rerun this uninstaller.' }
}
foreach ($LegacyPath in @((Join-Path $env:LOCALAPPDATA 'Programs\VANTA'), (Join-Path $StartMenu 'VANTA Competition Tracker.lnk'), (Join-Path $StartMenu 'Uninstall VANTA Competition Tracker.lnk'))) {
    if (Test-Path -LiteralPath $LegacyPath) { Remove-Item -LiteralPath $LegacyPath -Recurse -Force -ErrorAction SilentlyContinue }
}
foreach ($Shortcut in $Shortcuts) {
    if (Test-Path -LiteralPath $Shortcut) { Remove-Item -LiteralPath $Shortcut -Force }
}

Write-Host 'CHRONYX application files and Start menu shortcuts were removed.'
Write-Host "Competition data was preserved in $env:APPDATA\CHRONYX."
