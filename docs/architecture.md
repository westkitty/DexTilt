# DexTilt Architecture

## Components

Android app:
- Kotlin + Jetpack Compose UI.
- Pairing client and HMAC signer.
- Sensor availability and live sensor pipeline.
- Face-down baseline detector.
- Deterministic gesture recorder and matcher.
- Local gesture template storage.
- Manual fallback buttons and logs.

Mac receiver:
- Python + FastAPI local receiver.
- Dashboard at `http://127.0.0.1:47391/status`.
- One-time QR pairing token.
- Persistent receiver identity and paired device state.
- HMAC command validator with timestamp, nonce, replay protection, allowlist, rate limiting, and logs.
- Action adapters for notifications and opening URLs.

## State machine

Android visible states:
Disconnected, Connected, Paired, Disarmed, Armed, BaselineDetecting, ReadyForGesture, Recording, Matching, LowConfidence, AwaitingConfirmation, CommandSending, CommandAccepted, CommandRejected, Error.

## First action

`open_gpt_default_browser` maps to opening `https://chatgpt.com/` in the user's default browser.
