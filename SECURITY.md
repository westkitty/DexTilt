# DexTilt Security

DexTilt treats the local network as potentially hostile. After pairing, command messages use protocol `dextilt.v1`, a persistent Android device ID, a persistent receiver ID, timestamp, nonce, confidence value, and HMAC-SHA256 signature. The Mac receiver rejects malformed messages, missing fields, invalid signatures, expired timestamps, replayed nonces, unknown command IDs, unknown protocols, rate-limit violations, and unpaired devices.

## Explicit exclusions

DexTilt does not unlock macOS, store Mac passwords, transmit passwords, type passwords, approve privileged prompts, bypass login security, or replace Touch ID / Apple Watch Auto Unlock / FileVault / password managers / 2FA.

## v1 limitation

v1 uses HTTP for setup simplicity on local or user-controlled networks. HMAC protects command authenticity after pairing, but HTTP does not encrypt pairing traffic. Pair on a trusted LAN or over an encrypted user-controlled transport such as Tailscale. Do not expose the receiver to the public internet.

## Action policy

The phone sends command IDs only. The Mac receiver maps those IDs to local allowlisted actions. Future scripts must live in an allowlisted DexTilt action folder such as `~/DexTilt/actions/`; arbitrary shell commands from the phone are not accepted.
