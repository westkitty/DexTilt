#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

from starlette.testclient import TestClient

from dextilt_receiver.app import create_app
from dextilt_receiver.constants import COMMAND_PROTOCOL
from dextilt_receiver.crypto import generate_token, sign_command, verify_command_signature


def make_client(tmp_path: Path) -> TestClient:
    config = tmp_path / "config.json"
    state = tmp_path / "state.json"
    log = tmp_path / "receiver.log"
    config.write_text(json.dumps({
        "host": "127.0.0.1",
        "port": 47391,
        "advertised_host": "127.0.0.1",
        "state_path": str(state),
        "log_path": str(log),
        "dry_run_actions": True,
        "command_cooldown_seconds": 0,
        "timestamp_window_seconds": 60,
        "commands": {
            "notify_test": {"type": "notification", "title": "DexTilt", "message": "Test"},
            "open_gpt_default_browser": {"type": "open_url", "url": "https://chatgpt.com/"}
        }
    }), encoding="utf-8")
    return TestClient(create_app(config_path=config))


def pair(client: TestClient):
    # Unit tests seed a paired device directly so command-validation tests do not
    # depend on QR image rendering. The live /pairing endpoint is smoke-tested
    # separately through the running receiver.
    ctx = client.app.state.dextilt
    device_id = "android-device-test"
    secret = generate_token(32)
    ctx.state.pair_device(device_id, "Unit Test Android", secret, "testclient")
    return ctx.state.receiver_id, device_id, secret


def signed_message(receiver_id, device_id, secret, *, command_id="notify_test", protocol="dextilt.v1", timestamp_ms=None, nonce="nonce-unit-test-1"):
    msg = {
        "protocol": protocol,
        "device_id": device_id,
        "receiver_id": receiver_id,
        "command_id": command_id,
        "gesture_id": "manual",
        "timestamp_ms": int(time.time() * 1000) if timestamp_ms is None else timestamp_ms,
        "nonce": nonce,
        "confidence": 100,
    }
    msg["signature"] = sign_command(msg, secret)
    return msg


def test_crypto_round_trip():
    secret = generate_token(32)
    msg = {
        "protocol": COMMAND_PROTOCOL,
        "device_id": "device-12345678",
        "receiver_id": "receiver-12345678",
        "command_id": "notify_test",
        "gesture_id": "manual",
        "timestamp_ms": 1730000000000,
        "nonce": "nonce-123456789",
        "confidence": 100,
    }
    msg["signature"] = sign_command(msg, secret)
    assert verify_command_signature(msg, secret)
    assert not verify_command_signature(msg, generate_token(32))


def test_health_endpoint():
    with tempfile.TemporaryDirectory() as td:
        client = make_client(Path(td))
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert r.json()["protocol"] == "dextilt.v1"


def test_pairing_endpoint_returns_qr_payload():
    with tempfile.TemporaryDirectory() as td:
        client = make_client(Path(td))
        r = client.get("/pairing")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["payload"]["protocol"] == "dextilt.pairing.v1"
        assert body["payload"]["port"] == 47391
        assert body["qr_data_url"].startswith("data:image/png;base64,")


def test_pairing_and_known_command_acceptance():
    with tempfile.TemporaryDirectory() as td:
        client = make_client(Path(td))
        receiver_id, device_id, secret = pair(client)
        r = client.post("/command", json=signed_message(receiver_id, device_id, secret))
        assert r.status_code == 200, r.text
        assert r.json()["accepted"] is True


def test_invalid_hmac_rejected():
    with tempfile.TemporaryDirectory() as td:
        client = make_client(Path(td))
        receiver_id, device_id, secret = pair(client)
        msg = signed_message(receiver_id, device_id, secret)
        msg["signature"] = "bad-signature-value"
        r = client.post("/command", json=msg)
        assert r.status_code == 403
        assert r.json()["error_code"] == "invalid_signature"


def test_reused_nonce_rejected():
    with tempfile.TemporaryDirectory() as td:
        client = make_client(Path(td))
        receiver_id, device_id, secret = pair(client)
        msg = signed_message(receiver_id, device_id, secret, nonce="same-nonce-123")
        assert client.post("/command", json=msg).status_code == 200
        r = client.post("/command", json=msg)
        assert r.status_code == 403
        assert r.json()["error_code"] == "replay"


def test_expired_timestamp_rejected():
    with tempfile.TemporaryDirectory() as td:
        client = make_client(Path(td))
        receiver_id, device_id, secret = pair(client)
        old = int((time.time() - 3600) * 1000)
        r = client.post("/command", json=signed_message(receiver_id, device_id, secret, timestamp_ms=old, nonce="old-nonce-123"))
        assert r.status_code == 400
        assert r.json()["error_code"] == "expired_timestamp"


def test_unknown_command_rejected():
    with tempfile.TemporaryDirectory() as td:
        client = make_client(Path(td))
        receiver_id, device_id, secret = pair(client)
        r = client.post("/command", json=signed_message(receiver_id, device_id, secret, command_id="unknown_command", nonce="unknown-nonce-123"))
        assert r.status_code == 400
        assert r.json()["error_code"] == "unknown_command"


def test_unknown_protocol_rejected():
    with tempfile.TemporaryDirectory() as td:
        client = make_client(Path(td))
        receiver_id, device_id, secret = pair(client)
        r = client.post("/command", json=signed_message(receiver_id, device_id, secret, protocol="dextilt.v9", nonce="proto-nonce-123"))
        assert r.status_code == 400
        assert r.json()["error_code"] == "unknown_protocol"


def test_malformed_json_rejected():
    with tempfile.TemporaryDirectory() as td:
        client = make_client(Path(td))
        r = client.post("/command", content="{not-json", headers={"Content-Type": "application/json"})
        assert r.status_code == 400
        assert r.json()["error_code"] == "malformed_json"


def test_logs_endpoint_redacts_signature():
    with tempfile.TemporaryDirectory() as td:
        client = make_client(Path(td))
        receiver_id, device_id, secret = pair(client)
        msg = signed_message(receiver_id, device_id, secret, nonce="logs-nonce-123")
        client.post("/command", json=msg)
        r = client.get("/logs")
        assert r.status_code == 200
        assert msg["signature"] not in r.text


TESTS = [
    test_crypto_round_trip,
    test_health_endpoint,
    test_pairing_and_known_command_acceptance,
    test_invalid_hmac_rejected,
    test_reused_nonce_rejected,
    test_expired_timestamp_rejected,
    test_unknown_command_rejected,
    test_unknown_protocol_rejected,
    test_malformed_json_rejected,
    test_logs_endpoint_redacts_signature,
]


def main() -> int:
    failures = 0
    for test in TESTS:
        try:
            test()
            print(f"PASS {test.__name__}")
        except Exception as exc:
            failures += 1
            print(f"FAIL {test.__name__}: {exc}")
    print(f"{len(TESTS) - failures}/{len(TESTS)} tests passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
