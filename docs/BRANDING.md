# Branding inventory

CHRONYX and VANTA currently coexist across repository, application, packaging, generated assets, and storage identifiers. This is an inventory snapshot; line numbers refer to this source tree at generation time.

No branding rename has been made. A future data-folder rename must include a one-time database migration so existing `~/.local/share/vanta` and `%APPDATA%\VANTA` databases remain discoverable.

## Current naming surfaces

- **CHRONYX** appears in repository-facing metadata, Python server logs, security documentation, and project documentation.
- **VANTA** appears in the product title, executable and RPM package name, Linux launchers, Windows installation paths, and UI labels.
- Linux user data remains in `${XDG_DATA_HOME:-$HOME/.local/share}/vanta`; Windows user data remains in `%APPDATA%\VANTA`.
- Compiled frontend bundles mirror labels from the source components.

## File and line inventory

The following files contain either brand name. Line numbers are grouped by file to make a later rename reviewable. This index file is excluded from its own inventory.

| File | Lines containing CHRONYX or VANTA |
| --- | --- |
| `package.json` | 2 |
| `index.html` | 1 |
| `LICENSE` | 3 |
| `desktop.py` | 34, 36, 44, 53, 56, 77, 91, 99, 101, 108, 111, 123, 130 |
| `package-lock.json` | 2, 8 |
| `README.md` | 1, 3, 30, 33, 34, 36, 42, 45, 46, 56, 60, 66, 74, 91, 99, 101, 110, 114, 121, 128, 129, 132, 134, 139, 140, 143, 187, 196, 197, 198, 201, 206, 207, 209, 213, 242 |
| `server.py` | 2, 45, 49, 54, 128, 352, 423, 432, 444, 487, 491, 537, 605, 623, 681, 706, 714, 727, 729, 841, 846, 857 |
| `install-user.sh` | 5, 9, 10, 31, 32, 33, 34, 56, 59, 60, 63, 66, 76, 84 |
| `uninstall-user.sh` | 4, 5, 6, 7, 12 |
| `install-windows.ps1` | 21, 64, 65, 66, 68, 69, 70, 71, 72, 73, 97, 111, 143, 144 |
| `uninstall-windows.ps1` | 7, 10, 11, 16, 22, 23 |
| `SECURITY.md` | 5, 9 |
| `src/event-store.js` | 1, 2, 3, 4 |
| `src/Dashboard.tsx` | 31 |
| `src/SettingsPage.tsx` | 80, 92, 99, 106 |
| `src/App.tsx` | 57, 148, 181 |
| `packaging/vanta.desktop` | 2, 4, 5 |
| `packaging/vanta.spec` | 1, 22, 23, 24, 25, 26, 28, 30, 31, 33, 35, 36, 42, 45, 46, 47, 48, 49, 50, 51, 52, 55, 59, 63, 66, 70, 75, 79 |
| `tests/test_paths.py` | 12, 15, 18, 21, 24 |
| `tests/test_service.py` | 136 |
| `tests/event-store.test.js` | 25, 32, 33, 42, 55, 56, 77, 82, 98, 103, 106, 114, 127, 131 |
| `tests/test_desktop.py` | 44 |
| `dist/index.html` | 1 |
| `.github/workflows/ci.yml` | 1, 105, 106, 107, 108 |
| `.github/workflows/release-rpm.yml` | 28, 29, 30 |
| `dist/assets/index-0H94CXi_.js` | 180 |
