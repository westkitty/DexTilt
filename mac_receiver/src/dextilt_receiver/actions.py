from __future__ import annotations

import platform
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any


@dataclass
class ActionResult:
    ok: bool
    action_type: str
    message: str
    returncode: int | None = None


class ActionRunner:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.commands = config.get("commands", {})
        self.dry_run = bool(config.get("dry_run_actions", False))

    def is_known_command(self, command_id: str) -> bool:
        return command_id in self.commands

    def command_ids(self) -> list[str]:
        return sorted(self.commands.keys())

    def run(self, command_id: str) -> ActionResult:
        action = self.commands.get(command_id)
        if not action:
            return ActionResult(False, "unknown", f"Unknown command ID: {command_id}")
        action_type = action.get("type")
        if action_type == "open_url":
            return self._open_url(action)
        if action_type == "notification":
            return self._notification(action)
        return ActionResult(False, str(action_type), f"Unsupported action type for command {command_id}: {action_type}")

    def _open_url(self, action: dict[str, Any]) -> ActionResult:
        url = str(action.get("url", ""))
        browser_app = action.get("browser_app")
        if not url.startswith(("https://", "http://")):
            return ActionResult(False, "open_url", "Configured URL is not http/https.")
        if self.dry_run:
            target = f" in {browser_app}" if browser_app else ""
            return ActionResult(True, "open_url", f"DRY RUN: would open {url}{target}")
        if platform.system() != "Darwin":
            return ActionResult(False, "open_url", "Open URL action is macOS-only in DexTilt v1. Enable dry_run_actions for non-macOS tests.")
        if browser_app:
            if shutil.which("open") is None:
                return ActionResult(False, "open_url", "macOS open command was not found.")
            cmd = ["open", "-a", str(browser_app), url]
        else:
            cmd = ["open", url]
        try:
            completed = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=8)
        except Exception as exc:
            return ActionResult(False, "open_url", f"Failed to run macOS open command: {exc}")
        if completed.returncode == 0:
            return ActionResult(True, "open_url", str(action.get("success_message") or f"Opened {url}"), completed.returncode)
        detail = (completed.stderr or completed.stdout or "open command failed").strip()
        return ActionResult(False, "open_url", detail, completed.returncode)

    def _notification(self, action: dict[str, Any]) -> ActionResult:
        title = str(action.get("title") or "DexTilt")
        message = str(action.get("message") or "DexTilt command received")
        if self.dry_run:
            return ActionResult(True, "notification", f"DRY RUN: would notify {title}: {message}")
        if platform.system() != "Darwin":
            return ActionResult(False, "notification", "macOS notification action is macOS-only in DexTilt v1. Enable dry_run_actions for non-macOS tests.")
        script = f'display notification {message!r} with title {title!r}'
        try:
            completed = subprocess.run(["osascript", "-e", script], check=False, capture_output=True, text=True, timeout=8)
        except Exception as exc:
            return ActionResult(False, "notification", f"Failed to run osascript notification: {exc}")
        if completed.returncode == 0:
            return ActionResult(True, "notification", message, completed.returncode)
        detail = (completed.stderr or completed.stdout or "notification command failed").strip()
        return ActionResult(False, "notification", detail, completed.returncode)
