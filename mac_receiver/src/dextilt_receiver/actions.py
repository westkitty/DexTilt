from __future__ import annotations

import ctypes
import platform
import shutil
import subprocess
import time
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
        action = self.commands.get(command_id)
        return bool(action) and action.get("enabled", True) is not False

    def command_ids(self) -> list[str]:
        return sorted(k for k, v in self.commands.items() if v.get("enabled", True) is not False)

    def command_details(self) -> dict[str, Any]:
        return {key: dict(value) for key, value in sorted(self.commands.items())}

    def notify(self, title: str, message: str) -> ActionResult:
        return self._notification({"type": "notification", "title": title, "message": message})

    def run(self, command_id: str) -> ActionResult:
        action = self.commands.get(command_id)
        if not action:
            return ActionResult(False, "unknown", f"Unknown command ID: {command_id}")
        if action.get("enabled", True) is False:
            return ActionResult(False, "disabled", f"Command is disabled: {command_id}")
        action_type = action.get("type")
        if action_type == "open_url":
            return self._open_url(action)
        if action_type == "open_app":
            return self._open_app(action)
        if action_type == "notification":
            return self._notification(action)
        if action_type == "key_press":
            return self._key_press(action)
        if action_type == "hotkey":
            return self._hotkey(action)
        if action_type == "hid_middle_click":
            return self._hid_middle_click(action)
        return ActionResult(False, str(action_type), f"Unsupported action type for command {command_id}: {action_type}")

    def _success_message(self, action: dict[str, Any], fallback: str) -> str:
        return str(action.get("success_message") or fallback)

    def _open_url(self, action: dict[str, Any]) -> ActionResult:
        url = str(action.get("url") or action.get("target") or "")
        browser_app = action.get("browser_app")
        if not url.startswith(("https://", "http://")):
            return ActionResult(False, "open_url", "Configured URL is not http/https.")
        if self.dry_run:
            target = f" in {browser_app}" if browser_app else ""
            return ActionResult(True, "open_url", f"DRY RUN: would open {url}{target}")
        if platform.system() != "Darwin":
            return ActionResult(False, "open_url", "Open URL action is macOS-only in DexTilt v1.")
        cmd = ["open", "-a", str(browser_app), url] if browser_app else ["open", url]
        try:
            completed = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=8)
        except Exception as exc:
            return ActionResult(False, "open_url", f"Failed to run macOS open command: {exc}")
        if completed.returncode == 0:
            return ActionResult(True, "open_url", self._success_message(action, f"Opened {url}"), completed.returncode)
        detail = (completed.stderr or completed.stdout or "open command failed").strip()
        return ActionResult(False, "open_url", detail, completed.returncode)

    def _open_app(self, action: dict[str, Any]) -> ActionResult:
        app_name = str(action.get("app") or action.get("target") or "").strip()
        if not app_name:
            return ActionResult(False, "open_app", "No app name configured.")
        if self.dry_run:
            return ActionResult(True, "open_app", f"DRY RUN: would open app {app_name}")
        if platform.system() != "Darwin":
            return ActionResult(False, "open_app", "Open app action is macOS-only in DexTilt v1.")
        try:
            completed = subprocess.run(["open", "-a", app_name], check=False, capture_output=True, text=True, timeout=8)
        except Exception as exc:
            return ActionResult(False, "open_app", f"Failed to open app {app_name}: {exc}")
        if completed.returncode == 0:
            return ActionResult(True, "open_app", self._success_message(action, f"Opened {app_name}"), completed.returncode)
        detail = (completed.stderr or completed.stdout or f"open -a {app_name} failed").strip()
        return ActionResult(False, "open_app", detail, completed.returncode)

    def _notification(self, action: dict[str, Any]) -> ActionResult:
        title = str(action.get("title") or "DexTilt")
        message = str(action.get("message") or action.get("target") or "DexTilt command received")
        if self.dry_run:
            return ActionResult(True, "notification", f"DRY RUN: would notify {title}: {message}")
        if platform.system() != "Darwin":
            return ActionResult(False, "notification", "macOS notification action is macOS-only in DexTilt v1.")
        def applescript_quote(value: str) -> str:
            return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
        script = f"display notification {applescript_quote(message)} with title {applescript_quote(title)}"
        try:
            completed = subprocess.run(["osascript", "-e", script], check=False, capture_output=True, text=True, timeout=8)
        except Exception as exc:
            return ActionResult(False, "notification", f"Failed to run osascript notification: {exc}")
        if completed.returncode == 0:
            return ActionResult(True, "notification", self._success_message(action, message), completed.returncode)
        detail = (completed.stderr or completed.stdout or "notification command failed").strip()
        return ActionResult(False, "notification", detail, completed.returncode)

    def _key_press(self, action: dict[str, Any]) -> ActionResult:
        key = str(action.get("key") or action.get("target") or "").lower().strip()
        key_codes = {
            "enter": 36,
            "return": 36,
            "space": 49,
            "escape": 53,
            "esc": 53,
            "tab": 48,
        }
        if key not in key_codes:
            return ActionResult(False, "key_press", f"Unsupported key_press target: {key}")
        if self.dry_run:
            return ActionResult(True, "key_press", f"DRY RUN: would press {key}")
        if platform.system() != "Darwin":
            return ActionResult(False, "key_press", "Key press action is macOS-only in DexTilt v1.")
        script = f'tell application "System Events" to key code {key_codes[key]}'
        try:
            completed = subprocess.run(["osascript", "-e", script], check=False, capture_output=True, text=True, timeout=8)
        except Exception as exc:
            return ActionResult(False, "key_press", f"Failed to press {key}: {exc}")
        if completed.returncode == 0:
            return ActionResult(True, "key_press", self._success_message(action, f"Pressed {key}"), completed.returncode)
        detail = (completed.stderr or completed.stdout or "key press failed").strip()
        return ActionResult(False, "key_press", detail, completed.returncode)

    def _hotkey(self, action: dict[str, Any]) -> ActionResult:
        key = str(action.get("key") or action.get("target") or "").lower().strip()
        modifiers = [str(x).lower().strip() for x in action.get("modifiers", [])]
        key_codes = {
            "enter": 36,
            "return": 36,
            "space": 49,
            "escape": 53,
            "esc": 53,
            "tab": 48,
        }
        modifier_map = {
            "command": "command down",
            "cmd": "command down",
            "shift": "shift down",
            "option": "option down",
            "alt": "option down",
            "control": "control down",
            "ctrl": "control down",
        }
        if key not in key_codes:
            return ActionResult(False, "hotkey", f"Unsupported hotkey key: {key}")
        modifier_terms = []
        for modifier in modifiers:
            term = modifier_map.get(modifier)
            if term and term not in modifier_terms:
                modifier_terms.append(term)
        if self.dry_run:
            return ActionResult(True, "hotkey", f"DRY RUN: would press {'+'.join(modifiers + [key])}")
        if platform.system() != "Darwin":
            return ActionResult(False, "hotkey", "Hotkey action is macOS-only in DexTilt v1.")
        using = ""
        if modifier_terms:
            using = " using {" + ", ".join(modifier_terms) + "}"
        script = f'tell application "System Events" to key code {key_codes[key]}{using}'
        try:
            completed = subprocess.run(["osascript", "-e", script], check=False, capture_output=True, text=True, timeout=8)
        except Exception as exc:
            return ActionResult(False, "hotkey", f"Failed to press hotkey {modifiers}+{key}: {exc}")
        if completed.returncode == 0:
            return ActionResult(True, "hotkey", self._success_message(action, f"Pressed hotkey {'+'.join(modifiers + [key])}"), completed.returncode)
        detail = (completed.stderr or completed.stdout or "hotkey failed").strip()
        return ActionResult(False, "hotkey", detail, completed.returncode)

    def _hid_middle_click(self, action: dict[str, Any]) -> ActionResult:
        if self.dry_run:
            return ActionResult(True, "hid_middle_click", "DRY RUN: would send middle mouse click")
        if platform.system() != "Darwin":
            return ActionResult(False, "hid_middle_click", "Middle-click action is macOS-only in DexTilt v1.")
        try:
            self._post_middle_click()
        except Exception as exc:
            return ActionResult(False, "hid_middle_click", f"Failed to send middle click. Check macOS Accessibility permission for Terminal/Python. Detail: {exc}")
        return ActionResult(True, "hid_middle_click", self._success_message(action, "Middle click sent"), 0)

    def _post_middle_click(self) -> None:
        class CGPoint(ctypes.Structure):
            _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]

        app_services = ctypes.CDLL("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
        app_services.CGEventCreate.restype = ctypes.c_void_p
        app_services.CGEventGetLocation.argtypes = [ctypes.c_void_p]
        app_services.CGEventGetLocation.restype = CGPoint
        app_services.CGEventCreateMouseEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint32, CGPoint, ctypes.c_uint32]
        app_services.CGEventCreateMouseEvent.restype = ctypes.c_void_p
        app_services.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
        app_services.CGEventPost.restype = None

        current = app_services.CGEventCreate(None)
        loc = app_services.CGEventGetLocation(current)

        kCGHIDEventTap = 0
        kCGEventOtherMouseDown = 25
        kCGEventOtherMouseUp = 26
        kCGMouseButtonCenter = 2

        down = app_services.CGEventCreateMouseEvent(None, kCGEventOtherMouseDown, loc, kCGMouseButtonCenter)
        up = app_services.CGEventCreateMouseEvent(None, kCGEventOtherMouseUp, loc, kCGMouseButtonCenter)

        app_services.CGEventPost(kCGHIDEventTap, down)
        time.sleep(0.05)
        app_services.CGEventPost(kCGHIDEventTap, up)

        try:
            core_foundation = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
            core_foundation.CFRelease.argtypes = [ctypes.c_void_p]
            for obj in (current, down, up):
                if obj:
                    core_foundation.CFRelease(obj)
        except Exception:
            pass
