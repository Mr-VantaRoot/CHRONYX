# CHRONYX — VANTA Competition Tracker

VANTA is an offline-first desktop app for tracking competitions, registration deadlines, and reminders. It uses a local SQLite database and opens its interface in an embedded native webview; it does not launch Brave, Firefox, or another browser.

## Features

- Track CTFs, hackathons, AI/ML events, robotics competitions, programming contests, scholarships, and other opportunities.
- Create, edit, duplicate, complete, and delete events; save descriptions, organisers, links, dates, deadlines, time zones, status, priority, and notes.
- Live start and deadline countdowns, dashboard summaries, upcoming events, and recent activity.
- Month, week, day, and agenda calendar views.
- Search and filter by category, status, and priority; sort by start date or registration deadline.
- Fedora desktop reminders 7 days, 3 days, 1 day, or 1 hour before starts and registration deadlines; supports a custom hour offset.
- JSON backup/import, CSV export, and dark/light themes.
- A device-local profile picture shown in the workspace sidebar.

## Platform support and test status

| Platform | Desktop view | Installation | Tested here |
| --- | --- | --- | --- |
| Fedora Linux | GTK 3 + WebKitGTK 4.1 | Fedora RPM or user install | Yes: frontend build, Python tests, countdown tests, GTK/WebKit imports, and RPM build |
| Other Linux distributions | GTK 3 + WebKitGTK 4.1 + PyGObject | Install the distribution's matching runtime packages, then use the source launcher | Compatibility is conditional on those packages; not every distribution was available for testing |
| Windows 10/11 | pywebview + Microsoft Edge WebView2 Runtime | `install-windows.ps1` | Windows branch and APPDATA path have unit/static checks; a Windows machine was not available for a native GUI run |

VANTA's React UI, countdown code, and SQLite service are portable. The native window and notification integration use each operating system's runtime. Linux distribution package names and availability vary; the Fedora RPM is Fedora-specific. Windows needs Python and the WebView2 Runtime. Microsoft's WebView2 distribution options are described in the [WebView2 documentation](https://learn.microsoft.com/microsoft-edge/webview2/concepts/distribution). pywebview's supported native backends are described in its [installation guide](https://pywebview.flowrl.com/guide/installation.html).

## Install on Fedora

The repository includes `vanta-1.0.0-6.fc44.noarch.rpm`:

```bash
sudo dnf install ./vanta-1.0.0-6.fc44.noarch.rpm
```

If the machine is offline and GTK 3, WebKitGTK 4.1, Python, and PyGObject are already installed, skip repository refresh:

```bash
sudo dnf install --disablerepo='*' ./vanta-1.0.0-6.fc44.noarch.rpm
```

Launch **VANTA Competition Tracker** from the applications menu or run `vanta` in a terminal.

### User-level Linux install

On Linux distributions with Python 3, GTK 3, WebKitGTK 4.1, and PyGObject installed, run:

```bash
./install-user.sh
```

The script installs app files in `~/.local/lib/vanta`, creates `~/.local/bin/vanta`, and adds a Start-menu equivalent (applications menu) entry and icon. It leaves the database in `~/.local/share/vanta` intact. This script does not install platform libraries; use your distribution's package manager for those.

### Linux runtime dependencies

The desktop shell requires GTK 3, WebKitGTK 4.1, and PyGObject for the Python interpreter used to launch VANTA. Package names differ by distribution. The Fedora RPM declares Fedora's package names; on other distributions, install the matching GTK 3, WebKitGTK 4.1 typelib/bindings, and Python GObject bindings using that distribution's package manager.

## Install on Windows

Windows requires Python 3.10+ and the Microsoft Edge WebView2 Runtime. VANTA uses WebView2 inside its own window; it does not open the Edge browser. The first setup installs the Python packages `pywebview` and `winotify` into a private virtual environment, so internet access is needed during setup unless those packages are available from a configured local Python package index. Runtime use is offline.

Open PowerShell in the repository folder and run:

```powershell
powershell -ExecutionPolicy Bypass -File .\install-windows.ps1
```

The script installs the app under `%LOCALAPPDATA%\Programs\VANTA` and creates a Start menu shortcut. Launch **VANTA Competition Tracker** from Start. Competition data is stored under `%APPDATA%\VANTA\vanta.sqlite3`. Windows notifications use toast notifications through `winotify`.

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

SQLite stores competition records, reminder preferences, and sent-notification records. VANTA's local API binds to `127.0.0.1:8765`. No cloud account or network access is needed after installation.

Use **Settings → Backup JSON** for a portable event backup and **Settings → Import JSON** to import/merge events. CSV export is for spreadsheets; it is not an import format. To back up the entire SQLite database, close VANTA and run on Linux:

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
- Windows desktop development: Python 3.10+, Edge WebView2 Runtime, and packages in `requirements-windows.txt`.

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
```

The production UI is written to `dist/`. Node tests cover countdown boundaries, expiration, and invalid dates. Python tests cover SQLite CRUD/persistence, notification deduplication, and Linux/Windows data-directory selection. Run `python3 desktop.py` on Linux with GTK/WebKitGTK installed, or on Windows with WebView2 and the Windows requirements installed.

### Build the Fedora RPM

Build the frontend first. From the parent directory of this repository:

```bash
npm --prefix vanta run build
mkdir -p "$HOME/rpmbuild/SOURCES"
tar --exclude='vanta/node_modules' --exclude='vanta/.git' \
  --exclude='vanta/__pycache__' --exclude='vanta/tests/__pycache__' \
  --exclude='vanta/*.rpm' \
  --transform='s,^vanta,vanta-1.0.0,' \
  -czf "$HOME/rpmbuild/SOURCES/vanta-1.0.0.tar.gz" vanta
rpmbuild -bb --define "_topdir $HOME/rpmbuild" vanta/packaging/vanta.spec
```

The RPM is written under `~/rpmbuild/RPMS/noarch/`. Increment `Release` and add a changelog entry in `packaging/vanta.spec` for each new package build.

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
