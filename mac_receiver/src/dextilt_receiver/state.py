from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from .constants import DEFAULT_PORT


def now_ms() -> int:
    return int(time.time() * 1000)


class StateStore:
    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()
        self.lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load_or_create()
        self._live_phone_state: dict | None = None

    def _load_or_create(self) -> dict[str, Any]:
        if self.path.exists():
            try:
                with self.path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        else:
            data = {}
        changed = False
        if not data.get("receiver_id"):
            data["receiver_id"] = str(uuid.uuid4())
            changed = True
        data.setdefault("schema_version", "dextilt.receiver_state.v1")
        data.setdefault("paired_devices", {})
        data.setdefault("nonce_cache", {})
        data.setdefault("last_command", None)
        data.setdefault("last_error", None)
        data.setdefault("last_calibration", None)
        data.setdefault("last_gesture_preview", None)
        data.setdefault("created_at_ms", now_ms())
        if changed or not self.path.exists():
            self._save_unlocked(data)
        return data

    def _save_unlocked(self, data: dict[str, Any] | None = None) -> None:
        payload = self.data if data is None else data
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
            f.write("\n")
        tmp.replace(self.path)

    def save(self) -> None:
        with self.lock:
            self._save_unlocked()

    @property
    def receiver_id(self) -> str:
        return str(self.data["receiver_id"])

    def paired_device_count(self) -> int:
        return len(self.data.get("paired_devices", {}))

    def pair_device(self, device_id: str, device_name: str, shared_secret: str, source_ip: str | None) -> dict[str, Any]:
        with self.lock:
            record = {
                "device_id": device_id,
                "device_name": device_name or "Android DexTilt",
                "shared_secret": shared_secret,
                "paired_at_ms": now_ms(),
                "last_seen_ms": None,
                "last_source_ip": source_ip,
            }
            self.data.setdefault("paired_devices", {})[device_id] = record
            self.data.setdefault("nonce_cache", {})[device_id] = {}
            self._save_unlocked()
            return dict(record)

    def get_device(self, device_id: str) -> dict[str, Any] | None:
        device = self.data.get("paired_devices", {}).get(device_id)
        return dict(device) if device else None

    def mark_seen(self, device_id: str, source_ip: str | None) -> None:
        with self.lock:
            device = self.data.get("paired_devices", {}).get(device_id)
            if device:
                device["last_seen_ms"] = now_ms()
                device["last_source_ip"] = source_ip
                self._save_unlocked()

    def reset_pairings(self) -> None:
        with self.lock:
            self.data["paired_devices"] = {}
            self.data["nonce_cache"] = {}
            self._save_unlocked()

    def remember_nonce(self, device_id: str, nonce: str, timestamp_ms: int, window_seconds: int) -> bool:
        """Returns True when nonce was stored; False means replay."""
        cutoff = now_ms() - (window_seconds * 1000 * 2)
        with self.lock:
            by_device = self.data.setdefault("nonce_cache", {}).setdefault(device_id, {})
            old_keys = [key for key, value in by_device.items() if int(value) < cutoff]
            for key in old_keys:
                by_device.pop(key, None)
            if nonce in by_device:
                self._save_unlocked()
                return False
            by_device[nonce] = int(timestamp_ms)
            # Bound cache size per device.
            if len(by_device) > 500:
                for key, _ in sorted(by_device.items(), key=lambda item: int(item[1]))[: len(by_device) - 500]:
                    by_device.pop(key, None)
            self._save_unlocked()
            return True

    def set_last_command(self, command: dict[str, Any]) -> None:
        with self.lock:
            self.data["last_command"] = command
            self.data["last_error"] = None if command.get("accepted") else command.get("error_message")
            self._save_unlocked()

    def set_last_calibration(self, update: dict[str, Any]) -> None:
        with self.lock:
            self.data["last_calibration"] = update
            self._save_unlocked()

    def set_last_phone_state(self, state: dict) -> None:
        with self.lock:
            self._live_phone_state = state

    def get_last_phone_state(self) -> dict | None:
        with self.lock:
            return self._live_phone_state

    def set_last_gesture_preview(self, preview: dict) -> None:
        with self.lock:
            self.data["last_gesture_preview"] = preview
            self._save_unlocked()

    def get_last_gesture_preview(self) -> dict | None:
        with self.lock:
            return self.data.get("last_gesture_preview")

    def status_snapshot(self, port: int = DEFAULT_PORT) -> dict[str, Any]:
        paired = self.data.get("paired_devices", {})
        devices = []
        for device_id, record in paired.items():
            devices.append(
                {
                    "device_id": device_id,
                    "device_name": record.get("device_name"),
                    "paired_at_ms": record.get("paired_at_ms"),
                    "last_seen_ms": record.get("last_seen_ms"),
                    "last_source_ip": record.get("last_source_ip"),
                }
            )
        return {
            "receiver_id": self.receiver_id,
            "port": port,
            "paired_device_count": len(devices),
            "paired_devices": devices,
            "last_command": self.data.get("last_command"),
            "last_error": self.data.get("last_error"),
            "last_calibration": self.data.get("last_calibration"),
        }
