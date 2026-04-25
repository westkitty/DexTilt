#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import tempfile
import time
from pathlib import Path

from dextilt_receiver.actions import ActionRunner
from dextilt_receiver.app import create_app, make_context, validate_signed_envelope
from dextilt_receiver.constants import COMMAND_PROTOCOL
from dextilt_receiver.crypto import generate_token, sign_command, verify_command_signature


def temp_config(tmp: Path) -> Path:
    config = tmp / "config.json"
    state = tmp / "state.json"
    log = tmp / "receiver.log"
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
    return config


def signed_message(receiver_id: str, device_id: str, secret: str, *, command_id="notify_test", protocol=COMMAND_PROTOCOL, timestamp_ms=None, nonce="nonce-core-test-1") -> dict:
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


def context_with_pairing(tmp: Path):
    ctx = make_context(config_path=temp_config(tmp))
    device_id = "android-device-test"
    secret = generate_token(32)
    ctx.state.pair_device(device_id, "Unit Test Android", secret, "127.0.0.1")
    return ctx, device_id, secret


def assert_ok(name: str, condition: bool, detail: str = "") -> None:
    if not condition:
        raise AssertionError(f"{name} failed {detail}")


def test_crypto_round_trip():
    secret = generate_token(32)
    msg = signed_message("receiver-12345678", "device-12345678", secret)
    assert_ok("valid signature", verify_command_signature(msg, secret))
    assert_ok("invalid signature", not verify_command_signature(msg, generate_token(32)))


def test_health_route_direct():
    with tempfile.TemporaryDirectory() as td:
        app = create_app(config_path=temp_config(Path(td)))
        route = next(r for r in app.routes if getattr(r, "path", None) == "/health")
        body = asyncio.run(route.endpoint())
        assert_ok("health ok", body["ok"] is True)
        assert_ok("health protocol", body["protocol"] == COMMAND_PROTOCOL)


def test_known_command_acceptance():
    with tempfile.TemporaryDirectory() as td:
        ctx, device_id, secret = context_with_pairing(Path(td))
        ok, code, _, _ = validate_signed_envelope(signed_message(ctx.state.receiver_id, device_id, secret), ctx, "127.0.0.1", require_known_command=True)
        assert_ok("known command accepted", ok, code)


def test_invalid_hmac_rejected():
    with tempfile.TemporaryDirectory() as td:
        ctx, device_id, secret = context_with_pairing(Path(td))
        msg = signed_message(ctx.state.receiver_id, device_id, secret)
        msg["signature"] = "bad-signature-value"
        ok, code, _, _ = validate_signed_envelope(msg, ctx, "127.0.0.1", require_known_command=True)
        assert_ok("invalid hmac rejected", not ok and code == "invalid_signature", code)


def test_reused_nonce_rejected():
    with tempfile.TemporaryDirectory() as td:
        ctx, device_id, secret = context_with_pairing(Path(td))
        msg = signed_message(ctx.state.receiver_id, device_id, secret, nonce="same-nonce-123")
        ok1, code1, _, _ = validate_signed_envelope(msg, ctx, "127.0.0.1", require_known_command=True)
        ok2, code2, _, _ = validate_signed_envelope(msg, ctx, "127.0.0.1", require_known_command=True)
        assert_ok("first nonce accepted", ok1, code1)
        assert_ok("second nonce replay rejected", not ok2 and code2 == "replay", code2)


def test_expired_timestamp_rejected():
    with tempfile.TemporaryDirectory() as td:
        ctx, device_id, secret = context_with_pairing(Path(td))
        old = int((time.time() - 3600) * 1000)
        msg = signed_message(ctx.state.receiver_id, device_id, secret, timestamp_ms=old, nonce="old-nonce-123")
        ok, code, _, _ = validate_signed_envelope(msg, ctx, "127.0.0.1", require_known_command=True)
        assert_ok("expired rejected", not ok and code == "expired_timestamp", code)


def test_unknown_command_rejected():
    with tempfile.TemporaryDirectory() as td:
        ctx, device_id, secret = context_with_pairing(Path(td))
        msg = signed_message(ctx.state.receiver_id, device_id, secret, command_id="unknown_command", nonce="unknown-nonce-123")
        ok, code, _, _ = validate_signed_envelope(msg, ctx, "127.0.0.1", require_known_command=True)
        assert_ok("unknown command rejected", not ok and code == "unknown_command", code)


def test_unknown_protocol_rejected():
    with tempfile.TemporaryDirectory() as td:
        ctx, device_id, secret = context_with_pairing(Path(td))
        msg = signed_message(ctx.state.receiver_id, device_id, secret, protocol="dextilt.v9", nonce="proto-nonce-123")
        ok, code, _, _ = validate_signed_envelope(msg, ctx, "127.0.0.1", require_known_command=True)
        assert_ok("unknown protocol rejected", not ok and code == "unknown_protocol", code)


def test_action_routing_dry_run():
    runner = ActionRunner({"dry_run_actions": True, "commands": {"open_gpt_default_browser": {"type": "open_url", "url": "https://chatgpt.com/"}}})
    result = runner.run("open_gpt_default_browser")
    assert_ok("dry run action", result.ok and "DRY RUN" in result.message, result.message)


TESTS = [
    test_crypto_round_trip,
    test_health_route_direct,
    test_known_command_acceptance,
    test_invalid_hmac_rejected,
    test_reused_nonce_rejected,
    test_expired_timestamp_rejected,
    test_unknown_command_rejected,
    test_unknown_protocol_rejected,
    test_action_routing_dry_run,
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
