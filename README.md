# CHRONYX — VANTA Competition Tracker

A privacy-first local competition tracker designed for Linux. Events are stored in SQLite in `~/.local/share/vanta/vanta.sqlite3`. The Python service uses only the standard library; desktop notices use Fedora's `notify-send` when a session notification bus is available.

## Features

- Competition create, edit and delete; statuses, priorities, URLs, notes and time zones.
- Live second-by-second start countdown and deadline tracking.
- Month calendar, upcoming/deadline/completed lists, category filtering and search.
- JSON import and backup, CSV export, light/dark theme.
- SQLite persistence and a local reminder service for 7 day, 3 day, 1 day and 1 hour start/deadline notifications.
- Responsive, lightweight React interface and local-only API.

## Run

Requires Python 3.9+, GTK 3, WebKitGTK 4.1 and PyGObject for daily use. Install `vanta-1.0.0-4.fc44.noarch.rpm` with `sudo dnf install ./vanta-1.0.0-4.fc44.noarch.rpm`, or run `./install-user.sh` for a user-level install. Launch VANTA from the Fedora application menu. The local service displays the compiled UI in VANTA's own window and stores events in SQLite; browser storage is used only if the service is unavailable.

For development, run `npm install`, start `python3 server.py`, and run `npm run dev`. The Vite development server proxies `/api` to the local service. Build with `npm run build`.

## Fedora desktop integration

The RPM adds the launcher, desktop menu entry and icon. For a user install, run `./install-user.sh`; it places the app in `~/.local/share/vanta` and adds a menu launcher and icon.

## Data and backup

The SQLite file is under `$XDG_DATA_HOME/vanta/` or `~/.local/share/vanta/`. Use Settings → Backup JSON to create a portable backup; Settings → Import JSON restores an export. CSV export is provided for spreadsheets.

## Architecture

The UI is React, TypeScript and Vite, presented in its own GTK window using Fedora's WebKitGTK embedded view. VANTA does not launch or depend on Brave, Firefox, or another browser. The local Python service provides SQLite persistence and desktop notifications through `notify-send`; no cloud account or internet connection is used at runtime. The RPM uses Fedora's system GTK/WebKitGTK libraries rather than bundling a second browser engine. Reminders support 7 days, 3 days, 1 day, 1 hour and a custom hour offset for both start and registration deadline. Notification delivery needs a graphical session and notification daemon. Dates are stored as ISO instants and entered/displayed in each event's IANA time zone.
