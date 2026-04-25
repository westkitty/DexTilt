# DexTilt Protocol

## Pairing payload: dextilt.pairing.v1

The Mac dashboard displays a QR code with:

```json
{
  "protocol": "dextilt.pairing.v1",
  "host": "192.168.1.20",
  "port": 47391,
  "receiver_id": "uuid",
  "pairing_token": "one-time-token",
  "expires_at_ms": 1730000000000
}
```

The token is one-time and expires. The phone posts the token plus its persistent Android device ID to `/pair`. The receiver returns a shared secret for future HMAC signing. In v1 this exchange uses local HTTP, so pair only on a trusted LAN or user-controlled encrypted transport.

The `/pairing` token endpoint is intended for local Mac dashboard use. The Android phone receives the token by scanning the Mac screen.

## Command message: dextilt.v1

```json
{
  "protocol": "dextilt.v1",
  "device_id": "android-phone-id",
  "receiver_id": "macbook-receiver-id",
  "command_id": "open_gpt_default_browser",
  "gesture_id": "primary_open_gpt",
  "timestamp_ms": 1730000000000,
  "nonce": "random-nonce",
  "confidence": 92,
  "signature": "base64url-hmac-sha256"
}
```

The signature covers all fields except `signature`.

Canonical signing order:

```text
command_id, confidence, device_id, gesture_id, nonce, protocol, receiver_id, timestamp_ms
```

Canonical body rules:

- Compact JSON.
- Keys sorted alphabetically as above.
- String values JSON-escaped.
- Integers serialized as base-10 numbers.
- HMAC-SHA256 using the paired shared secret decoded from base64url.
- Signature encoded as base64url without padding.

## Calibration update

Android calibration updates are signed with the same envelope fields, using:

```text
command_id: calibration_update
gesture_id: calibration
```

The body also includes:

```json
{
  "step_id": "face_down",
  "step_label": "Face down",
  "status": "detected",
  "detail": "Phone-side calibration step marked detected."
}
```

## Gesture template schema: dextilt.gesture.v1

```json
{
  "schema_version": "dextilt.gesture.v1",
  "gesture_id": "primary_open_gpt",
  "name": "Open GPT Gesture",
  "created_at": "ISO-8601 timestamp",
  "sample_rate_hz": 50,
  "duration_ms": 1400,
  "start_posture": "face_down",
  "sensor_sources": ["accelerometer", "gyroscope", "rotation_vector"],
  "features": {
    "rotation_total_x": 0.0,
    "rotation_total_y": 0.0,
    "rotation_total_z": 0.0,
    "acceleration_peak": 0.0,
    "acceleration_mean": 0.0,
    "stable_start_ms": 500,
    "major_axis": "z",
    "orientation_delta": {},
    "acceleration_summary": {},
    "stability_summary": {}
  },
  "tolerance": "normal"
}
```

Unsupported gesture schemas must show a retraining message instead of crashing.
