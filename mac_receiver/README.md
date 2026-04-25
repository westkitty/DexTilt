# DexTilt Mac Receiver

The DexTilt Mac Receiver is a local FastAPI server for post-login Mac commands. It pairs with the Android app by QR token, stores paired device state locally, verifies HMAC-signed command messages, runs allowlisted actions, and logs all accepted/rejected command attempts.

Default dashboard:

```text
http://127.0.0.1:47391/status
```

Default port: `47391`.

## Setup

```sh
./scripts/setup.sh
```

## Run

```sh
./scripts/run.sh
```

## Test

```sh
./scripts/test_health.sh
./scripts/test_signed_command.sh --command notify_test
```

The signed command test pairs a local test device through the same one-time token mechanism and then sends a signed command.
