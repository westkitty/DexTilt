# DexTilt Troubleshooting

## Mac receiver is not reachable from Android

Confirm both devices are on the same LAN or a user-controlled network such as Tailscale. Confirm the Mac receiver printed port `47391`. Open the dashboard locally on the Mac at `http://127.0.0.1:47391/status`. If the Mac firewall prompts, allow incoming connections for the Python receiver only if you intend to use LAN pairing.

## QR pairing failed

Refresh the dashboard to generate a fresh one-time token. Pairing tokens expire and are consumed after one use. Make sure the Android app is using the host and port shown in the QR code.

## Command rejected because pairing credentials did not match

Reset pairing on both Mac and Android, then pair again. This usually means the Android app has a different shared secret than the Mac receiver.

## Browser did not open

Use the Android manual Open ChatGPT button after pairing. Check Mac receiver logs. The default v1 action uses `open "https://chatgpt.com/"` on macOS and usually requires no Accessibility permission.

## Notification did not appear

macOS notification permission may be needed for the terminal/Python app. The command can still be accepted and logged even if the notification display fails.

## Gesture not recognized

Use manual buttons first to prove networking and signing. Then check sensor availability, run calibration, confirm face-down stability, record a new gesture, and test locally before arming.

## APK build failed

Confirm command-line Android SDK tools, `sdkmanager`, Java, and Gradle or a generated Gradle wrapper are installed. Do not install emulator images for DexTilt v1.
