# DexTilt Project Bible

## Bootstrap Prompt for Successor AI
Read this file before making substantive DexTilt changes. Treat it as the authoritative ledger for project state, decisions, commands, tests, known limitations, and next steps. Append new entries only. Do not rewrite, delete, reorder, or silently normalize previous entries. If an earlier entry is wrong, append a correction entry that clearly supersedes it.

## Project Goal
DexTilt is a local Android-to-macOS gesture command system. A paired Android phone recognizes local motion gestures and sends authenticated command IDs to a Mac receiver. The v1 proof path is: trained face-down phone gesture -> signed local command -> Mac opens https://chatgpt.com/ in the default browser.

## Scope
v1 builds a native Android app and a lightweight Python FastAPI Mac receiver. The receiver runs after login, exposes a local dashboard, pairs by QR token, verifies HMAC-signed command messages, maps command IDs to allowlisted actions, logs events, and shows visible confirmation. Android handles pairing, manual command testing, sensor checks, calibration, gesture recording, confidence scoring, arming, and local storage.

## Constraints
- Exact project name: DexTilt.
- Android package name: com.stinkyweasel.dextilt.
- Mac receiver display name: DexTilt Mac Receiver.
- Default receiver port: 47391.
- Command IDs and gesture IDs use snake_case.
- Protocol IDs use dotted lowercase, for example dextilt.v1.
- DexTilt is a post-login local command layer. It must not unlock macOS, store or transmit Mac passwords, enter passwords, approve privileged prompts, bypass security, or impersonate Touch ID / Apple Watch Auto Unlock / FileVault / password managers.
- No OpenAI API or GPT runtime dependency.
- No cloud build service, telemetry, account system, analytics, or remote command execution.
- Phone sends command IDs only. Mac maps command IDs to local allowlisted actions.
- Never commit real secrets.

## Assumptions
- Primary Android device: Samsung Galaxy S21+ 5G, model SM-G996U.
- Primary Mac target: MacBook Air M1 running current macOS available to the user.
- User prefers command-line Android SDK/Gradle over Android Studio due to storage.
- MacBook and Android phone are normally on the same trusted LAN; Tailscale can be used as a transport address later but does not replace DexTilt pairing/HMAC.
- DexDictate repository/source/screenshots were not found in this sandbox during bootstrap, so v1 uses compatible dark utility styling hooks rather than claiming exact DexDictate visuals.

## Architecture / Design
- Android: Kotlin + Jetpack Compose, Android sensor APIs, deterministic gesture templates, local state machine, HMAC signing, manual fallback buttons, logs/debug screens.
- Mac receiver: Python + FastAPI, dashboard at http://127.0.0.1:47391/status, QR pairing, local state/config under user-controlled paths, allowlisted actions only.
- Communication: HTTP POST command events over local or user-controlled network. Message protocol dextilt.v1. Pairing protocol dextilt.pairing.v1.
- Security baseline: one-time pairing token, persistent receiver ID, persistent Android device ID, shared secret stored locally, HMAC signature, timestamp, nonce, replay protection, command allowlist, rate limiting, logs, visible feedback, reset path.
- v1 cleartext HTTP is used for setup simplicity on local/trusted networks. HMAC protects command authenticity after pairing, but pairing should be done on a trusted LAN or Tailscale because cleartext HTTP does not hide the shared secret from a LAN eavesdropper.

## File Map
See PROJECT_MANIFEST.md for the generated file manifest.

## Current State Summary
Repository bootstrap started in sandbox at /mnt/data/DexTilt. This path is a build artifact location, not the user's real ~/Projects/DexTilt folder.

## Open Questions
None blocking. Future styling should inspect DexDictate if the repository/source becomes available.

## Chronological Ledger

### Entry 1 - Repository scaffold initialized
Summary:
Created the initial DexTilt repository scaffold, naming conventions, core docs placeholders, project bible, manifest, and ignore rules.

Reason / Intent:
Establish the required project structure and durable handoff ledger before writing executable code.

Files Changed:
- .gitignore
- UNLICENSE
- DexTilt_Bible.md
- PROJECT_MANIFEST.md
- README.md
- SECURITY.md
- PRIVACY.md
- TROUBLESHOOTING.md
- docs/architecture.md
- docs/setup_mac.md
- docs/setup_android.md
- docs/test_plan.md
- docs/protocol.md
- docs/permissions.md

