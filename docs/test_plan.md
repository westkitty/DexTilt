# DexTilt Test Plan

## Automated Mac receiver tests

Run from `mac_receiver`:

```sh
./scripts/setup.sh
./scripts/run_core_tests.sh
```

Current core tests cover:

- HMAC signature round trip.
- Direct health route output.
- Known command acceptance.
- Invalid HMAC rejection.
- Timestamp expiry rejection.
- Nonce replay rejection.
- Unknown command rejection.
- Unknown protocol rejection.
- Dry-run action routing.

Additional pytest files exist for endpoint-style tests. In the sandbox build, a custom core runner was used because the container's Python/site-package startup and TestClient behavior were unreliable. On the user's Mac, `pytest` may also be used after setup.

## Manual Mac receiver tests

With the receiver running:

```sh
./scripts/test_health.sh
./scripts/test_signed_command.sh --command notify_test
./scripts/test_signed_command.sh --command open_gpt_default_browser
```

The Open ChatGPT command intentionally opens the default browser.

## Android checks

After APK install:

1. Open DexTilt.
2. Confirm sensor availability shows accelerometer and ideally gyroscope/rotation vector.
3. Pair with QR.
4. Run Health check.
5. Send Test Mac Notification.
6. Send Open ChatGPT.
7. Start sensor preview.
8. Confirm live accelerometer/gyro values change when moving the phone.
9. Run calibration steps and confirm Mac dashboard updates.
10. Record a face-down-start gesture.
11. Test the gesture locally and read confidence score.
12. Arm DexTilt and perform the gesture.

## Done-means-done demo script

1. Start the Mac receiver on the MacBook.
2. Confirm the receiver health endpoint passes.
3. Open the DexTilt Mac receiver dashboard.
4. Display pairing QR code on the MacBook.
5. Install/open DexTilt on the Galaxy S21+.
6. Scan the QR code.
7. Confirm paired/connected status in the Android app.
8. Send manual test notification from Android.
9. Confirm Mac notification appears.
10. Send manual Open GPT command from Android.
11. Confirm the default browser opens `https://chatgpt.com/`.
12. Run Mac-guided calibration.
13. Confirm calibration feedback appears on both Mac and Android.
14. Train the first face-down-start gesture.
15. Test gesture locally without firing command.
16. Confirm confidence score displays.
17. Arm DexTilt.
18. Perform the trained gesture.
19. Confirm Android haptic success.
20. Confirm Mac notification appears.
21. Confirm the default browser opens `https://chatgpt.com/`.
22. Inspect logs on both sides and verify command accepted with valid signature.
23. Confirm `DexTilt_Bible.md` and `PROJECT_MANIFEST.md` are updated.


## Stable-end regression checks

The face-down end is a command-safety invariant, not merely a confidence hint.

1. Arm DexTilt, obtain a face-down baseline, begin a gesture, then **do not** return the phone to stable face-down before the 5-second capture limit.
2. Expected: DexTilt reports a timeout, disarms, sends no command, and does not enter gesture matching.
3. Start training, begin either training pass, then **do not** return the phone to stable face-down before the capture limit.
4. Expected: training fails, the session is cleared, and no gesture template is saved.
5. Repeat a valid gesture and hold the stable face-down end for at least 600 ms before the limit.
6. Expected: capture completes normally and proceeds to matching/training validation.

The JVM unit tests in `GestureCapturePolicyTest.kt` lock the corresponding timeout/complete decision boundary.
