# CHRONYX — VANTA Competition Tracker

CHRONYX (the VANTA Competition Tracker) is an offline-first desktop app for tracking competitions, registration deadlines, and reminders. Its React interface runs in an embedded native webview; it does not launch Brave, Firefox, or another browser. Competition data and reminder delivery state are stored in SQLite on the current device.

## Features

- Track CTFs, hackathons, AI/ML events, robotics competitions, programming contests, scholarships, and other opportunities.
- Create, edit, duplicate, complete, and delete events; save descriptions, organisers, links, dates, deadlines, time zones, status, priority, and notes.
- Live start and deadline countdowns, dashboard summaries, upcoming events, and recent activity.
- Month, week, day, and agenda calendar views.
- Search and filter by category, status, and priority; sort by start date or registration deadline.
- Desktop reminders 7 days, 3 days, 1 day, or 1 hour before starts and registration deadlines; supports a custom hour offset and retries failed delivery.
- JSON backup/import, CSV export, and dark/light themes.
- A device-local profile picture shown in the workspace sidebar.

## Platform support and verification status

| Platform | Desktop view | Installation | Tested here |
| --- | --- | --- | --- |
| Fedora Linux 44 | GTK 3 + WebKitGTK 4.1 + PyGObject | RPM or per-user install | **Partially verified:** tests, GTK/WebKit imports, RPM build, and notifier package mapping passed; a live desktop notification and installed RPM launch were not exercised |
| Ubuntu 24.04 LTS or newer | GTK 3 + WebKitGTK 4.1 + PyGObject | Install native dependencies, then `./install-user.sh` | **Not verified:** package names checked against Ubuntu package metadata; no Ubuntu runtime was available |
| Kali Linux rolling | GTK 3 + WebKitGTK 4.1 + PyGObject | Install available Debian-based dependencies, then `./install-user.sh` | **Not verified:** no Kali runtime was available |
| Windows 10/11 | pywebview + Microsoft Edge WebView2 Runtime | `install-windows.ps1` | **Not verified:** APPDATA paths are covered by unit tests; PowerShell and a native Windows desktop were unavailable |