Commands Run:
- pwd
- whoami
- python3 --version
- python --version
- git --version
- java -version
- gradle --version
- command -v adb
- command -v sdkmanager
- df -h
- find /mnt/data -maxdepth 3 -iname '*DexDictate*' -o -iname '*dexdictate*'
- mkdir -p /mnt/data/DexTilt/...
- cat > initial files

Command Intent:
Inspect available build/test tooling, check storage, look for DexDictate source, and create the initial repository skeleton.

Outputs Generated:
Initial repository files under /mnt/data/DexTilt.

Decisions:
- Use sandbox path /mnt/data/DexTilt for generated artifact because this environment cannot write to the user's real Mac ~/Projects/DexTilt.
- Treat Android APK build and wireless install as NOT RUN until Gradle, Android SDK command-line tools, and ADB are available.
- Use dark utility UI direction with DexDictate-compatible styling hooks because no DexDictate source was found in sandbox.

Bugs / Blockers:
- gradle command not found.
- adb command not found.
- sdkmanager command not found.
- Android Studio not installed and not required by this scaffold.

Correction:
None.

State After Completion:
Phase 1 scaffold exists and is ready for Mac receiver implementation.

Next Step / Handoff:
Implement and test the Mac receiver health/status/pairing/command path.

### Entry 2 - Mac receiver implemented and core-tested
Summary:
Implemented the Python/FastAPI DexTilt Mac Receiver with local dashboard, pairing token flow, persistent receiver/device state, HMAC command validation, nonce replay protection, timestamp checking, rate limiting, allowlisted action routing, logging, diagnostics, and setup/run/test scripts.

Reason / Intent:
Build and validate the Mac side before Android command execution so networking/signing/action routing can be debugged independently from gesture recognition.

Files Changed:
- mac_receiver/README.md
- mac_receiver/config.example.json
- mac_receiver/requirements.txt
- mac_receiver/pyproject.toml
- mac_receiver/scripts/setup.sh
- mac_receiver/scripts/run.sh
- mac_receiver/scripts/run_core_tests.sh
- mac_receiver/scripts/test_health.sh
- mac_receiver/scripts/test_signed_command.py
- mac_receiver/scripts/test_signed_command.sh
- mac_receiver/scripts/collect_mac_debug.sh
- mac_receiver/scripts/install_launch_agent.sh
- mac_receiver/scripts/uninstall_launch_agent.sh
- mac_receiver/src/dextilt_receiver/__init__.py
- mac_receiver/src/dextilt_receiver/__main__.py
- mac_receiver/src/dextilt_receiver/actions.py
- mac_receiver/src/dextilt_receiver/app.py
- mac_receiver/src/dextilt_receiver/config.py
- mac_receiver/src/dextilt_receiver/constants.py
- mac_receiver/src/dextilt_receiver/crypto.py
- mac_receiver/src/dextilt_receiver/dashboard.py
- mac_receiver/src/dextilt_receiver/logging_utils.py
- mac_receiver/src/dextilt_receiver/models.py
- mac_receiver/src/dextilt_receiver/pairing.py
- mac_receiver/src/dextilt_receiver/rate_limit.py
- mac_receiver/src/dextilt_receiver/state.py
- mac_receiver/tests/__init__.py
- mac_receiver/tests/run_core_tests.py
- mac_receiver/tests/run_unit_tests.py
- mac_receiver/tests/test_app.py
- mac_receiver/tests/test_crypto.py

