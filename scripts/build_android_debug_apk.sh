#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/android_app"
RELEASE="$ROOT/release"
mkdir -p "$RELEASE"
echo "DexTilt Android debug APK build"
echo "Project: $ROOT"
echo "Disk space:"
df -h "$ROOT" || true

if [ ! -d "$APP" ]; then
  echo "Missing android_app directory." >&2
  exit 1
fi

SDK="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-$HOME/Library/Android/sdk}}"
export ANDROID_HOME="$SDK"
export ANDROID_SDK_ROOT="$SDK"
mkdir -p "$SDK"

if command -v sdkmanager >/dev/null 2>&1; then
  echo "sdkmanager found. Installing only command-line build components, no emulator images."
  yes | sdkmanager --licenses >/dev/null || true
  sdkmanager "platform-tools" "platforms;android-36" "build-tools;36.0.0"
else
  echo "sdkmanager not found. Install Android command-line tools, then rerun."
  echo "Homebrew option on macOS: brew install --cask android-commandlinetools"
  echo "Then run: sdkmanager \"platform-tools\" \"platforms;android-36\" \"build-tools;36.0.0\""
fi

cd "$APP"
if [ -x ./gradlew ]; then
  GRADLE=./gradlew
elif command -v gradle >/dev/null 2>&1; then
  GRADLE=gradle
else
  echo "Gradle was not found and no Gradle wrapper is present." >&2
  echo "Smallest next step: brew install gradle, then rerun this script." >&2
  echo "This does not require Android Studio or emulator images." >&2
  exit 2
fi

"$GRADLE" :app:assembleDebug
APK="$APP/app/build/outputs/apk/debug/app-debug.apk"
if [ ! -f "$APK" ]; then
  echo "Expected APK was not created: $APK" >&2
  find "$APP/app/build/outputs" -name '*.apk' -print 2>/dev/null || true
  exit 3
fi
cp "$APK" "$RELEASE/DexTilt-debug.apk"
echo "Built APK: $APK"
echo "Copied release APK: $RELEASE/DexTilt-debug.apk"
