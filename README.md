# CHRONYX

[![CI](https://github.com/Mr-VantaRoot/CHRONYX/actions/workflows/ci.yml/badge.svg)](https://github.com/Mr-VantaRoot/CHRONYX/actions/workflows/ci.yml)

**Never miss a registration deadline again.** CHRONYX is an offline-first desktop app for tracking competitions, registration deadlines, and reminders: CTFs, hackathons, scholarships, programming contests, and anything else with a date attached. Its React interface runs in an embedded native webview (it does not launch Brave, Firefox, or another browser), and your data is stored in SQLite on your own device. No account, no cloud.

> CHRONYX was previously released as **VANTA** (up to 1.0.0-8). Upgrading keeps your data. See [Upgrading from VANTA](#upgrading-from-vanta).

**Contents:** [Features](#features) · [Platform support](#platform-support-and-verification-status) · [Install](#install-on-fedora) · [Upgrading from VANTA](#upgrading-from-vanta) · [Using CHRONYX](#first-launch-and-daily-use) · [Data and privacy](#data-backups-and-privacy) · [Development](#development) · [Troubleshooting](#troubleshooting) · [Security](#security-assumptions)

## Features

- Track CTFs, hackathons, AI/ML events, robotics competitions, programming contests, scholarships, and other opportunities.
- Create, edit, duplicate, complete, and delete events; save descriptions, organisers, links, dates, deadlines, time zones, status, priority, and notes.
- Live start and deadline countdowns, dashboard summaries, upcoming events, and recent activity.
- Month, week, day, and agenda calendar views, with separate deadline markers and multi-day events.
- Competition website and registration links open in the system browser.
- Search and filter by category, status, and priority; sort by start date or registration deadline.
- Desktop reminders 7 days, 3 days, 1 day, or 1 hour before starts and registration deadlines, plus a custom hour offset. Failed deliveries are retried, and one catch-up reminder is sent after downtime.
- JSON backup and import, CSV export, and dark/light themes.
- A device-local profile picture shown in the workspace sidebar.
- Offline edits are queued and synchronized automatically; changes the service permanently rejects are discarded with a visible notice instead of blocking later changes.

## Platform support and verification status

| Platform | Desktop view | Installation | Tested here |
| --- | --- | --- | --- |
| Fedora Linux 44 | GTK 3 + WebKitGTK 4.1 + PyGObject | RPM or per-user install | **Partially verified:** unit tests, GTK/WebKit imports, the RPM build and its package metadata pass. Live desktop notifications, the installed launch, and native export saving still need manual verification |
| Ubuntu 24.04 LTS or newer | GTK 3 + WebKitGTK 4.1 + PyGObject | Install native dependencies, then `./install-user.sh` | **Not verified:** package names checked against Ubuntu package metadata; no Ubuntu runtime was available |
| Kali Linux rolling | GTK 3 + WebKitGTK 4.1 + PyGObject | Install available Debian-based dependencies, then `./install-user.sh` | **Not verified:** no Kali runtime was available |
| Windows 10/11 | pywebview + Microsoft Edge WebView2 Runtime | `install-windows.ps1` | **Not verified on a desktop:** unit tests run on Windows in CI and both PowerShell scripts are parsed there, but a native Windows desktop was unavailable |

The frontend, countdown code, local API, and SQLite schema are shared. Native windows and notifications use platform runtimes. Package names and WebKitGTK versions vary by distribution; the RPM is Fedora-specific. Windows requires Python 3.10+ and the WebView2 Runtime. See Microsoft's [WebView2 deployment documentation](https://learn.microsoft.com/microsoft-edge/webview2/concepts/distribution) and pywebview's [installation guide](https://pywebview.flowrl.com/guide/installation.html).

## Install on Fedora

Download the RPM and checksum file from the [latest GitHub Release](https://github.com/Mr-VantaRoot/CHRONYX/releases/latest), then verify and install them:

```bash
curl -fLO https://github.com/Mr-VantaRoot/CHRONYX/releases/latest/download/chronyx-1.0.0-9.fc44.noarch.rpm
curl -fLO https://github.com/Mr-VantaRoot/CHRONYX/releases/latest/download/SHA256SUMS
sha256sum --check SHA256SUMS
sudo dnf install ./chronyx-1.0.0-9.fc44.noarch.rpm
```

If the machine is offline and GTK 3, WebKitGTK 4.1, Python, and PyGObject are already installed, skip repository refresh:

```bash
sudo dnf install --disablerepo='*' ./chronyx-1.0.0-9.fc44.noarch.rpm
```

Launch **CHRONYX Competition Tracker** from the applications menu or run `chronyx` in a terminal.
To uninstall, run `sudo dnf remove chronyx`; this leaves per-user data under `~/.local/share/chronyx` intact.

### User-level Linux install

After installing your distribution's native dependencies (below), run:

```bash
./install-user.sh
```

The script stages and checks the files before replacing `~/.local/lib/chronyx`, creates `~/.local/bin/chronyx`, and adds a desktop entry and icon. Competition data lives under `~/.local/share/chronyx`. To remove the per-user app files and launcher while keeping user data, run `~/.local/lib/chronyx/uninstall-user.sh`.

### Linux runtime dependencies

The Linux shell needs Python 3.10+, GTK 3, WebKitGTK 4.1, PyGObject bindings for the same Python interpreter that launches CHRONYX, and IANA timezone data. `notify-send` is required for Linux desktop reminders (`libnotify` on Fedora, `libnotify-bin` on Debian-derived systems). Without it, event tracking still works and the reminder service records retryable failures.

For a source install on Fedora, install dependencies with `sudo dnf install python3 gtk3 webkit2gtk4.1 python3-gobject libnotify tzdata`. The Fedora RPM declares these requirements itself.

### Ubuntu

Ubuntu 24.04 LTS or newer provides the WebKitGTK 4.1 introspection package. Install dependencies and CHRONYX as your normal user:

```bash
sudo apt update
sudo apt install python3 python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1 libnotify-bin tzdata
./install-user.sh
```

Launch **CHRONYX Competition Tracker** from the applications menu or run `~/.local/bin/chronyx`. The [Ubuntu package index](https://packages.ubuntu.com/noble/gir1.2-webkit2-4.1) lists WebKitGTK 4.1 for Noble (24.04 LTS). Earlier Ubuntu releases may only provide WebKitGTK 4.0, which this application does not use.

### Kali Linux

On current Kali rolling, install the available GTK 3, WebKitGTK 4.1 and PyGObject packages, then use the per-user installer. Package availability follows Kali's current Debian-based repositories; check WebKitGTK 4.1 before installing:

```bash
sudo apt update
apt-cache policy gir1.2-webkit2-4.1
sudo apt install python3 python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1 libnotify-bin tzdata
./install-user.sh
```

If `apt-cache policy` shows no candidate for `gir1.2-webkit2-4.1`, the configured Kali repositories do not provide the runtime needed by this build. The package name is present in Debian's [WebKitGTK 4.1 package index](https://packages.debian.org/bookworm/gir1.2-webkit2-4.1), but Kali itself has not been tested here.

## Install on Windows

Windows requires Python 3.10+ and the Microsoft Edge WebView2 Runtime. CHRONYX uses WebView2 inside its own window; it does not open the Edge browser. The installer checks both prerequisites, stages files before replacing an old installation, and installs `pywebview`, `winotify`, and IANA timezone data in a private virtual environment. Setup needs internet or a configured local Python package index; runtime use is offline.

Open PowerShell in the repository folder and run:

```powershell
powershell -ExecutionPolicy Bypass -File .\install-windows.ps1
```

The script installs the app under `%LOCALAPPDATA%\Programs\CHRONYX` and creates Start menu shortcuts for launch and uninstall. Launch **CHRONYX Competition Tracker** from Start. Competition data is stored under `%APPDATA%\CHRONYX\chronyx.sqlite3`. Windows notifications use toast notifications through `winotify`.

To uninstall, close CHRONYX and choose **Uninstall CHRONYX Competition Tracker** from Start, or run `%LOCALAPPDATA%\Programs\CHRONYX\uninstall-windows.ps1` in PowerShell. The app files and shortcuts are removed; `%APPDATA%\CHRONYX` is preserved so competition data remains available if you reinstall.

For a source checkout without installing a shortcut:

```powershell
python -m pip install -r requirements-windows.txt
python desktop.py
```

If the WebView2 Runtime is missing, install Microsoft's [Evergreen WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/), then launch CHRONYX again.

## Upgrading from VANTA

Releases up to 1.0.0-8 were named VANTA. Installing CHRONYX over them is safe and keeps your competitions.

| What | How it is handled |
| --- | --- |
| Fedora RPM | `sudo dnf install ./chronyx-…rpm` replaces the old `vanta` package automatically. |
| Per-user Linux install | `./install-user.sh` installs CHRONYX and removes the old `~/.local/lib/vanta`, `~/.local/bin/vanta`, desktop entry, and icon. |
| Windows | `install-windows.ps1` installs CHRONYX and removes the old `Programs\VANTA` folder and shortcuts. |
| Your competitions | The first time CHRONYX starts, it **copies** your database from the old data folder (`~/.local/share/vanta` or `%APPDATA%\VANTA`) into the new one. The copy happens once and includes reminder history, so you will not get duplicate reminders. |
| Profile picture, offline queue | Moved to their new browser-storage keys automatically. |
| The old data folder | **Never modified or deleted.** Once you have confirmed everything looks right, you may delete it yourself. |

Close any running VANTA window before starting CHRONYX; both use port 8765. If your competitions look missing after the upgrade, see [Troubleshooting](#troubleshooting).

## First launch and daily use

1. Launch CHRONYX from the applications menu or Start menu.
2. Choose **Add competition**. Enter a name, start date/time, and valid IANA time zone, such as `Africa/Nairobi`.
3. Add optional category, organiser, description, end date, registration deadline, website, registration URL, status, priority, and personal notes.
4. Use the dashboard to watch the nearest start countdown. **All Competitions** provides search, filters, sorting, and event actions. Press Ctrl+K (or Cmd+K) to jump to search.
5. Use **Calendar** for Month, Week, Day, or Agenda. Select an entry to open its details.
6. In **Settings**, choose a profile picture, change the theme, configure reminders, export a JSON or CSV file, or import a JSON backup. The profile picture is saved locally on that device and is not included in competition exports.

To receive reminders, leave CHRONYX running in your desktop session. The scheduler checks once a minute and stores sent reminder keys in SQLite to avoid sending the same reminder twice. If CHRONYX was closed when a reminder window opened, it sends one catch-up for the tightest missed window when it next runs. Adding, importing, or editing an event that is already inside a reminder window does not trigger an immediate notification. Notifications show the actual time remaining. Linux needs a session notification bus and `notify-send`; Windows needs working Windows notifications. Completed and cancelled events do not generate reminders.

## Data, backups, and privacy

The default database locations are:

```text
Linux:   ${XDG_DATA_HOME:-$HOME/.local/share}/chronyx/chronyx.sqlite3
Windows: %APPDATA%\CHRONYX\chronyx.sqlite3
```

SQLite stores competition records, reminder preferences, and notification delivery/retry state. Profile pictures and the offline write queue are held in the embedded webview's per-user browser storage, not in SQLite or competition JSON backups. CHRONYX's local API binds only to `127.0.0.1:8765`; it does not listen on LAN interfaces. Every request must carry this service's own Host, and any Origin header must be exactly `http://127.0.0.1:8765` or `http://localhost:8765`; requests without an Origin are accepted for the native desktop shell. No cloud account or network access is needed after installation.

Use **Settings → Backup JSON** for a portable event backup and **Settings → Import JSON** to import/merge events. CSV export is for spreadsheets; it is not an import format. Back up the webview profile separately if you want to preserve the profile picture and queued offline edits.

JSON and CSV downloads use the local API's attachment endpoints. On Linux the desktop shell saves them to your Downloads folder without overwriting existing files and confirms the saved path in a dialog; on Windows the shell enables pywebview downloads so WebView2 shows its own save flow. Both still need manual verification on a real desktop. JSON import validates every row, converts offset-free wall times in the event timezone, imports valid rows in one database transaction, and shows the exact invalid rows and reasons. CSV cells beginning with spreadsheet formula characters are prefixed to prevent formula execution when opened in spreadsheet software.

To back up the entire SQLite database, close CHRONYX and run on Linux:

```bash
sqlite3 "${XDG_DATA_HOME:-$HOME/.local/share}/chronyx/chronyx.sqlite3" \
  ".backup '$HOME/chronyx-database-backup.sqlite3'"
```

On Windows, close CHRONYX and copy `%APPDATA%\CHRONYX\chronyx.sqlite3` to your backup location. Uninstalling CHRONYX does not remove the database.

## Development

### Requirements

- Python 3.10+ and SQLite (Python's standard-library `sqlite3`).
- Node.js 20+ and npm for the frontend build.
- Linux desktop development: GTK 3, WebKitGTK 4.1, and PyGObject.
- Windows desktop development: Python 3.10+, Edge WebView2 Runtime, PowerShell 5.1 or newer for the installer, and packages in `requirements-windows.txt`.

Install npm dependencies once (requires package registry access):

```bash
npm ci
```

Run the API and frontend in separate terminals:

```bash
# Terminal 1
python3 server.py

# Terminal 2
npm run dev
```

Open the Vite URL printed in Terminal 2, usually `http://127.0.0.1:5173`. Vite proxies `/api` to the local service on port 8765 and presents the service's own Host and Origin, which the API requires.

### Build and tests

```bash
npm run build
npm test
python3 -m unittest discover -s tests -v
npm run typecheck
npm run lint
npm run format:check
python3 -m py_compile server.py desktop.py
sh -n install-user.sh uninstall-user.sh
```

The production UI is written to `dist/` and is committed; CI fails if it is out of date, so run `npm run build` and commit the result after any frontend change. Run `npm run format` to apply Prettier; TypeScript runs in strict mode and ESLint forbids explicit `any`. Tests cover countdowns, DST gaps/folds and calendar timezone keys; SQLite CRUD, schema migration, and the VANTA-to-CHRONYX data migration; notification failures, retries, catch-up, deduplication and rescheduling; HTTP input/Host/Origin validation; offline save/delete synchronization and rejected-change handling; import/export; and data paths. `desktop.py` runs on Fedora with GTK/WebKitGTK installed or on Windows with WebView2 and the Windows requirements installed. Native desktop testing is still required on Windows, Ubuntu, and Kali.

### Build the Fedora RPM

Build the frontend first. These commands work from a fresh clone named `CHRONYX` or another directory name:

```bash
npm run build
PROJECT_DIR=$(basename "$PWD")
PROJECT_PARENT=$(dirname "$PWD")
mkdir -p "$HOME/rpmbuild/SOURCES"
tar -C "$PROJECT_PARENT" --exclude='node_modules' --exclude='.git' \
  --exclude='__pycache__' --exclude='.venv' --exclude='*.rpm' \
  --transform="s,^${PROJECT_DIR}/,chronyx-1.0.0/," \
  -czf "$HOME/rpmbuild/SOURCES/chronyx-1.0.0.tar.gz" "$PROJECT_DIR"
rpmbuild -bb --define "_topdir $HOME/rpmbuild" packaging/chronyx.spec
```

The RPM is written under `~/rpmbuild/RPMS/noarch/`. To publish it, push a tag that starts with `v` (for example `git tag v1.0.0-9 && git push origin v1.0.0-9`); the release workflow runs the tests, builds the RPM, and attaches it with a `SHA256SUMS` file. The install commands above work only after a release exists. Increment `Release` and add a changelog entry in `packaging/chronyx.spec` for each package build, and update the file name in the install commands. The Fedora package requires `libnotify`, which provides `notify-send`.

## Troubleshooting

- **Linux window fails to start:** confirm the launching Python can import `gi`, GTK 3, and WebKit2 4.1: `python3 -c "import gi; gi.require_version('Gtk','3.0'); gi.require_version('WebKit2','4.1'); from gi.repository import Gtk, WebKit2"`.
- **Linux reminders do not appear:** install `libnotify` (Fedora) or `libnotify-bin` (Ubuntu/Kali), and launch CHRONYX from a logged-in graphical desktop session with its notification service active.
- **Port 8765 is occupied:** close an existing CHRONYX (or old VANTA) instance. If another service owns that port, CHRONYX exits with an error instead of opening the unrelated service.
- **Windows installer reports WebView2 missing:** install the Microsoft Edge WebView2 Evergreen Runtime, then rerun `install-windows.ps1`.
- **Offline changes are queued:** leave CHRONYX open; it retries synchronization when its local service responds again. If the service permanently rejects a queued change, CHRONYX discards it and shows a dismissible notice naming what was dropped.
- **My competitions are missing after upgrading from VANTA:** run `chronyx` from a terminal and look for the line `CHRONYX: copied your data from …`. Your old data is still in the old folder. If the new database is empty and you want to repeat the copy, close CHRONYX and delete the new database and the marker, then start it again. Linux: `rm ~/.local/share/chronyx/chronyx.sqlite3 ~/.local/share/chronyx/.migrated-from-vanta`. Windows: delete `chronyx.sqlite3` and `.migrated-from-vanta` in `%APPDATA%\CHRONYX`. This discards anything added in CHRONYX since the upgrade, so back it up first if you added events.

## Security assumptions

CHRONYX is a single-user desktop application. The local API binds to IPv4 loopback, validates the Host header on every request, and requires any Origin header on API requests to be exactly this service's own loopback origin (`http://127.0.0.1:8765` or `http://localhost:8765`). This protects reads and writes against DNS rebinding and against pages served from other localhost ports; native-shell requests without an Origin remain allowed. The server uses parameterized SQL, validates write payloads, and limits JSON request size. Authentication is intentionally absent because the service is only for the local desktop application. Any process running as the same OS user can access the database and local profile data. Do not expose port 8765 through a proxy or bind it to a public interface. To report a vulnerability, see [SECURITY.md](SECURITY.md).

## Continuous integration

GitHub Actions runs the test, lint, format, type-check, and build suite on Ubuntu 24.04 and Windows Server 2022 with Python 3.10, 3.13, and 3.14. The Ubuntu job checks GTK/WebKitGTK imports, checks that committed `dist/` matches the build, and validates the RPM recipe. The Windows job parses both PowerShell scripts. This CI does not simulate a logged-in desktop, Windows toast delivery, or Kali. Fedora desktop testing remains a local check, and native GUI validation is still needed on Windows, Ubuntu, and Kali. Tagged releases run the same checks before building and publishing the RPM.

## Technical overview

- **Frontend:** React, TypeScript (strict), Vite, Lucide icons, and CSS.
- **Desktop shell:** GTK 3/WebKitGTK 4.1 on Linux; pywebview/WebView2 on Windows.
- **Service:** Python standard-library HTTP server, bound to loopback only.
- **Persistence:** SQLite through Python `sqlite3`; platform-appropriate per-user data directory.
- **Notifications:** `notify-send` on Linux; `winotify` toasts on Windows.
- **Offline runtime:** Compiled frontend is bundled in `dist/`; no web APIs or cloud services are used.

| Path | Purpose |
| --- | --- |
| `src/main.tsx`, `src/App.tsx` | React entry point and application shell; feature components live beside them in `src/` |
| `src/style.css` | Responsive interface styling |
| `src/time.js`, `src/*-model.js`, `src/event-store.js`, `src/open-link.js`, `src/storage-migration.js` | Countdown, calendar, filter, import/export, offline-sync, link, and storage-migration logic (unit-tested) |
| `server.py` | SQLite API, data migration, and reminder scheduler |
| `desktop.py` | Linux GTK and Windows pywebview desktop shells |
| `dist/` | Compiled frontend served locally |
| `packaging/chronyx.spec` | Fedora RPM recipe |
| `docs/BRANDING.md` | The CHRONYX name and the VANTA migration notes |
| `tests/` | Countdown, persistence, migration, reminder, API, and desktop tests |

API routes: `GET /api/events`, `POST`/`PUT /api/events`, `POST /api/events/import`, `DELETE /api/events/<id>`, `GET /api/export.json`, `GET /api/export.csv`, `POST /api/open` (http/https links only), `GET /api/settings`, and `PATCH /api/settings`. Event times are stored as ISO 8601 instants and entered/displayed using each event's IANA time zone.

## License

MIT. See [LICENSE](LICENSE).
