#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APK="${1:-$ROOT/release/DexTilt-debug.apk}"
if ! command -v adb >/dev/null 2>&1; then
  echo "adb not found. Install Android platform-tools first." >&2
  echo "Homebrew option on macOS: brew install android-platform-tools" >&2
  exit 1
fi
if [ ! -f "$APK" ]; then
  echo "APK not found: $APK" >&2
  echo "Run ./scripts/build_android_debug_apk.sh first." >&2
  exit 2
fi

echo "DexTilt wireless install for Galaxy S21+"
echo "On the phone: Developer options -> Wireless debugging -> Pair device with pairing code."
read -r -p "Enter pairing address host:port shown by Android: " PAIR_ADDR
read -r -p "Enter 6-digit pairing code: " PAIR_CODE
if [ -n "$PAIR_ADDR" ] && [ -n "$PAIR_CODE" ]; then
  adb pair "$PAIR_ADDR" "$PAIR_CODE" || true
fi
read -r -p "Enter connect address host:port shown under Wireless debugging: " CONNECT_ADDR
adb connect "$CONNECT_ADDR"
adb devices
adb install -r "$APK"
adb shell monkey -p com.stinkyweasel.dextilt 1 || true
echo "DexTilt installed. Open the app if it did not launch automatically."