Commands Run:
- cat > mac_receiver/... source, config, script, and test files
- chmod +x mac_receiver/scripts/*.sh mac_receiver/scripts/test_signed_command.py mac_receiver/tests/run_core_tests.py
- PYTHONPATH=src python3 -S -m py_compile $(find src -name '*.py' -print)
- PYTHONUNBUFFERED=1 python3 -S - <<'PY' ... run tests/run_core_tests.py ... PY

Command Intent:
Create the Mac receiver implementation, verify Python syntax, and run core receiver security/action tests in the sandbox.

Outputs Generated:
- Mac receiver package and scripts.
- Core test output: 9/9 tests passed.

Decisions:
- Store local Mac config/state/logs under `~/.dextilt` by default and ignore real secrets in Git.
- Use HMAC-SHA256 over canonical JSON sorted keys.
- Keep `/pairing` local-only so unauthenticated LAN clients cannot fetch a pairing token directly.
- Use local HTTP in v1 for setup simplicity; document pairing confidentiality limitation.
- Use dry-run action mode in tests to avoid opening browser/notifications in non-macOS sandbox.

Bugs / Blockers:
- Sandbox Python normal startup and FastAPI TestClient behavior were unreliable due the environment. A direct core test runner was added and passed.
- `pytest tests/test_crypto.py` passed, but full pytest/TestClient endpoint suite was not used as the authoritative sandbox test.
- Live macOS notification and browser actions were NOT RUN because this sandbox is not macOS.

Correction:
Initial Git commit during Entry 1 failed because Git author identity was not configured. Local repository identity was later set to `DexTilt Builder <dextilt-builder@example.invalid>` and a commit was created.

State After Completion:
Mac receiver phases through signed command validation, dashboard/pairing implementation, action allowlist, diagnostics, and scripts are implemented. Core automated tests passed in sandbox.

Next Step / Handoff:
Build Android app scaffold, pairing client, manual signed command buttons, sensors, calibration, gesture recording, and local gesture matching.

### Entry 3 - Android native app scaffold and gesture engine implemented
Summary:
Implemented a Kotlin/Jetpack Compose Android app scaffold for DexTilt with QR/manual pairing, HMAC command signing, manual buttons, secure local secret storage, sensor availability/live display, calibration step updates, face-down baseline detection, gesture recording, deterministic matching, arming flow, haptic feedback, logs/debug UI, and command-line build/install scripts.

Reason / Intent:
Create the Android side needed to pair with the Mac receiver, test manual commands before gestures, and support the first trained face-down-start Open GPT gesture.

Files Changed:
- android_app/settings.gradle.kts
- android_app/build.gradle.kts
- android_app/gradle.properties
- android_app/app/build.gradle.kts
- android_app/app/src/main/AndroidManifest.xml
- android_app/app/src/main/java/com/stinkyweasel/dextilt/MainActivity.kt
- android_app/app/src/main/java/com/stinkyweasel/dextilt/DexTiltViewModel.kt
- android_app/app/src/main/java/com/stinkyweasel/dextilt/gesture/*.kt
- android_app/app/src/main/java/com/stinkyweasel/dextilt/model/*.kt
- android_app/app/src/main/java/com/stinkyweasel/dextilt/net/*.kt
- android_app/app/src/main/java/com/stinkyweasel/dextilt/sensor/*.kt
- android_app/app/src/main/java/com/stinkyweasel/dextilt/storage/*.kt
- android_app/app/src/main/java/com/stinkyweasel/dextilt/ui/Feedback.kt
- android_app/app/src/main/res/**
- android_app/app/src/test/java/com/stinkyweasel/dextilt/gesture/GestureMatcherTest.kt
- scripts/build_android_debug_apk.sh
- scripts/install_android_wireless.sh
- shared/protocol_schema.json

Commands Run:
- cat > android_app/... Gradle, manifest, resource, Kotlin source, and test files
- chmod +x scripts/build_android_debug_apk.sh scripts/install_android_wireless.sh
- web search for current Android Gradle Plugin / Compose setup references
- command -v gradle
- command -v adb
- command -v sdkmanager

Command Intent:
Generate Android app source and scripts while avoiding Android Studio/emulator requirements and confirming sandbox tooling availability.

Outputs Generated:
- Native Android app source tree.
- Android command-line build and wireless install scripts.
- Shared protocol JSON schema.

Decisions:
- Use Kotlin + Jetpack Compose.
- Use Android package `com.stinkyweasel.dextilt`.
- Use minSdk 26, compileSdk/targetSdk 36.
- Use Android Gradle Plugin 8.13.0 and Compose compiler plugin pattern for Kotlin 2.x.
- Use ZXing Android Embedded for QR scanning.
- Store the shared secret encrypted with Android Keystore AES-GCM.
- Use cleartext HTTP for local receiver access because v1 uses local LAN HTTP plus HMAC; document the limitation.
- Keep gesture recognition deterministic and conservative with strict/normal/relaxed tolerance.

Bugs / Blockers:
- APK build NOT RUN: sandbox has no Gradle, Android SDK command-line tools, sdkmanager, or adb.
- Android unit tests NOT RUN: Gradle unavailable in sandbox.
- QR scanning and real sensor behavior require testing on the Galaxy S21+.

Correction:
None.

State After Completion:
Android source is complete draft form but not compiled in this environment. It is ready for command-line SDK/Gradle build on the user's Mac.

Next Step / Handoff:
Run `./scripts/build_android_debug_apk.sh` on the MacBook after installing command-line Android tooling if necessary, then install via wireless debugging and perform staged manual tests.

### Entry 4 - Documentation, manifest, security review, and repository checkpoint
Summary:
Updated setup/test/protocol documentation, added security review, regenerated project manifest, and created a Git checkpoint commit.

Reason / Intent:
Make the project handoff-grade and preserve the exact state of generated files and known test limitations.

Files Changed:
- README.md
- docs/setup_mac.md
- docs/setup_android.md
- docs/test_plan.md
- docs/protocol.md
- docs/security_review.md
- PROJECT_MANIFEST.md
- DexTilt_Bible.md

Commands Run:
- cat > docs/setup_mac.md docs/setup_android.md docs/test_plan.md docs/protocol.md docs/security_review.md README.md
- python3 -S - <<'PY' ... regenerate PROJECT_MANIFEST.md ... PY
- git config user.name "DexTilt Builder"
- git config user.email "dextilt-builder@example.invalid"
- git add .
- git commit -m "Implement DexTilt receiver and Android scaffold"
- git status --short

Command Intent:
Document setup/testing/security, update manifest, and create a local Git checkpoint without real secrets.

Outputs Generated:
- Git commit `9339233` with implemented scaffold, receiver, Android source, docs, and scripts.

Decisions:
- Keep generated APK out of the repository until a real build succeeds and copies it to `release/DexTilt-debug.apk` intentionally.
- Mark Android build/install and device tests as NOT RUN until tooling/device access is available.

Bugs / Blockers:
- Manifest initially needed regeneration after adding `docs/security_review.md`; regenerated afterward.

Correction:
None.

State After Completion:
Repository has a committed build checkpoint and generated manifest. One modified manifest/bible update may exist after this entry and should be committed or amended by the next session if desired.

Next Step / Handoff:
Zip/export project artifact, then run Android build on the MacBook with command-line SDK tooling.

### Entry 5 - Final sandbox validation and packaging prep
Summary:
Reran Mac receiver syntax and core security/action tests in the sandbox, removed generated Python caches from the export tree, corrected the earlier Git hash note by deferring to `git log`, and prepared the repository for downloadable packaging.

Reason / Intent:
Give the handoff a clean final state with honest test results and no generated cache files listed as project deliverables.

Files Changed:
- DexTilt_Bible.md
- PROJECT_MANIFEST.md

Commands Run:
- cd /mnt/data/DexTilt/mac_receiver && PYTHONPATH=src python3 -S -m py_compile $(find src -name '*.py' -print)
- cd /mnt/data/DexTilt/mac_receiver && PYTHONUNBUFFERED=1 python3 -S - <<'PY' ... execute tests/run_core_tests.py ... PY
- cd /mnt/data/DexTilt && find . -name __pycache__ -type d -prune -exec rm -rf {} + && rm -rf mac_receiver/.pytest_cache
- cd /mnt/data/DexTilt && python3 -S - <<'PY' ... regenerate PROJECT_MANIFEST.md ... PY
- git status --short
- git add DexTilt_Bible.md PROJECT_MANIFEST.md
- git commit --amend --no-edit

Command Intent:
Validate the Mac receiver core, keep generated caches out of the project artifact, refresh the manifest, and fold the final ledger/manifest state into the existing local checkpoint.

Outputs Generated:
- Mac receiver core test output: 9/9 tests passed.
- Refreshed `PROJECT_MANIFEST.md` excluding `.git`, `.pytest_cache`, `__pycache__`, build directories, Gradle caches, and release APK placeholders.
- Final downloadable project archive generated outside the repository.

Decisions:
- Treat the custom core test runner as the authoritative sandbox test result because pytest/TestClient behavior was unreliable in this environment.
- Keep Android build and device tests marked NOT RUN until command-line Android SDK/Gradle/ADB and the Galaxy S21+ are available.
- Keep `release/` empty until a real APK is built and intentionally copied to `release/DexTilt-debug.apk`.

Bugs / Blockers:
- Android APK build remains NOT RUN: Gradle, Android SDK command-line tools, sdkmanager, and adb are not installed in the sandbox.
- macOS notification/browser-open actions remain NOT RUN because the sandbox is not the target MacBook/macOS environment.
- Real QR camera scan, sensor sampling, haptics, wireless debugging, and end-to-end Android-to-Mac tests remain NOT RUN.

Correction:
Entry 4 listed an intermediate commit hash. The authoritative final checkpoint is the current output of `git log --oneline -1` in the exported repository.

State After Completion:
Mac receiver source and core tests are validated in sandbox. Android source is complete draft form and documented, but must still be compiled and tested on the MacBook/Galaxy S21+ path.

Next Step / Handoff:
Unzip the project to `~/Projects/DexTilt`, run the Mac receiver setup and core tests, then run `./scripts/build_android_debug_apk.sh` on the MacBook after installing minimal Android command-line tooling.
