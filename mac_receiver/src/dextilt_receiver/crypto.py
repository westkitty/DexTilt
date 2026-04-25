from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from typing import Any, Mapping

from .constants import SIGNING_FIELDS


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def generate_token(num_bytes: int = 32) -> str:
    return b64url_encode(secrets.token_bytes(num_bytes))


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_command_payload(message: Mapping[str, Any]) -> bytes:
    canonical = {field: message[field] for field in SIGNING_FIELDS}
    return json.dumps(canonical, separators=(",", ":"), sort_keys=True).encode("utf-8")


def sign_command(message: Mapping[str, Any], shared_secret_b64url: str) -> str:
    secret = b64url_decode(shared_secret_b64url)
    digest = hmac.new(secret, canonical_command_payload(message), hashlib.sha256).digest()
    return b64url_encode(digest)


def verify_command_signature(message: Mapping[str, Any], shared_secret_b64url: str) -> bool:
    provided = str(message.get("signature", ""))
    if not provided:
        return False
    try:
        expected = sign_command(message, shared_secret_b64url)
    except Exception:
        return False
    return hmac.compare_digest(provided, expected)


def redact_value(key: str, value: Any) -> Any:
    lowered = key.lower()
    if any(token in lowered for token in ("secret", "token", "signature", "hmac")):
        if value is None:
            return None
        text = str(value)
        if len(text) <= 8:
            return "[redacted]"
        return f"[redacted:{len(text)}]"
    return value


def redact_mapping(data: Mapping[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, Mapping):
            redacted[key] = redact_mapping(value)
        elif isinstance(value, list):
            redacted[key] = [redact_mapping(v) if isinstance(v, Mapping) else v for v in value]
        else:
            redacted[key] = redact_value(key, value)
    return redacted
