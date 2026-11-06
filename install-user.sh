#!/bin/sh
set -eu

BASE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
APPDIR="$HOME/.local/lib/chronyx"
LIBDIR=$(dirname -- "$APPDIR")
BINDIR="$HOME/.local/bin"
DATADIR="$HOME/.local/share"
APP_ENTRY="$DATADIR/applications/chronyx.desktop"
ICON="$DATADIR/icons/hicolor/scalable/apps/chronyx.svg"

if ! command -v python3 >/dev/null 2>&1; then
  echo 'Python 3 is required. Install it with your distribution package manager.' >&2
  exit 1
fi
if ! python3 - <<'PY'
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.1')
from gi.repository import Gtk, WebKit2
PY
then
  echo 'GTK 3, WebKitGTK 4.1, and Python GObject bindings are required. Install those runtime packages for your distribution, then rerun this installer.' >&2
  exit 1
fi
if ! command -v notify-send >/dev/null 2>&1; then
  echo 'Warning: notify-send is missing; desktop reminders will not be available until it is installed.' >&2
fi

mkdir -p "$LIBDIR" "$BINDIR" "$DATADIR/applications" "$DATADIR/icons/hicolor/scalable/apps"
STAGE=$(mktemp -d "$LIBDIR/.chronyx-stage.XXXXXX")
ARCHIVE=$(mktemp "$LIBDIR/.chronyx-source.XXXXXX.tar")
BACKUP="$LIBDIR/.chronyx-backup.$$"
BIN_TMP="$BINDIR/.chronyx.$$"
ENTRY_TMP="$APP_ENTRY.$$"
ICON_TMP="$ICON.$$"
OLD_MOVED=0
NEW_MOVED=0
COMMITTED=0
cleanup() {
  rm -rf -- "$STAGE" "$ARCHIVE" "$BIN_TMP" "$ENTRY_TMP" "$ICON_TMP"
  if [ "$COMMITTED" -eq 0 ]; then
    if [ "$NEW_MOVED" -eq 1 ]; then rm -rf -- "$APPDIR"; fi
    if [ "$OLD_MOVED" -eq 1 ] && [ -d "$BACKUP" ]; then mv -- "$BACKUP" "$APPDIR" || true; fi
  fi
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM

tar -C "$BASE" --exclude='node_modules' --exclude='.git' --exclude='__pycache__' \
  --exclude='.venv' --exclude='*.rpm' --exclude='*.sqlite3*' -cf "$ARCHIVE" .
tar -C "$STAGE" -xf "$ARCHIVE"

cat > "$BIN_TMP" <<EOF
#!/bin/sh
exec "$APPDIR/chronyx" "\$@"
EOF
chmod 0755 "$BIN_TMP"
cp "$BASE/public/chronyx.svg" "$ICON_TMP"
EXEC_PATH=$(printf '%s' "$BINDIR/chronyx" | sed 's/\\/\\\\/g; s/"/\\"/g; s/%/%%/g')
cat > "$ENTRY_TMP" <<EOF
[Desktop Entry]
Name=CHRONYX Competition Tracker
Comment=Track competitions, deadlines and reminders
Exec="$EXEC_PATH"
Icon=chronyx
Terminal=false
Type=Application
Categories=Office;
StartupNotify=true
EOF

if [ -e "$APPDIR" ]; then mv -- "$APPDIR" "$BACKUP"; OLD_MOVED=1; fi
mv -- "$STAGE" "$APPDIR"
NEW_MOVED=1
mv -f -- "$BIN_TMP" "$BINDIR/chronyx"
mv -f -- "$ENTRY_TMP" "$APP_ENTRY"
mv -f -- "$ICON_TMP" "$ICON"
rm -rf -- "$ARCHIVE"
COMMITTED=1
if [ -d "$BACKUP" ]; then rm -rf -- "$BACKUP" || echo "Warning: old application files remain at $BACKUP" >&2; fi
# Remove the files of earlier releases that were named VANTA (data is kept and migrated on first launch).
rm -rf -- "$LIBDIR/vanta"
rm -f -- "$BINDIR/vanta" "$DATADIR/applications/vanta.desktop" "$DATADIR/icons/hicolor/scalable/apps/vanta.svg"
trap - EXIT HUP INT TERM
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$DATADIR/applications" || true
echo 'Installed CHRONYX for this user. Launch it from the applications menu or run ~/.local/bin/chronyx.'
echo 'If you used VANTA before, CHRONYX copies your competitions the first time it starts; the old data folder is left untouched.'
