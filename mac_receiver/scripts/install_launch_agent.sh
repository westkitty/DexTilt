#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/python ]; then
  echo "Missing .venv/bin/python. Run ./scripts/setup.sh first." >&2
  exit 1
fi
PLIST="$HOME/Library/LaunchAgents/com.stinkyweasel.dextilt.receiver.plist"
mkdir -p "$HOME/Library/LaunchAgents" "$HOME/.dextilt/logs"
PYTHON_PATH="$(pwd)/.venv/bin/python"
WORKDIR="$(pwd)"
cat > "$PLIST" <<EOF2
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.stinkyweasel.dextilt.receiver</string>
  <key>WorkingDirectory</key><string>${WORKDIR}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${PYTHON_PATH}</string>
    <string>-m</string>
    <string>dextilt_receiver</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><false/>
  <key>StandardOutPath</key><string>${HOME}/.dextilt/logs/launch_agent.out.log</string>
  <key>StandardErrorPath</key><string>${HOME}/.dextilt/logs/launch_agent.err.log</string>
</dict>
</plist>
EOF2
launchctl unload "$PLIST" >/dev/null 2>&1 || true
launchctl load "$PLIST"
echo "Installed DexTilt LaunchAgent: $PLIST"
echo "Dashboard: http://127.0.0.1:47391/status"
