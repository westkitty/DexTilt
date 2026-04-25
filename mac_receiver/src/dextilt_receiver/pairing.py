from __future__ import annotations

import time
from dataclasses import dataclass

from .constants import PAIRING_PROTOCOL
from .crypto import generate_token, sha256_hex


@dataclass
class PairingToken:
    token_hash: str
    token_plain: str
    expires_at_ms: int
    used: bool = False


class PairingManager:
    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        self._current: PairingToken | None = None

    def issue(self, *, host: str, port: int, receiver_id: str) -> dict[str, object]:
        token = generate_token(32)
        expires_at_ms = int((time.time() + self.ttl_seconds) * 1000)
        self._current = PairingToken(token_hash=sha256_hex(token), token_plain=token, expires_at_ms=expires_at_ms)
        return {
            "protocol": PAIRING_PROTOCOL,
            "host": host,
            "port": port,
            "receiver_id": receiver_id,
            "pairing_token": token,
            "expires_at_ms": expires_at_ms,
        }

    def verify_and_consume(self, token: str) -> tuple[bool, str]:
        current = self._current
        now = int(time.time() * 1000)
        if current is None:
            return False, "No active pairing token. Refresh the Mac dashboard and scan the new QR code."
        if current.used:
            return False, "This pairing token was already used. Refresh the Mac dashboard and scan a new QR code."
        if now > current.expires_at_ms:
            return False, "This pairing token expired. Refresh the Mac dashboard and scan the new QR code."
        if sha256_hex(token) != current.token_hash:
            return False, "The pairing token did not match. Scan the current DexTilt QR code again."
        current.used = True
        return True, "Pairing token accepted."
