#!/usr/bin/env bash
set -euo pipefail
PORT="${DEXTILT_PORT:-47391}"
OUT="${1:-debug_bundle}"
mkdir -p "$OUT"
{
  echo "DexTilt Mac debug bundle"
  date -u
  echo
  echo "Python:"
  python3 --version 2>&1 || true
  echo
  echo "Receiver health:"
  curl -fsS "http://127.0.0.1:${PORT}/health" 2>&1 || true
  echo
  echo "Receiver status:"
  curl -fsS "http://127.0.0.1:${PORT}/api/status" 2>&1 || true
  echo
  echo "Port listening:"
  lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN 2>&1 || true
  echo
  echo "Default browser hint:"
  defaults read com.apple.LaunchServices/com.apple.launchservices.secure LSHandlers 2>/dev/null | grep -A2 'https' | head -n 40 || true
  echo
  echo "Tailscale:"
  command -v tailscale >/dev/null 2>&1 && tailscale status 2>&1 || echo "tailscale not found"
  echo
  echo "Recent logs (redacted by receiver):"
  curl -fsS "http://127.0.0.1:${PORT}/logs?limit=50" 2>&1 || true
} > "$OUT/dextilt_mac_debug.txt"
echo "Wrote $OUT/dextilt_mac_debug.txt"