The frontend, countdown code, local API, and SQLite schema are shared. Native windows and notifications use platform runtimes. Package names and WebKitGTK versions vary by distribution; the RPM is Fedora-specific. Windows requires Python 3.10+ and the WebView2 Runtime. See Microsoft's [WebView2 deployment documentation](https://learn.microsoft.com/microsoft-edge/webview2/concepts/distribution) and pywebview's [installation guide](https://pywebview.flowrl.com/guide/installation.html).

## Install on Fedora

The repository includes `vanta-1.0.0-7.fc44.noarch.rpm`:

```bash
sudo dnf install ./vanta-1.0.0-7.fc44.noarch.rpm
```

If the machine is offline and GTK 3, WebKitGTK 4.1, Python, and PyGObject are already installed, skip repository refresh:

```bash
sudo dnf install --disablerepo='*' ./vanta-1.0.0-7.fc44.noarch.rpm
```

Launch **VANTA Competition Tracker** from the applications menu or run `vanta` in a terminal.
To uninstall the RPM, run `sudo dnf remove vanta`; this leaves per-user data under `~/.local/share/vanta` intact.

### User-level Linux install

After installing your distribution's native dependencies (below), run:

```bash
./install-user.sh
```

The script stages and checks the files before replacing `~/.local/lib/vanta`, creates `~/.local/bin/vanta`, and adds a desktop entry and icon. Competition data remains under `~/.local/share/vanta`. To remove the per-user app files and launcher while keeping user data, run `~/.local/lib/vanta/uninstall-user.sh`.

### Linux runtime dependencies

The Linux shell needs Python 3, GTK 3, WebKitGTK 4.1, PyGObject bindings for the same Python interpreter that launches CHRONYX, and IANA timezone data. `notify-send` is required for Linux desktop reminders (`libnotify` on Fedora, `libnotify-bin` on Debian-derived systems). Without it, event tracking still works and the reminder service records retryable failures.

For a source install on Fedora, install dependencies with `sudo dnf install python3 gtk3 webkit2gtk4.1 python3-gobject libnotify tzdata`. The Fedora RPM declares these requirements itself.

### Ubuntu

Ubuntu 24.04 LTS or newer provides the WebKitGTK 4.1 introspection package. Install dependencies and CHRONYX as your normal user:

```bash
sudo apt update
sudo apt install python3 python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1 libnotify-bin tzdata
./install-user.sh
```

Launch **VANTA Competition Tracker** from the applications menu or run `~/.local/bin/vanta`. The [Ubuntu package index](https://packages.ubuntu.com/noble/gir1.2-webkit2-4.1) lists WebKitGTK 4.1 for Noble (24.04 LTS). Earlier Ubuntu releases may only provide WebKitGTK 4.0, which this application does not use.

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

Windows requires Python 3.10+ and the Microsoft Edge WebView2 Runtime. VANTA uses WebView2 inside its own window; it does not open the Edge browser. The installer checks both prerequisites, stages files before replacing an old installation, and installs `pywebview`, `winotify`, and IANA timezone data in a private virtual environment. Setup needs internet or a configured local Python package index; runtime use is offline.

Open PowerShell in the repository folder and run:

```powershell
powershell -ExecutionPolicy Bypass -File .\install-windows.ps1
```

The script installs the app under `%LOCALAPPDATA%\Programs\VANTA` and creates Start menu shortcuts for launch and uninstall. Launch **VANTA Competition Tracker** from Start. Competition data is stored under `%APPDATA%\VANTA\vanta.sqlite3`. Windows notifications use toast notifications through `winotify`.

To uninstall, close VANTA and choose **Uninstall VANTA Competition Tracker** from Start, or run `%LOCALAPPDATA%\Programs\VANTA\uninstall-windows.ps1` in PowerShell. The app files and shortcuts are removed; `%APPDATA%\VANTA` is preserved so competition data remains available if you reinstall.

For a source checkout without installing a shortcut:

```powershell
python -m pip install -r requirements-windows.txt
python desktop.py
```

If the WebView2 Runtime is missing, install Microsoft's [Evergreen WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/), then launch VANTA again.

## First launch and daily use

1. Launch VANTA from the applications menu or Start menu.
2. Choose **Add competition**. Enter a name, start date/time, and valid IANA time zone, such as `Africa/Nairobi`.
3. Add optional category, organiser, description, end date, registration deadline, website, registration URL, status, priority, and personal notes.
4. Use the dashboard to watch the nearest start countdown. **All Competitions** provides search, filters, sorting, and event actions.
5. Use **Calendar** for Month, Week, Day, or Agenda. Select an entry to open its details.
6. In **Settings**, choose a profile picture, change the theme, configure reminders, export a JSON or CSV file, or import a JSON backup. The profile picture is saved locally on that device and is not included in competition exports.

To receive reminders, leave VANTA running in your desktop session. The scheduler checks once a minute and stores sent reminder keys in SQLite to avoid sending the same reminder twice. Linux needs a session notification bus and `notify-send`; Windows needs working Windows notifications. Completed and cancelled events do not generate reminders.

## Data, backups, and privacy

The default database locations are:

```text
Linux:   ${XDG_DATA_HOME:-$HOME/.local/share}/vanta/vanta.sqlite3
Windows: %APPDATA%\VANTA\vanta.sqlite3
```

SQLite stores competition records, reminder preferences, and notification delivery/retry state. Linux uses `${XDG_DATA_HOME:-$HOME/.local/share}/vanta/vanta.sqlite3`; Windows uses `%APPDATA%\VANTA\vanta.sqlite3`. Profile pictures and the offline write queue are held in the embedded webview's per-user browser storage, not in SQLite or competition JSON backups. VANTA's local API binds only to `127.0.0.1:8765`; it does not listen on LAN interfaces. API writes accept requests without an Origin header for the native desktop shell and otherwise require a loopback Origin. No cloud account or network access is needed after installation.

Use **Settings → Backup JSON** for a portable event backup and **Settings → Import JSON** to import/merge events. CSV export is for spreadsheets; it is not an import format. Back up the webview profile separately if you want to preserve the profile picture and queued offline edits. To back up the entire SQLite database, close VANTA and run on Linux:

JSON and CSV downloads are served by the local API with attachment filenames so the native webviews can handle saving them. JSON import validates every row, converts offset-free wall times in the event timezone, imports valid rows in one database transaction, and shows the exact invalid rows and reasons. CSV cells beginning with spreadsheet formula characters are prefixed to prevent formula execution when opened in spreadsheet software. Native download dialogs still need manual verification on each desktop shell.

```bash
sqlite3 "${XDG_DATA_HOME:-$HOME/.local/share}/vanta/vanta.sqlite3" \
  ".backup '$HOME/vanta-database-backup.sqlite3'"
```

On Windows, close VANTA and copy `%APPDATA%\VANTA\vanta.sqlite3` to your backup location. Uninstalling VANTA does not remove the database.

## Development

### Requirements

- Python 3.9+ and SQLite (Python's standard-library `sqlite3`).
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

Open the Vite URL printed in Terminal 2, usually `http://127.0.0.1:5173`. Vite proxies `/api` to the local service on port 8765.

### Build and tests

```bash
npm run build
npm test
python3 -m unittest discover -s tests -v
npx tsc --noEmit
python3 -m py_compile server.py desktop.py
sh -n install-user.sh uninstall-user.sh
```

The production UI is written to `dist/`. Tests cover countdowns, DST gaps/folds and calendar timezone keys; SQLite CRUD and schema migration; notification failures, retries, deduplication and rescheduling; HTTP input/origin validation; offline save/delete synchronization; and data paths. `desktop.py` runs on Fedora with GTK/WebKitGTK installed or on Windows with WebView2 and the Windows requirements installed. Native desktop testing is still required on Windows, Ubuntu, and Kali.

### Build the Fedora RPM

Build the frontend first. From the parent directory of this repository:

```bash
npm --prefix vanta run build
mkdir -p "$HOME/rpmbuild/SOURCES"
tar --exclude='vanta/node_modules' --exclude='vanta/.git' \
  --exclude='vanta/__pycache__' --exclude='vanta/tests/__pycache__' \
  --exclude='vanta/.venv' --exclude='vanta/*.rpm' \
  --transform='s,^vanta,vanta-1.0.0,' \
  -czf "$HOME/rpmbuild/SOURCES/vanta-1.0.0.tar.gz" vanta
rpmbuild -bb --define "_topdir $HOME/rpmbuild" vanta/packaging/vanta.spec
```

The RPM is written under `~/rpmbuild/RPMS/noarch/`. Increment `Release` and add a changelog entry in `packaging/vanta.spec` for each package build. The Fedora package requires `libnotify`, which provides `notify-send` on this Fedora build host.

## Troubleshooting

- **Linux window fails to start:** confirm the launching Python can import `gi`, GTK 3, and WebKit2 4.1: `python3 -c "import gi; gi.require_version('Gtk','3.0'); gi.require_version('WebKit2','4.1'); from gi.repository import Gtk, WebKit2"`.
- **Linux reminders do not appear:** install `libnotify` (Fedora) or `libnotify-bin` (Ubuntu/Kali), and launch VANTA from a logged-in graphical desktop session with its notification service active.
- **Port 8765 is occupied:** close an existing VANTA instance. If another service owns that port, VANTA exits with an error instead of opening the unrelated service.
- **Windows installer reports WebView2 missing:** install the Microsoft Edge WebView2 Evergreen Runtime, then rerun `install-windows.ps1`.
- **Offline changes are queued:** leave VANTA open; it retries synchronization when its local service responds again. Check the status message in the app before closing it.

## Security assumptions

CHRONYX is a single-user desktop application. The local API binds to IPv4 loopback, uses parameterized SQL, validates write payloads, limits JSON request size, rejects non-loopback browser Origins on writes, and does not expose authentication because it is not intended as a network server. Any process running as the same OS user can access the database and local profile data. Do not expose port 8765 through a proxy or bind it to a public interface.

## Continuous integration

GitHub Actions runs the test/build/type-check suite on Ubuntu 24.04 and Windows Server 2022 with Python 3.10 and 3.13. The Ubuntu job checks GTK/WebKitGTK imports and builds the RPM recipe; the Windows job parses both PowerShell scripts. This CI does not simulate a logged-in desktop, Windows toast delivery, or Kali. Fedora desktop testing remains a local check, and native GUI validation is still needed on Windows, Ubuntu, and Kali.

## Technical overview

- **Frontend:** React, TypeScript, Vite, Lucide icons, and CSS.
- **Desktop shell:** GTK 3/WebKitGTK 4.1 on Linux; pywebview/WebView2 on Windows.
- **Service:** Python standard-library HTTP server, bound to loopback only.
- **Persistence:** SQLite through Python `sqlite3`; platform-appropriate per-user data directory.
- **Notifications:** `notify-send` on Linux; `winotify` toasts on Windows.
- **Offline runtime:** Compiled frontend is bundled in `dist/`; no web APIs or cloud services are used.

| Path | Purpose |
| --- | --- |
| `src/main.tsx` | React application and views |
| `src/style.css` | Responsive interface styling |
| `src/time.js` | Countdown calculations |
| `server.py` | SQLite API and reminder scheduler |
| `desktop.py` | Linux GTK and Windows pywebview desktop shells |
| `dist/` | Compiled frontend served locally |
| `packaging/vanta.spec` | Fedora RPM recipe |
| `tests/` | Countdown, persistence, reminder, and data-path tests |

API routes: `GET /api/events`, `POST`/`PUT /api/events`, `DELETE /api/events/<id>`, `GET /api/settings`, and `PATCH /api/settings`. Event times are stored as ISO 8601 instants and entered/displayed using each event's IANA time zone.
