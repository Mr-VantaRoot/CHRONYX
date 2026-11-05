#!/bin/sh
set -eu

APPDIR="$HOME/.local/lib/vanta"
BIN="$HOME/.local/bin/vanta"
ENTRY="$HOME/.local/share/applications/vanta.desktop"
ICON="$HOME/.local/share/icons/hicolor/scalable/apps/vanta.svg"

rm -rf -- "$APPDIR"
rm -f -- "$BIN" "$ENTRY" "$ICON"
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$HOME/.local/share/applications" || true
echo 'VANTA application files were removed. Your local competition database and webview profile were left in place.'
