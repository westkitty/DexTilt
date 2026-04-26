from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import ValidationError

from .actions import ActionRunner
from .config import advertised_host, load_config
from .constants import COMMAND_PROTOCOL, PAIRING_PROTOCOL
from .crypto import generate_token, redact_mapping, sign_command, verify_command_signature
from .dashboard import qr_data_url, render_dashboard
from .logging_utils import EventLogger
from .models import CalibrationUpdate, CommandMessage, PairRequest, SignedEnvelope, clamp_phone_state, clamp_preview_point
from .pairing import PairingManager
from .rate_limit import RateLimiter
from .state import StateStore, now_ms


@dataclass
class RuntimeContext:
    config: dict[str, Any]
    state: StateStore
    pairing: PairingManager
    limiter: RateLimiter
    logger: EventLogger
    actions: ActionRunner


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def is_local_request(request: Request) -> bool:
    ip = client_ip(request)
    return ip in {"127.0.0.1", "::1", "localhost", "testclient"}


def make_context(
    *,
    config_path: str | Path | None = None,
    state_path: str | Path | None = None,
    log_path: str | Path | None = None,
    dry_run_actions: bool | None = None,
) -> RuntimeContext:
    config = load_config(config_path)
    config["_config_path"] = str(Path(config_path).expanduser()) if config_path is not None else str(Path.home() / ".dextilt" / "config.json")
    if state_path is not None:
        config["state_path"] = str(Path(state_path).expanduser())
    if log_path is not None:
        config["log_path"] = str(Path(log_path).expanduser())
    if dry_run_actions is not None:
        config["dry_run_actions"] = bool(dry_run_actions)
    state = StateStore(config["state_path"])

    # Safety rule: dashboard phone-control requests are ephemeral.
    # Never let old Start Training / Arm / Cancel clicks survive receiver launch.
    state.data["phone_control_queue"] = []
    state.save()

    pairing = PairingManager(int(config.get("pairing_token_ttl_seconds", 300)))
    limiter = RateLimiter(int(config.get("rate_limit_per_minute", 30)), float(config.get("command_cooldown_seconds", 2.0)))
    logger = EventLogger(config["log_path"])
    actions = ActionRunner(config)
    return RuntimeContext(config=config, state=state, pairing=pairing, limiter=limiter, logger=logger, actions=actions)


def json_error(status_code: int, code: str, user_message: str, **extra: Any) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"ok": False, "error_code": code, "user_message": user_message, **extra})


def validate_signed_envelope(
    payload: dict[str, Any],
    ctx: RuntimeContext,
    source_ip: str,
    *,
    require_known_command: bool,
) -> tuple[bool, str, str, CommandMessage | None]:
    model_cls = CommandMessage if require_known_command else SignedEnvelope
    try:
        command = model_cls.model_validate(payload)
    except ValidationError as exc:
        return False, "invalid_shape", "DexTilt received a command with missing or invalid fields. Update/retry from the Android app.", None
    if command.protocol != COMMAND_PROTOCOL:
        return False, "unknown_protocol", "DexTilt rejected the command because the phone used an unsupported protocol version. Update both DexTilt apps.", command
    if command.receiver_id != ctx.state.receiver_id:
        return False, "wrong_receiver", "DexTilt rejected the command because it was meant for a different Mac receiver. Re-pair the phone with this Mac.", command
    if require_known_command and not ctx.actions.is_known_command(command.command_id):
        return False, "unknown_command", "DexTilt rejected the command because this Mac does not allow that command ID.", command
    device = ctx.state.get_device(command.device_id)
    if not device:
        return False, "unpaired_device", "DexTilt rejected the command because this Android device is not paired. Pair the phone with the Mac again.", command
    skew = abs(now_ms() - int(command.timestamp_ms))
    window_ms = int(ctx.config.get("timestamp_window_seconds", 60)) * 1000
    if skew > window_ms:
        return False, "expired_timestamp", "DexTilt rejected the command because the phone and Mac clocks were too far apart or the message was stale.", command
    if not verify_command_signature(command.model_dump(), str(device["shared_secret"])):
        return False, "invalid_signature", "DexTilt rejected the command because the phone and Mac pairing credentials did not match. Re-pair the phone with the Mac.", command
    remembered = ctx.state.remember_nonce(command.device_id, command.nonce, command.timestamp_ms, int(ctx.config.get("timestamp_window_seconds", 60)))
    if not remembered:
        return False, "replay", "DexTilt rejected a repeated command message. Try the gesture or manual button again.", command
    ctx.state.mark_seen(command.device_id, source_ip)
    return True, "ok", "ok", command


