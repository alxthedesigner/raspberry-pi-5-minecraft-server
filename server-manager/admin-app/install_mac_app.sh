#!/bin/bash
# Installs (or updates) "Minecraft Server Manager.app" in /Applications.
#
# macOS blocks apps opened from Finder/Launchpad from reading the Documents folder,
# so the app runs a copy of admin-app kept in ~/Library/Application Support.
# Re-run this script after changing the app's code to update that copy.
# Settings (connection, API key, mod packages) are stored by macOS separately and are kept.
set -e

SRC="$(cd "$(dirname "$0")" && pwd)"        # this admin-app folder
ROOT="$(dirname "$SRC")"
DEST="$HOME/Library/Application Support/Minecraft Server Manager"
APP="/Applications/Minecraft Server Manager.app"

if [ ! -x "$SRC/venv/bin/python" ]; then
  echo "Create the app's venv first: cd \"$SRC\" && python3 -m venv venv && venv/bin/pip install -r requirements.txt"
  exit 1
fi

echo "Copying app to: $DEST"
mkdir -p "$DEST/player-portal/templates"
rsync -a --delete --exclude '__pycache__' --exclude '*.bak-*' --exclude 'install_mac_app.sh' "$SRC/" "$DEST/admin-app/"
# The Instructions tab shows the player portal's join steps
cp "$ROOT/player-portal/templates/index.html" "$DEST/player-portal/templates/index.html"

echo "Building: $APP"
TMP="$(mktemp -d)"
mkdir -p "$TMP/AppIcon.iconset"
for sz in 16 32 128 256 512; do
  sips -z $sz $sz "$SRC/assets/app_icon.png" --out "$TMP/AppIcon.iconset/icon_${sz}x${sz}.png" >/dev/null
  sips -z $((sz * 2)) $((sz * 2)) "$SRC/assets/app_icon.png" --out "$TMP/AppIcon.iconset/icon_${sz}x${sz}@2x.png" >/dev/null
done
iconutil -c icns "$TMP/AppIcon.iconset" -o "$TMP/AppIcon.icns"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$TMP/AppIcon.icns" "$APP/Contents/Resources/AppIcon.icns"
rm -rf "$TMP"

cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Minecraft Server Manager</string>
  <key>CFBundleDisplayName</key><string>Minecraft Server Manager</string>
  <key>CFBundleIdentifier</key><string>local.minecraft-server-manager</string>
  <key>CFBundleExecutable</key><string>launcher</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST

cat > "$APP/Contents/MacOS/launcher" <<'LAUNCH'
#!/bin/bash
APP_DIR="$HOME/Library/Application Support/Minecraft Server Manager/admin-app"
LOG="$HOME/Library/Logs/Minecraft Server Manager.log"
if [ ! -x "$APP_DIR/venv/bin/python" ]; then
  osascript -e 'display alert "Minecraft Server Manager" message "The app files are missing. Run admin-app/install_mac_app.sh again."'
  exit 1
fi
cd "$APP_DIR"
echo "--- $(date) starting" >> "$LOG"
# Run natively on Apple Silicon (the app's Qt libraries are arm64-only); plain exec on Intel Macs
if [ "$(sysctl -n hw.optional.arm64 2>/dev/null)" = "1" ]; then
  exec arch -arm64 "$APP_DIR/venv/bin/python" main.py >> "$LOG" 2>&1
fi
exec "$APP_DIR/venv/bin/python" main.py >> "$LOG" 2>&1
LAUNCH
chmod +x "$APP/Contents/MacOS/launcher"

codesign --force --deep -s - "$APP" >/dev/null 2>&1 || true
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP" >/dev/null 2>&1 || true
echo "Done. Open \"Minecraft Server Manager\" from Applications, Launchpad or Spotlight."
