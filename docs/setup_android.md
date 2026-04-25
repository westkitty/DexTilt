# Android Setup

DexTilt targets package `com.stinkyweasel.dextilt` and is designed for the Galaxy S21+ SM-G996U without requiring Android Studio.

## What this project uses

- Kotlin + Jetpack Compose.
- Android Gradle Plugin 8.13.0.
- Kotlin / Compose compiler plugin 2.3.20.
- Compose BOM 2026.04.00.
- Compile SDK 36, target SDK 36, min SDK 26.
- ZXing Android Embedded for QR scanning.

The build script intentionally avoids emulator images and Android Studio.

## Build debug APK

```sh
cd ~/Projects/DexTilt
./scripts/build_android_debug_apk.sh
```

The script checks disk space, uses `ANDROID_HOME` or `~/Library/Android/sdk`, installs only command-line SDK components if `sdkmanager` is available, and then runs Gradle.

Expected APK path:

```text
android_app/app/build/outputs/apk/debug/app-debug.apk
```

If successful, it is copied to:

```text
release/DexTilt-debug.apk
```

## Smallest tooling install path on macOS

If the build script reports missing tools:

```sh
brew install gradle android-platform-tools
brew install --cask android-commandlinetools
sdkmanager "platform-tools" "platforms;android-36" "build-tools;36.0.0"
```

Do not install Android emulator system images for DexTilt v1.

## Wireless debugging install

1. On the Galaxy S21+, open Settings.
2. Enable Developer options if needed.
3. Enable Wireless debugging.
4. Tap Pair device with pairing code.
5. Run:

```sh
cd ~/Projects/DexTilt
./scripts/install_android_wireless.sh
```

The script prompts for the pairing address, pairing code, and connect address shown on the phone. It then installs `release/DexTilt-debug.apk` and tries to launch DexTilt.

## Pair DexTilt

1. Start the Mac receiver.
2. Open the Mac dashboard: `http://127.0.0.1:47391/status`.
3. In Android DexTilt, choose Scan Mac QR.
4. Scan the QR shown on the Mac.
5. Test Health, Test Mac Notification, and Open ChatGPT.
6. Run calibration.
7. Train and test a gesture locally.
8. Assign/use the saved gesture for `open_gpt_default_browser`.

## Android permissions

DexTilt requests only: Internet, network state, vibration, and camera for QR scanning. It does not request location or Bluetooth in v1.
