# DexTilt Security Review

Date: 2026-04-25

## Reviewed controls

- Arbitrary command execution: v1 does not accept raw shell commands from Android. The phone sends command IDs only. The Mac receiver maps IDs to configured allowlisted action adapters.
- Secrets in source: no real shared secret, pairing token, or HMAC key is committed. `config.example.json` contains only example structure.
- Logs: receiver logging redacts fields whose names include secret, token, signature, or hmac. Android local logs redact obvious secret/token/signature patterns.
- Replay protection: receiver stores per-device nonces and rejects reuse. Cache is pruned and bounded.
- Timestamp window: receiver defaults to 60 seconds and rejects stale/future-skewed messages outside the window.
- Rate limiting: receiver applies per-source request limits and per-device command cooldown.
- Receiver binding: default host is `0.0.0.0` for LAN usability. This exposes receiver endpoints to the LAN; command execution still requires HMAC. Do not expose the port to the public internet.
- Pairing token: generated as a one-time random token, expires, and is consumed after successful pairing.
- Pairing QR exposure: `/pairing` is intended for local Mac dashboard use and rejects non-local clients. The QR itself is visible on the Mac screen.
- Receiver identity: command messages include receiver ID. Android stores paired receiver ID. Future UI should add a stronger trust-on-first-use warning if the same host returns a different receiver ID.
- CORS/browser origin: receiver does not enable permissive CORS. Dashboard uses same-origin local requests.
- Shutdown endpoint: no unauthenticated shutdown endpoint is implemented.
- Actions: `open_gpt_default_browser`, `notify_test`, and `open_test_url` are action-adapter based. `open_gpt_brave` is example-configured and fails clearly if the app is unavailable.
- macOS permissions: Open URL usually needs no special permission. Notification permission may be requested by macOS.
- Android permissions: v1 requests Internet, network state, vibration, and camera only.

## Known limitations

- v1 pairing uses local HTTP. HMAC protects command authenticity after pairing, but it does not encrypt the pairing exchange. A LAN eavesdropper during pairing could observe the shared secret. Pair only on a trusted LAN or over a user-controlled encrypted transport such as Tailscale.
- The Android project has not been compiled in this sandbox because Gradle, Android SDK command-line tools, and ADB are unavailable.
- The QR scanner and Android sensor flows require device testing on the Galaxy S21+.
- Gesture recognition is deterministic and intentionally conservative. It will need real-device tuning for Andrew's exact motion.
- Receiver dashboard is not a native menubar/Dock app. v1 documents a Shortcut/Automator/script launcher.

## Final security stance

DexTilt v1 is suitable as a local post-login command layer on a trusted LAN after setup and testing. It is not suitable for public internet exposure, Mac login/unlock, privileged prompt approval, password entry, or high-security remote automation.
