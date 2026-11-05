$ErrorActionPreference = 'Stop'

if (-not $env:LOCALAPPDATA -or -not $env:APPDATA) {
    throw 'Windows did not provide the expected per-user data directories.'
}

$Install = Join-Path $env:LOCALAPPDATA 'Programs\VANTA'
$StartMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
$Shortcuts = @(
    (Join-Path $StartMenu 'VANTA Competition Tracker.lnk'),
    (Join-Path $StartMenu 'Uninstall VANTA Competition Tracker.lnk')
)

if (Test-Path -LiteralPath $Install) {
    try { Remove-Item -LiteralPath $Install -Recurse -Force }
    catch { throw 'Could not remove application files. Close VANTA and rerun this uninstaller.' }
}
foreach ($Shortcut in $Shortcuts) {
    if (Test-Path -LiteralPath $Shortcut) { Remove-Item -LiteralPath $Shortcut -Force }
}

Write-Host 'CHRONYX application files and Start menu shortcuts were removed.'
Write-Host "Competition data was preserved in $env:APPDATA\VANTA."
