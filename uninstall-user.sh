#!/bin/sh
set -eu

APPDIR="$HOME/.local/lib/chronyx"
BIN="$HOME/.local/bin/chronyx"
ENTRY="$HOME/.local/share/applications/chronyx.desktop"
ICON="$HOME/.local/share/icons/hicolor/scalable/apps/chronyx.svg"

rm -rf -- "$APPDIR" "$HOME/.local/lib/vanta"
rm -f -- "$BIN" "$ENTRY" "$ICON" "$HOME/.local/bin/vanta" "$HOME/.local/share/applications/vanta.desktop" "$HOME/.local/share/icons/hicolor/scalable/apps/vanta.svg"
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$HOME/.local/share/applications" || true
echo 'CHRONYX application files were removed. Your local competition database and webview profile were left in place.'
