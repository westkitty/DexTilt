#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import secrets
import time
import urllib.request

SIGNING_FIELDS = ["protocol", "device_id", "receiver_id", "command_id", "gesture_id", "timestamp_ms", "nonce", "confidence"]


def b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode((value + "=" * (-len(value) % 4)).encode("ascii"))


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def sign(message: dict, secret: str) -> str:
    canonical = {field: message[field] for field in SIGNING_FIELDS}
    body = json.dumps(canonical, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return b64url_encode(hmac.new(b64url_decode(secret), body, hashlib.sha256).digest())


def main() -> None:
    parser = argparse.ArgumentParser(description="Pair a local test device and send a DexTilt signed command")
    parser.add_argument("--base", default="http://127.0.0.1:47391")
    parser.add_argument("--command", default="notify_test")
    parser.add_argument("--confidence", type=int, default=100)
    args = parser.parse_args()

    pairing = get_json(args.base + "/pairing")["payload"]
    device_id = "mac_test_device_" + secrets.token_hex(6)
    pair_resp = post_json(args.base + "/pair", {
        "protocol": "dextilt.pairing.v1",
        "receiver_id": pairing["receiver_id"],
        "pairing_token": pairing["pairing_token"],
        "device_id": device_id,
        "device_name": "DexTilt Mac Test Script"
    })
    secret = pair_resp["shared_secret"]
    message = {
        "protocol": "dextilt.v1",
        "device_id": device_id,
        "receiver_id": pairing["receiver_id"],
        "command_id": args.command,
        "gesture_id": "manual_test_script",
        "timestamp_ms": int(time.time() * 1000),
        "nonce": secrets.token_urlsafe(24),
        "confidence": args.confidence,
    }
    message["signature"] = sign(message, secret)
    result = post_json(args.base + "/command", message)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