def create_app(
    *,
    config_path: str | Path | None = None,
    state_path: str | Path | None = None,
    log_path: str | Path | None = None,
    dry_run_actions: bool | None = None,
) -> FastAPI:
    ctx = make_context(config_path=config_path, state_path=state_path, log_path=log_path, dry_run_actions=dry_run_actions)
    app = FastAPI(title="DexTilt Mac Receiver", version="0.1.0")
    app.state.dextilt = ctx

    def save_runtime_config() -> None:
        path = Path(str(ctx.config.get("_config_path") or Path.home() / ".dextilt" / "config.json")).expanduser()
        payload = {k: v for k, v in ctx.config.items() if not str(k).startswith("_")}
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
            f.write("\n")
        tmp.replace(path)
        ctx.actions.commands = ctx.config.get("commands", {})

    def require_local_dashboard(request: Request) -> JSONResponse | None:
        if not is_local_request(request):
            return json_error(403, "local_only", "This dashboard control is local-Mac only.")
        return None

    def normalize_dashboard_command(payload: dict[str, Any]) -> tuple[str | None, dict[str, Any] | None, str | None]:
        command_id = str(payload.get("command_id") or "").strip()
        if not re.match(r"^[a-z][a-z0-9_]{1,80}$", command_id):
            return None, None, "Command ID must be snake_case and start with a lowercase letter."
        action_type = str(payload.get("type") or "").strip()
        allowed = {"open_url", "open_app", "notification", "key_press", "hid_middle_click"}
        if action_type not in allowed:
            return None, None, f"Unsupported action type: {action_type}"
        target = str(payload.get("target") or "").strip()
        action: dict[str, Any] = {
            "type": action_type,
            "label": str(payload.get("label") or command_id).strip()[:120],
            "description": str(payload.get("description") or "").strip()[:500],
            "enabled": bool(payload.get("enabled", True)),
            "success_message": str(payload.get("success_message") or "").strip()[:240],
        }
        if action_type == "open_url":
            if not target.startswith(("https://", "http://")):
                return None, None, "open_url target must start with http:// or https://."
            action["url"] = target
        elif action_type == "open_app":
            if not target:
                return None, None, "open_app target must be an app name."
            action["app"] = target[:120]
        elif action_type == "notification":
            action["title"] = str(payload.get("title") or "DexTilt").strip()[:120]
            action["message"] = str(payload.get("message") or target or "DexTilt notification").strip()[:300]
        elif action_type == "key_press":
            key = (target or str(payload.get("key") or "")).lower().strip()
            if key not in {"enter", "return", "space", "escape", "esc", "tab"}:
                return None, None, "key_press target must be enter, return, space, escape, esc, or tab."
            action["key"] = key
        elif action_type == "hid_middle_click":
            action["target"] = "middle_mouse"
        return command_id, action, None


    @app.middleware("http")
    async def payload_size_guard(request: Request, call_next):
        max_bytes = int(ctx.config.get("max_payload_bytes", 32768))
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > max_bytes:
            return json_error(413, "payload_too_large", "DexTilt rejected a request because it was too large.")
        return await call_next(request)

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "ok": True,
            "service": "DexTilt Mac Receiver",
            "protocol": COMMAND_PROTOCOL,
            "receiver_id": ctx.state.receiver_id,
            "port": int(ctx.config.get("port", 47391)),
            "paired_device_count": ctx.state.paired_device_count(),
        }

    @app.get("/api/status")
    async def status_json() -> dict[str, Any]:
        return {
            "ok": True,
            "service": "DexTilt Mac Receiver",
            **ctx.state.status_snapshot(int(ctx.config.get("port", 47391))),
            "commands": ctx.actions.command_ids(),
            "log_path": str(ctx.logger.path),
        }

    @app.get("/status", response_class=HTMLResponse)
    async def dashboard() -> HTMLResponse:
        status = ctx.state.status_snapshot(int(ctx.config.get("port", 47391)))
        html = render_dashboard(status, ctx.actions.command_details(), ctx.logger.read_recent(20))
        return HTMLResponse(html)

    @app.get("/pairing")
    async def pairing(request: Request) -> JSONResponse:
        if not is_local_request(request):
            return json_error(403, "local_only", "For safety, the DexTilt pairing QR can only be generated from the Mac itself. Open the dashboard at http://127.0.0.1:47391/status.")
        host = advertised_host(ctx.config)
        port = int(ctx.config.get("port", 47391))
        payload = ctx.pairing.issue(host=host, port=port, receiver_id=ctx.state.receiver_id)
        ctx.logger.append({"event": "pairing_token_issued", "source_ip": client_ip(request), "receiver_id": ctx.state.receiver_id, "expires_at_ms": payload["expires_at_ms"]})
        return JSONResponse({"ok": True, "payload": payload, "qr_data_url": qr_data_url(payload)})

    @app.post("/pair")
    async def pair(request: Request) -> JSONResponse:
        source = client_ip(request)
        try:
            payload = await request.json()
        except Exception:
            return json_error(400, "malformed_json", "DexTilt could not read the pairing request. Try scanning the QR code again.")
        try:
            req = PairRequest.model_validate(payload)
        except ValidationError:
            return json_error(400, "invalid_pair_request", "DexTilt received an incomplete pairing request. Update/retry from the Android app.")
        if req.protocol != PAIRING_PROTOCOL:
            return json_error(400, "unknown_pairing_protocol", "DexTilt rejected pairing because the phone used an unsupported pairing protocol.")
        if req.receiver_id != ctx.state.receiver_id:
            return json_error(403, "wrong_receiver", "DexTilt rejected pairing because the QR code belongs to a different Mac receiver.")
        ok, message = ctx.pairing.verify_and_consume(req.pairing_token)
        if not ok:
            ctx.logger.append({"event": "pairing_rejected", "source_ip": source, "device_id": req.device_id, "reason": message})
            return json_error(403, "pairing_token_rejected", message)
        shared_secret = generate_token(32)
        ctx.state.pair_device(req.device_id, req.device_name, shared_secret, source)
        ctx.logger.append({"event": "pairing_accepted", "source_ip": source, "device_id": req.device_id, "receiver_id": ctx.state.receiver_id})
        return JSONResponse(
            {
                "ok": True,
                "protocol": PAIRING_PROTOCOL,
                "receiver_id": ctx.state.receiver_id,
                "device_id": req.device_id,
                "shared_secret": shared_secret,
                "user_message": "DexTilt paired this Android device with the Mac receiver.",
            }
        )

    @app.post("/command")
    async def command(request: Request) -> JSONResponse:
        source = client_ip(request)
        allowed, reason = ctx.limiter.allow_request(f"request:{source}")
        if not allowed:
            return json_error(429, "rate_limited", reason)
        try:
            payload = await request.json()
        except Exception:
            ctx.logger.append({"event": "command_rejected", "source_ip": source, "auth_result": "malformed_json"})
            return json_error(400, "malformed_json", "DexTilt could not read the command request. Try again from the Android app.")
        if not isinstance(payload, dict):
            return json_error(400, "malformed_json", "DexTilt expected a JSON object command message.")
        ok, code, message, command_model = validate_signed_envelope(payload, ctx, source, require_known_command=True)
        command_id = payload.get("command_id") if isinstance(payload, dict) else None
        device_id = payload.get("device_id") if isinstance(payload, dict) else None
        if not ok:
            event = {"event": "command_rejected", "source_ip": source, "device_id": device_id, "command_id": command_id, "auth_result": code, "error_message": message, "payload": redact_mapping(payload)}
            ctx.logger.append(event)
            ctx.state.set_last_command({"accepted": False, "source_ip": source, "device_id": device_id, "command_id": command_id, "auth_result": code, "error_message": message, "timestamp_ms": now_ms()})
            status = 403 if code in {"invalid_signature", "wrong_receiver", "unpaired_device", "replay"} else 400
            return json_error(status, code, message)
        assert command_model is not None
        allowed_success, cooldown_message = ctx.limiter.allow_success(f"success:{command_model.device_id}:{command_model.command_id}")
        if not allowed_success:
            ctx.logger.append({"event": "command_rejected", "source_ip": source, "device_id": command_model.device_id, "command_id": command_model.command_id, "auth_result": "cooldown", "error_message": cooldown_message})
            return json_error(429, "cooldown", cooldown_message)
        result = ctx.actions.run(command_model.command_id)
        event = {
            "event": "command_received",
            "source_ip": source,
            "receiver_id": ctx.state.receiver_id,
            "device_id": command_model.device_id,
            "command_id": command_model.command_id,
            "gesture_id": command_model.gesture_id,
            "confidence": command_model.confidence,
            "auth_result": "accepted",
            "action_result": "ok" if result.ok else "failed",
            "action_message": result.message,
        }
        ctx.logger.append(event)
        ctx.state.set_last_command({"accepted": result.ok, **event, "timestamp_ms": now_ms()})
        if result.ok:
            return JSONResponse({"ok": True, "accepted": True, "action_result": "ok", "user_message": result.message})
        return json_error(500, "action_failed", f"DexTilt accepted the command but the Mac action failed: {result.message}")


    @app.post("/event")
    async def phone_event(request: Request) -> JSONResponse:
        source = client_ip(request)
        try:
            payload = await request.json()
        except Exception:
            ctx.logger.append({"event": "phone_event_rejected", "source_ip": source, "auth_result": "malformed_json"})
            return json_error(400, "malformed_json", "DexTilt could not read the phone event.")
        if not isinstance(payload, dict):
            return json_error(400, "malformed_json", "DexTilt expected a JSON object phone event.")
        ok, code, message, command_model = validate_signed_envelope(payload, ctx, source, require_known_command=False)
        if not ok:
            ctx.logger.append({"event": "phone_event_rejected", "source_ip": source, "auth_result": code, "error_message": message, "payload": redact_mapping(payload)})
            return json_error(403, code, message)
        assert command_model is not None
        event_id = str(payload.get("event_id") or command_model.gesture_id or command_model.command_id)[:80]
        detail = str(payload.get("detail") or event_id)[:500]
        event = {
            "event": "phone_event",
            "source_ip": source,
            "receiver_id": ctx.state.receiver_id,
            "device_id": command_model.device_id,
            "event_id": event_id,
            "detail": detail,
            "confidence": command_model.confidence,
            "auth_result": "accepted",
        }
        ctx.logger.append(event)
        ctx.state.set_last_command({"accepted": True, **event, "timestamp_ms": now_ms()})
        result = ctx.actions.notify("DexTilt", detail)
        if result.ok:
            return JSONResponse({"ok": True, "accepted": True, "action_result": "ok", "user_message": detail})
        return json_error(500, "event_notification_failed", f"DexTilt accepted the phone event but notification failed: {result.message}")

    @app.post("/calibration")
    async def calibration(request: Request) -> JSONResponse:
        source = client_ip(request)
        try:
            payload = await request.json()
        except Exception:
            return json_error(400, "malformed_json", "DexTilt could not read the calibration update.")
        if not isinstance(payload, dict):
            return json_error(400, "malformed_json", "DexTilt expected a JSON object calibration update.")
        ok, code, message, command_model = validate_signed_envelope(payload, ctx, source, require_known_command=False)
        if not ok:
            ctx.logger.append({"event": "calibration_rejected", "source_ip": source, "auth_result": code, "error_message": message})
            return json_error(403, code, message)
        try:
            update = CalibrationUpdate.model_validate(payload)
        except ValidationError:
            return json_error(400, "invalid_calibration_update", "DexTilt received an incomplete calibration update.")
        event = {
            "event": "calibration_update",
            "source_ip": source,
            "device_id": update.device_id,
            "step_id": update.step_id,
            "step_label": update.step_label,
            "status": update.status,
            "detail": update.detail,
        }
        ctx.state.set_last_calibration({**event, "timestamp_ms": now_ms()})
        ctx.logger.append(event)
        return JSONResponse({"ok": True, "accepted": True, "user_message": "Calibration update received."})


    @app.get("/api/commands")
    async def api_commands() -> dict[str, Any]:
        return {"ok": True, "commands": ctx.actions.command_details()}

    @app.post("/api/commands/upsert")
    async def api_commands_upsert(request: Request) -> JSONResponse:
        local_error = require_local_dashboard(request)
        if local_error is not None:
            return local_error
        try:
            payload = await request.json()
        except Exception:
            return json_error(400, "malformed_json", "Could not read command JSON.")
        if not isinstance(payload, dict):
            return json_error(400, "malformed_json", "Expected a JSON object.")
        command_id, action, error_message = normalize_dashboard_command(payload)
        if error_message:
            return json_error(400, "invalid_command", error_message)
        assert command_id is not None and action is not None
        ctx.config.setdefault("commands", {})[command_id] = action
        save_runtime_config()
        ctx.logger.append({"event": "dashboard_command_upserted", "command_id": command_id, "action_type": action.get("type")})
        return JSONResponse({"ok": True, "command_id": command_id, "action": action})

    @app.post("/api/commands/delete")
    async def api_commands_delete(request: Request) -> JSONResponse:
        local_error = require_local_dashboard(request)
        if local_error is not None:
            return local_error
        payload = await request.json()
        command_id = str(payload.get("command_id") or "").strip()
        if command_id not in ctx.config.get("commands", {}):
            return json_error(404, "unknown_command", "Command not found.")
        ctx.config["commands"].pop(command_id, None)
        save_runtime_config()
        ctx.logger.append({"event": "dashboard_command_deleted", "command_id": command_id})
        return JSONResponse({"ok": True, "deleted": command_id})

    @app.post("/api/commands/test")
    async def api_commands_test(request: Request) -> JSONResponse:
        local_error = require_local_dashboard(request)
        if local_error is not None:
            return local_error
        payload = await request.json()
        command_id = str(payload.get("command_id") or "").strip()
        result = ctx.actions.run(command_id)
        ctx.logger.append({"event": "dashboard_command_test", "command_id": command_id, "action_result": "ok" if result.ok else "failed", "message": result.message})
        if result.ok:
            return JSONResponse({"ok": True, "command_id": command_id, "action_result": "ok", "user_message": result.message})
        return json_error(500, "action_failed", result.message)

    @app.get("/settings")
    async def get_settings() -> dict[str, Any]:
        return {"ok": True, "settings": ctx.config.setdefault("notification_settings", {})}

    @app.post("/settings")
    async def post_settings(request: Request) -> JSONResponse:
        local_error = require_local_dashboard(request)
        if local_error is not None:
            return local_error
        payload = await request.json()
        current = ctx.config.setdefault("notification_settings", {})
        for key in ["training_notifications", "runtime_notifications", "local_test_notifications", "command_result_notifications"]:
            if key in payload:
                current[key] = bool(payload[key])
        if payload.get("face_down_stable") in {"off", "training_only", "always"}:
            current["face_down_stable"] = payload["face_down_stable"]
        save_runtime_config()
        ctx.logger.append({"event": "dashboard_settings_updated", "settings": current})
        return JSONResponse({"ok": True, "settings": current})

    @app.post("/phone-control/queue")
    async def phone_control_queue(request: Request) -> JSONResponse:
        local_error = require_local_dashboard(request)
        if local_error is not None:
            return local_error
        payload = await request.json()
        action = str(payload.get("action") or "").strip()
        if action == "clear":
            ctx.state.data["phone_control_queue"] = []
            ctx.state.save()
            ctx.logger.append({"event": "phone_control_queue_cleared"})
            return JSONResponse({"ok": True, "cleared": True})
        allowed = {"start_training", "start_local_test", "arm", "disarm", "cancel", "start_sensors", "stop_sensors", "start_sensor_preview", "stop_sensor_preview"}
        if action not in allowed:
            return json_error(400, "invalid_phone_control", "Unsupported phone control action.")
        queue = ctx.state.data.setdefault("phone_control_queue", [])
        item = {"id": generate_token(12), "action": action, "created_at_ms": now_ms(), "ttl_ms": 30000, "target_device_id": payload.get("target_device_id")}
        queue.append(item)
        ctx.state.save()
        ctx.logger.append({"event": "phone_control_queued", **item})
        return JSONResponse({"ok": True, "queued": item})

    @app.get("/phone-control/poll")
    async def phone_control_poll(device_id: str = "") -> JSONResponse:
        if not device_id or not ctx.state.get_device(device_id):
            return json_error(403, "unknown_device", "DexTilt phone control polling requires a paired device ID.")
        queue = ctx.state.data.setdefault("phone_control_queue", [])
        current_ms = now_ms()
        selected = None
        remaining = []
        expired_count = 0
        for item in queue:
            # Expire items that have outlived their TTL — never deliver them.
            age_ms = current_ms - item.get("created_at_ms", 0)
            if age_ms > item.get("ttl_ms", 30000):
                ctx.logger.append({"event": "phone_control_expired", "device_id": device_id, "action": item.get("action"), "age_ms": age_ms})
                expired_count += 1
                continue
            target = item.get("target_device_id")
            if selected is None and (not target or target == device_id):
                selected = item
            else:
                remaining.append(item)
        if selected is not None or expired_count > 0:
            ctx.state.data["phone_control_queue"] = remaining
            ctx.state.save()
        if selected is not None:
            ctx.logger.append({"event": "phone_control_delivered", "device_id": device_id, **selected})
        return JSONResponse({"ok": True, "control": selected})

    @app.get("/commands")
    async def commands() -> dict[str, Any]:
        return {"ok": True, "commands": ctx.actions.command_ids(), "details": ctx.actions.command_details()}

    @app.get("/logs")
    async def logs(limit: int = 50) -> dict[str, Any]:
        safe_limit = min(max(int(limit), 1), 200)
        return {"ok": True, "log_path": str(ctx.logger.path), "events": ctx.logger.read_recent(safe_limit)}

    @app.post("/phone-state")
    async def post_phone_state(request: Request) -> JSONResponse:
        source = client_ip(request)
        try:
            body = await request.json()
        except Exception:
            return json_error(400, "malformed_json", "DexTilt could not read the phone state payload.")
        if not isinstance(body, dict):
            return json_error(400, "malformed_json", "DexTilt expected a JSON object.")
        ok, code, message, _ = validate_signed_envelope(body, ctx, source, require_known_command=False)
        if not ok:
            return json_error(401, code, message)
        sanitized = clamp_phone_state(body)
        ctx.state.set_last_phone_state(sanitized)
        return JSONResponse({"ok": True, "accepted": True, "user_message": "Phone state received."})

    @app.get("/phone-state")
    async def get_phone_state() -> dict[str, Any]:
        return {"ok": True, "state": ctx.state.get_last_phone_state()}

    @app.post("/gesture-preview")
    async def post_gesture_preview(request: Request) -> JSONResponse:
        source = client_ip(request)
        try:
            body = await request.json()
        except Exception:
            return json_error(400, "malformed_json", "DexTilt could not read the gesture preview payload.")
        if not isinstance(body, dict):
            return json_error(400, "malformed_json", "DexTilt expected a JSON object.")
        ok, code, message, _ = validate_signed_envelope(body, ctx, source, require_known_command=False)
        if not ok:
            return json_error(401, code, message)
        preview = dict(body)
        preview["name"] = str(preview.get("name", ""))[:128]
        preview["gesture_id"] = str(preview.get("gesture_id", ""))[:64]
        raw_pts = preview.get("points", [])
        if not isinstance(raw_pts, list):
            raw_pts = []
        preview["points"] = [clamp_preview_point(dict(p)) for p in raw_pts[:200] if isinstance(p, dict)]
        ctx.state.set_last_gesture_preview(preview)
        ctx.logger.append({
            "event": "gesture_preview_received",
            "gesture_id": preview.get("gesture_id", ""),
            "point_count": len(preview["points"]),
        })
        return JSONResponse({"ok": True, "accepted": True, "user_message": "Gesture preview received."})

    @app.get("/gesture-preview")
    async def get_gesture_preview() -> dict[str, Any]:
        return {"ok": True, "preview": ctx.state.get_last_gesture_preview()}

    @app.get("/api/queue-status")
    async def get_queue_status() -> dict[str, Any]:
        with ctx.state.lock:
            queue = list(ctx.state.data.get("phone_control_queue", []))
        return {"ok": True, "queue": queue}

    @app.post("/api/reset-pairing")
    async def api_reset_pairing(request: Request) -> JSONResponse:
        local_error = require_local_dashboard(request)
        if local_error is not None:
            return local_error
        ctx.state.reset_pairings()
        ctx.logger.append({"event": "pairing_reset_via_dashboard"})
        return JSONResponse({"ok": True, "user_message": "All pairings cleared. Re-pair the Android app."})

    return app
