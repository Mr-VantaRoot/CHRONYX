#!/bin/sh
set -eu
BASE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
APPDIR="$HOME/.local/lib/vanta"
rm -rf "$APPDIR"
mkdir -p "$APPDIR" "$HOME/.local/bin" "$HOME/.local/share/icons/hicolor/scalable/apps" "$HOME/.local/share/applications"
tar -C "$BASE" --exclude='*node_modules*' --exclude='*/.git' --exclude='*__pycache__*' --exclude='*.rpm' -cf - . | tar -C "$APPDIR" -xf -
cat > "$HOME/.local/bin/vanta" <<EOF
#!/bin/sh
exec "$APPDIR/vanta" "\$@"
EOF
chmod +x "$HOME/.local/bin/vanta"
sed "s|/home/USER/.local/bin/vanta|$HOME/.local/bin/vanta|" "$BASE/packaging/vanta.desktop" > "$HOME/.local/share/applications/vanta.desktop"
cp "$BASE/public/vanta.svg" "$HOME/.local/share/icons/hicolor/scalable/apps/vanta.svg"
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$HOME/.local/share/applications" || true
echo 'Installed VANTA. Launch it from your application menu or run ~/.local/bin/vanta.'
