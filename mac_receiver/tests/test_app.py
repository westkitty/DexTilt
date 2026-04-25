import json
import time
from pathlib import Path

from starlette.testclient import TestClient

from dextilt_receiver.app import create_app
from dextilt_receiver.crypto import generate_token, sign_command


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
    }))
    app = create_app(config_path=config)
    return TestClient(app)


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


def test_health_endpoint(tmp_path):
    client = make_client(tmp_path)
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["protocol"] == "dextilt.v1"


def test_pairing_and_known_command_acceptance(tmp_path):
    client = make_client(tmp_path)
    receiver_id, device_id, secret = pair(client)
    msg = signed_message(receiver_id, device_id, secret)
    r = client.post("/command", json=msg)
    assert r.status_code == 200, r.text
    assert r.json()["accepted"] is True


def test_invalid_hmac_rejected(tmp_path):
    client = make_client(tmp_path)
    receiver_id, device_id, secret = pair(client)
    msg = signed_message(receiver_id, device_id, secret)
    msg["signature"] = "bad-signature-value"
    r = client.post("/command", json=msg)
    assert r.status_code == 403
    assert r.json()["error_code"] == "invalid_signature"


def test_reused_nonce_rejected(tmp_path):
    client = make_client(tmp_path)
    receiver_id, device_id, secret = pair(client)
    msg = signed_message(receiver_id, device_id, secret, nonce="same-nonce-123")
    assert client.post("/command", json=msg).status_code == 200
    r = client.post("/command", json=msg)
    assert r.status_code == 403
    assert r.json()["error_code"] == "replay"


def test_expired_timestamp_rejected(tmp_path):
    client = make_client(tmp_path)
    receiver_id, device_id, secret = pair(client)
    old = int((time.time() - 3600) * 1000)
    msg = signed_message(receiver_id, device_id, secret, timestamp_ms=old, nonce="old-nonce-123")
    r = client.post("/command", json=msg)
    assert r.status_code == 400
    assert r.json()["error_code"] == "expired_timestamp"


def test_unknown_command_rejected(tmp_path):
    client = make_client(tmp_path)
    receiver_id, device_id, secret = pair(client)
    msg = signed_message(receiver_id, device_id, secret, command_id="unknown_command", nonce="unknown-nonce-123")
    r = client.post("/command", json=msg)
    assert r.status_code == 400
    assert r.json()["error_code"] == "unknown_command"


def test_unknown_protocol_rejected(tmp_path):
    client = make_client(tmp_path)
    receiver_id, device_id, secret = pair(client)
    msg = signed_message(receiver_id, device_id, secret, protocol="dextilt.v9", nonce="proto-nonce-123")
    r = client.post("/command", json=msg)
    assert r.status_code == 400
    assert r.json()["error_code"] == "unknown_protocol"


def test_malformed_json_rejected(tmp_path):
    client = make_client(tmp_path)
    r = client.post("/command", content="{not-json", headers={"Content-Type": "application/json"})
    assert r.status_code == 400
    assert r.json()["error_code"] == "malformed_json"


def test_logs_endpoint_redacts_signature(tmp_path):
    client = make_client(tmp_path)
    receiver_id, device_id, secret = pair(client)
    msg = signed_message(receiver_id, device_id, secret, nonce="logs-nonce-123")
    client.post("/command", json=msg)
    r = client.get("/logs")
    assert r.status_code == 200
    text = r.text
    assert msg["signature"] not in text
