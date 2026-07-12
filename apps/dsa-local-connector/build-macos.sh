#!/usr/bin/env bash
set -euo pipefail
(cd ../.. && python3 -m unittest tests.test_user_local_connector_v112)
python3 -m PyInstaller dsa-local-connector.spec --clean --noconfirm
arch="$(uname -m)"
if [[ "$arch" == "arm64" ]]; then suffix="arm64"; else suffix="x64"; fi
hdiutil create -volname "DSA Local Connector" -srcfolder dist/DSA-Local-Connector.app "dist/DSA-Local-Connector-macOS-${suffix}.dmg"
test -f "dist/DSA-Local-Connector-macOS-${suffix}.dmg"
mkdir -p ../../static/downloads
cp "dist/DSA-Local-Connector-macOS-${suffix}.dmg" "../../static/downloads/DSA-Local-Connector-macOS-${suffix}.dmg"
