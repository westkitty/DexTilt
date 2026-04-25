# DexTilt

DexTilt turns an Android phone into a local motion-based command object for a Mac.

The v1 goal is simple: pair an Android phone with a Mac, send authenticated local command IDs, and open ChatGPT in the Mac default browser after a trained face-down gesture or a manual fallback button.

DexTilt is not a Mac unlock tool. It does not store Mac passwords, type passwords, approve security prompts, bypass FileVault, replace Touch ID, or use GPT/OpenAI at runtime.

## Quick start snapshot

1. Set up and run the Mac receiver:

   ```sh
   cd ~/Projects/DexTilt/mac_receiver
   ./scripts/setup.sh
   ./scripts/run.sh
   ```

2. Open the local dashboard:

   ```text
   http://127.0.0.1:47391/status
   ```

3. Build and install the Android debug APK:

   ```sh
   cd ~/Projects/DexTilt
   ./scripts/build_android_debug_apk.sh
   ./scripts/install_android_wireless.sh
   ```

4. Pair Android by scanning the Mac dashboard QR.
5. Test Health, Test Mac Notification, and Open ChatGPT from Android manual buttons.
6. Calibrate, train a face-down-start gesture, test confidence locally, then arm DexTilt.

Detailed steps live in `docs/setup_mac.md`, `docs/setup_android.md`, and `docs/test_plan.md`.

## Local-first stance

DexTilt has no account system, no telemetry, no cloud sync, no OpenAI API dependency, and no cloud command path. Runtime traffic is between the user's devices on the user's local or user-controlled network.

## Safety boundary

DexTilt is a post-login command layer. It only executes allowlisted Mac-side command IDs. The phone never sends raw shell commands.

## Current build status

- Mac receiver source is implemented and core tests pass in the sandbox.
- Android app source is implemented as a command-line Gradle project, but APK build is NOT RUN in the sandbox because Gradle/Android SDK/ADB are unavailable.
- `release/DexTilt-debug.apk` is created only after a successful local Android build.
