# DexTilt Permissions

## macOS

| Feature | Expected permission profile |
| --- | --- |
| Open URL in default browser | Usually no special permission |
| Open URL in Brave | Usually no special permission if Brave is installed |
| Show notification | macOS notification permission may be needed |
| Run named Shortcut | Shortcuts may ask for approval depending on shortcut behavior |
| Run allowlisted shell script | Depends on script contents and filesystem access |
| AppleScript app control | Automation permission may be needed |
| UI clicks / keystrokes | Accessibility permission required |
| Security prompt approval | Excluded from v1 |
| Login/unlock/password entry | Excluded from v1 |

## Android

Expected v1 permissions:

```text
android.permission.INTERNET
android.permission.ACCESS_NETWORK_STATE
android.permission.VIBRATE
android.permission.CAMERA
```

DexTilt should avoid location, Bluetooth, background always-listening, telemetry, and unnecessary storage permissions in v1.
