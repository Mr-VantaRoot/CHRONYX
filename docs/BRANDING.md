# Naming

The project is called **CHRONYX**. Releases up to and including 1.0.0-8 shipped under the name **VANTA**; the rename landed in 1.0.0-9.

## What is named CHRONYX

| Surface | Name |
| --- | --- |
| Repository, window title, interface, About page | CHRONYX |
| Command | `chronyx` |
| Fedora package | `chronyx` (obsoletes and provides `vanta`) |
| Desktop entry and icon | `chronyx.desktop`, `chronyx.svg` |
| Linux per-user install | `~/.local/lib/chronyx`, `~/.local/bin/chronyx` |
| Windows install and shortcuts | `%LOCALAPPDATA%\Programs\CHRONYX`, "CHRONYX Competition Tracker" |
| Linux data | `${XDG_DATA_HOME:-~/.local/share}/chronyx/chronyx.sqlite3` |
| Windows data | `%APPDATA%\CHRONYX\chronyx.sqlite3` |
| GTK application id | `io.chronyx.CompetitionTracker` |
| Export files | `chronyx-competitions.json`, `chronyx-competitions.csv` |
| Browser-storage keys | `chronyxEvents`, `chronyxEventOutbox`, `chronyxReminders`, `chronyxReminderOutbox`, `chronyxProfilePicture` |

## Intentional VANTA references (migration only)

These exist so that people who used a VANTA-named release lose nothing. They should stay until old installs are no longer supported.

- `server.py`: `legacy_data_directory()`, `LEGACY_DB_NAME` and `migrate_legacy_data()` copy the old database into the new data folder once. The old folder is only read, never changed or deleted. A marker file (`.migrated-from-vanta`) prevents the copy from ever running twice, so resetting the new database does not bring old data back. If the copy fails, the old database keeps being used instead of being hidden behind an empty one.
- `src/storage-migration.js`: moves the old `vanta*` browser-storage keys to the new `chronyx*` keys without overwriting newer data.
- `install-user.sh`, `uninstall-user.sh`, `install-windows.ps1`, `uninstall-windows.ps1`: remove the old VANTA install files and shortcuts.
- `packaging/chronyx.spec`: `Obsoletes: vanta` and `Provides: vanta` so `dnf` replaces the old package.

The maintainer's GitHub handle (`Mr-VantaRoot`) is a personal identity, not a product name, and is unchanged.
