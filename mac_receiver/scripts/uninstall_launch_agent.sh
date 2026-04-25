#!/usr/bin/env bash
set -euo pipefail
PLIST="$HOME/Library/LaunchAgents/com.stinkyweasel.dextilt.receiver.plist"
if [ -f "$PLIST" ]; then
  launchctl unload "$PLIST" >/dev/null 2>&1 || true
  rm -f "$PLIST"
  echo "Removed $PLIST"
else
  echo "DexTilt LaunchAgent was not installed."
fi
