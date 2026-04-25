from __future__ import annotations

import json
import os
import shutil
import socket
from pathlib import Path
from typing import Any

from .constants import DEFAULT_PORT, DISPLAY_NAME


def dextilt_home() -> Path:
    return Path(os.environ.get("DEXTILT_HOME", "~/.dextilt")).expanduser()


def default_config_path() -> Path:
    return dextilt_home() / "config.json"


def default_state_path() -> Path:
    return dextilt_home() / "state.json"


def default_log_path() -> Path:
    return dextilt_home() / "logs" / "dextilt_receiver.log"


def default_config() -> dict[str, Any]:
    return {
        "display_name": DISPLAY_NAME,
        "host": "0.0.0.0",
        "port": DEFAULT_PORT,
        "advertised_host": None,
        "dashboard_local_url": f"http://127.0.0.1:{DEFAULT_PORT}/status",
        "pairing_token_ttl_seconds": 300,
        "timestamp_window_seconds": 60,
        "command_cooldown_seconds": 2.0,
        "rate_limit_per_minute": 30,
        "max_payload_bytes": 32768,
        "dry_run_actions": False,
        "log_path": str(default_log_path()),
        "state_path": str(default_state_path()),
        "commands": {
            "open_gpt_default_browser": {
                "type": "open_url",
                "url": "https://chatgpt.com/",
                "success_title": "DexTilt",
                "success_message": "Open GPT triggered",
            },
            "notify_test": {
                "type": "notification",
                "title": "DexTilt",
                "message": "Test command received",
            },
            "open_test_url": {
                "type": "open_url",
                "url": "https://example.com/",
                "success_title": "DexTilt",
                "success_message": "Test URL triggered",
            },
        },
    }


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def expand_config_paths(config: dict[str, Any]) -> dict[str, Any]:
    for key in ("log_path", "state_path"):
        if key in config and config[key]:
            config[key] = str(Path(str(config[key])).expanduser())
    return config


def load_config(path: str | Path | None = None, *, create_if_missing: bool = True) -> dict[str, Any]:
    config_path = Path(path).expanduser() if path else default_config_path()
    config = default_config()
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as f:
            loaded = json.load(f)
        config = deep_merge(config, loaded)
    elif create_if_missing:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with config_path.open("w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, sort_keys=True)
            f.write("\n")
    return expand_config_paths(config)


def copy_example_config(destination: str | Path | None = None) -> Path:
    dest = Path(destination).expanduser() if destination else default_config_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        here = Path(__file__).resolve()
        repo_example = here.parents[3] / "config.example.json"
        if repo_example.exists():
            shutil.copy2(repo_example, dest)
        else:
            with dest.open("w", encoding="utf-8") as f:
                json.dump(default_config(), f, indent=2, sort_keys=True)
                f.write("\n")
    return dest


def detect_lan_ip() -> str:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.2)
        sock.connect(("192.0.2.1", 80))
        ip = sock.getsockname()[0]
        sock.close()
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    try:
        ip = socket.gethostbyname(socket.gethostname())
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    return "127.0.0.1"


def advertised_host(config: dict[str, Any]) -> str:
    return str(config.get("advertised_host") or os.environ.get("DEXTILT_ADVERTISED_HOST") or detect_lan_ip())
