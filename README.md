# CHRONYX — VANTA Competition Tracker

VANTA is an offline-first Fedora desktop app for tracking competitions, registration deadlines, and event reminders. It opens in its own GTK window and does not launch a web browser. Competition data is kept in a local SQLite database.

## Features

- Track CTFs, hackathons, AI/ML events, robotics competitions, programming contests, scholarships, and other opportunities.
- Create, view, edit, duplicate, complete, and delete competitions.
- Save descriptions, organisers, event and registration URLs, start/end dates, registration deadlines, IANA time zones, status, priority, and personal notes.
- See live countdowns, dashboard summaries, recent activity, and upcoming events.
- Browse a month, week, day, or agenda calendar.
- Search and filter competitions by category, status, and priority; sort by start date or registration deadline.
- Receive Fedora desktop reminders 7 days, 3 days, 1 day, or 1 hour before an event or registration deadline. A custom reminder offset is also available.
- Export JSON backups and CSV files; import VANTA JSON backups.
- Choose a dark or light theme.

## Install on Fedora

The repository includes the Fedora 44 RPM `vanta-1.0.0-4.fc44.noarch.rpm`. From the repository directory, install it with:

```bash
sudo dnf install ./vanta-1.0.0-4.fc44.noarch.rpm
```

If your Fedora installation already has VANTA's GTK, WebKitGTK, Python, and PyGObject dependencies and you want DNF to skip refreshing repositories, use:

```bash
sudo dnf install --disablerepo='*' ./vanta-1.0.0-4.fc44.noarch.rpm
```

After installation, open **VANTA Competition Tracker** from the applications menu, or run:

```bash
vanta
```

The RPM installs a launcher, desktop entry, and application icon. The embedded view uses Fedora's GTK 3 and WebKitGTK 4.1 libraries; it does not require Brave, Firefox, or another browser.

### Install without system-wide RPM installation

From the checked-out repository, run:

```bash
./install-user.sh
```

This installs the app files under `~/.local/lib/vanta`, creates a launcher at `~/.local/bin/vanta`, and adds an application menu entry and icon for the current user. It does not remove the SQLite database in `~/.local/share/vanta`.

## First launch and everyday use

1. Launch VANTA from the applications menu or run `vanta` in a terminal.
2. Select **Add competition** and enter at least a name, start date/time, and valid IANA time zone (for example, `Africa/Nairobi`).
3. Add an optional registration deadline, end date, URLs, notes, category, registration status, and priority, then save.
4. Use the dashboard countdown to follow the nearest event. Select **All Competitions** to search, filter, sort, edit, duplicate, complete, or delete an event. Deletion asks for confirmation.
5. Open **Calendar** to switch among Month, Week, Day, and Agenda views. Select a calendar entry to open its details.
6. In **Settings**, change the theme, choose reminder times, create a JSON backup, export CSV, or import a JSON backup.

Reminders cover both competition starts and registration deadlines. VANTA checks once a minute and records sent reminder keys in SQLite to prevent duplicate notices. The VANTA desktop process must remain running for reminders to be checked; notification delivery also requires a Fedora graphical session and `notify-send`.

## Data, backups, and privacy

The SQLite database is stored at:

```text
${XDG_DATA_HOME:-$HOME/.local/share}/vanta/vanta.sqlite3
```

It contains competition records, reminder preferences, and sent-notification records. VANTA serves its local interface and API on `127.0.0.1:8765`; it does not use a cloud service or require an internet connection after installation.

Use **Settings → Backup JSON** for a portable backup and **Settings → Import JSON** to restore/merge events from one. CSV export is intended for spreadsheets and is not an import format. To make a full SQLite backup from a terminal, close VANTA and run:

```bash
sqlite3 "${XDG_DATA_HOME:-$HOME/.local/share}/vanta/vanta.sqlite3" \
  ".backup '$HOME/vanta-database-backup.sqlite3'"
```

Uninstalling the RPM or user-level app files does not delete the database. To remove user-level application files, remove `~/.local/lib/vanta`, `~/.local/bin/vanta`, `~/.local/share/applications/vanta.desktop`, and `~/.local/share/icons/hicolor/scalable/apps/vanta.svg` yourself. Keep or remove `~/.local/share/vanta` separately depending on whether you want to retain your data.

## Development

### Requirements

- Fedora Linux with Python 3.9 or newer, GTK 3, WebKitGTK 4.1, and PyGObject for the desktop window.
- Node.js 20 or newer and npm for the React/Vite frontend and asset build.
- SQLite is accessed through Python's standard-library `sqlite3` module.

### Run the development app

Install the frontend dependencies once (this step needs npm registry access):

```bash
npm ci
```

Use two terminals. In the first, start the local SQLite API service:

```bash
python3 server.py
```

In the second, start Vite:

```bash
npm run dev
```

Open the Vite URL printed in the terminal, usually `http://127.0.0.1:5173`. Its `/api` requests are proxied to the service at `http://127.0.0.1:8765`.

### Build, test, and launch the desktop window

```bash
npm run build
npm test
python3 -m unittest discover -s tests -v
python3 desktop.py
```

The frontend build is written to `dist/`. The Node tests cover countdown calculations, including expired and invalid dates. The Python tests cover SQLite CRUD/persistence and notification deduplication.

### Build an RPM

Build the frontend first, then create the source archive expected by the RPM spec and build the package:

```bash
npm run build
mkdir -p "$HOME/rpmbuild/SOURCES"
tar --exclude='vanta/node_modules' --exclude='vanta/.git' \
  --exclude='vanta/__pycache__' --exclude='vanta/tests/__pycache__' \
  --exclude='vanta/*.rpm' \
  --transform='s,^vanta,vanta-1.0.0,' \
  -czf "$HOME/rpmbuild/SOURCES/vanta-1.0.0.tar.gz" -C .. vanta
rpmbuild -bb --define "_topdir $HOME/rpmbuild" packaging/vanta.spec
```

The RPM is written under `~/rpmbuild/RPMS/noarch/`. Update the `Release` and changelog in `packaging/vanta.spec` before producing a subsequent package release.

## Technical overview

- **Frontend:** React, TypeScript, Vite, Lucide icons, and CSS.
- **Desktop shell:** Python GTK 3 application with an embedded WebKitGTK 4.1 view; single-user local desktop process.
- **Local service:** Python standard-library `http.server`, bound to loopback only.
- **Persistence:** SQLite via Python `sqlite3`; database location follows `XDG_DATA_HOME`.
- **Notifications:** Fedora `notify-send`, when available in a graphical session.
- **Offline operation:** The built frontend is bundled in `dist/`; runtime has no external API or cloud dependency.

Key files:

| Path | Purpose |
| --- | --- |
| `src/main.tsx` | React application and views |
| `src/style.css` | Application styling and responsive layout |
| `src/time.js` | Countdown calculation |
| `server.py` | SQLite API and reminder scheduler |
| `desktop.py` | GTK/WebKitGTK desktop window |
| `dist/` | Compiled offline frontend served by the desktop app |
| `packaging/vanta.spec` | Fedora RPM recipe |
| `tests/` | Countdown and service tests |

The HTTP API currently provides `GET /api/events`, `POST`/`PUT /api/events`, `DELETE /api/events/<id>`, `GET /api/settings`, and `PATCH /api/settings`. Event timestamps are stored as ISO 8601 instants; the UI converts date/time entry using each event's IANA time zone.
