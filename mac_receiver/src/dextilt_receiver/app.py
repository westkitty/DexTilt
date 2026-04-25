from __future__ import annotations

import json
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
from .models import CalibrationUpdate, CommandMessage, PairRequest, SignedEnvelope
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
    if state_path is not None:
        config["state_path"] = str(Path(state_path).expanduser())
    if log_path is not None:
        config["log_path"] = str(Path(log_path).expanduser())
    if dry_run_actions is not None:
        config["dry_run_actions"] = bool(dry_run_actions)
    state = StateStore(config["state_path"])
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
        html = render_dashboard(status, ctx.actions.command_ids(), ctx.logger.read_recent(20))
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

    @app.get("/commands")
    async def commands() -> dict[str, Any]:
        return {"ok": True, "commands": ctx.actions.command_ids()}

    @app.get("/logs")
    async def logs(limit: int = 50) -> dict[str, Any]:
        safe_limit = min(max(int(limit), 1), 200)
        return {"ok": True, "log_path": str(ctx.logger.path), "events": ctx.logger.read_recent(safe_limit)}

    return app
