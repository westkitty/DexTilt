from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PairRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol: str
    receiver_id: str
    pairing_token: str
    device_id: str = Field(min_length=8, max_length=128)
    device_name: str = Field(default="Android DexTilt", max_length=128)


class CommandMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol: str
    device_id: str = Field(min_length=8, max_length=128)
    receiver_id: str = Field(min_length=8, max_length=128)
    command_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-z0-9_]+$")
    gesture_id: str = Field(default="manual", max_length=128, pattern=r"^[a-z0-9_]+$")
    timestamp_ms: int
    nonce: str = Field(min_length=8, max_length=128)
    confidence: int = Field(ge=0, le=100)
    signature: str = Field(min_length=16, max_length=256)


class SignedEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore")

    protocol: str
    device_id: str = Field(min_length=8, max_length=128)
    receiver_id: str = Field(min_length=8, max_length=128)
    command_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-z0-9_]+$")
    gesture_id: str = Field(default="manual", max_length=128, pattern=r"^[a-z0-9_]+$")
    timestamp_ms: int
    nonce: str = Field(min_length=8, max_length=128)
    confidence: int = Field(ge=0, le=100)
    signature: str = Field(min_length=16, max_length=256)


def _clamp(v: object, lo: float, hi: float) -> float:
    try:
        return max(lo, min(hi, float(v)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return lo


def clamp_phone_state(d: dict) -> dict:
    out = dict(d)
    for k in ("ax", "ay", "az", "gx", "gy", "gz"):
        out[k] = _clamp(out.get(k, 0), -50, 50)
    for k in ("roll", "pitch", "yaw"):
        out[k] = _clamp(out.get(k, 0), -12.57, 12.57)
    out["qw"] = _clamp(out.get("qw", 1), -1.0, 1.0)
    for k in ("qx", "qy", "qz"):
        out[k] = _clamp(out.get(k, 0), -1.0, 1.0)
    out["phase"] = str(out.get("phase", ""))[:32]
    out["orientation_source"] = str(out.get("orientation_source", ""))[:32]
    out["device_id"] = str(out.get("device_id", ""))[:128]
    out["face_down_stable"] = bool(out.get("face_down_stable", False))
    return out


def clamp_preview_point(p: dict) -> dict:
    out = dict(p)
    out["t_ms"] = int(_clamp(out.get("t_ms", 0), 0, 60000))
    for k in ("x", "y", "z"):
        out[k] = _clamp(out.get(k, 0), -10, 10)
    for k in ("rx", "ry", "rz"):
        out[k] = _clamp(out.get(k, 0), -12.57, 12.57)
    out["qw"] = _clamp(out.get("qw", 1), -1.0, 1.0)
    for k in ("qx", "qy", "qz"):
        out[k] = _clamp(out.get(k, 0), -1.0, 1.0)
    return out


class LivePhoneStateEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore")

    protocol: str
    device_id: str
    receiver_id: str
    command_id: str
    gesture_id: str
    timestamp_ms: int
    nonce: str
    confidence: int
    signature: str
    face_down_stable: bool = False
    phase: str = Field(default="", max_length=32)
    ax: float = 0.0
    ay: float = 0.0
    az: float = 0.0
    gx: float = 0.0
    gy: float = 0.0
    gz: float = 0.0
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0
    qw: float = 1.0
    qx: float = 0.0
    qy: float = 0.0
    qz: float = 0.0
    orientation_source: str = Field(default="accelerometer", max_length=32)


class GesturePreviewPoint(BaseModel):
    model_config = ConfigDict(extra="ignore")

    t_ms: int = 0
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    rx: float = 0.0
    ry: float = 0.0
    rz: float = 0.0
    qw: float = 1.0
    qx: float = 0.0
    qy: float = 0.0
    qz: float = 0.0


class GesturePreviewEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore")

    protocol: str
    device_id: str
    receiver_id: str
    command_id: str
    gesture_id: str
    timestamp_ms: int
    nonce: str
    confidence: int
    signature: str
    name: str = Field(default="", max_length=128)
    duration_ms: int = 0
    created_at_ms: int = 0
    points: list[GesturePreviewPoint] = []


class CalibrationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol: str
    device_id: str = Field(min_length=8, max_length=128)
    receiver_id: str = Field(min_length=8, max_length=128)
    command_id: str = Field(default="calibration_update", pattern=r"^[a-z0-9_]+$")
    gesture_id: str = Field(default="calibration", pattern=r"^[a-z0-9_]+$")
    timestamp_ms: int
    nonce: str = Field(min_length=8, max_length=128)
    confidence: int = Field(default=100, ge=0, le=100)
    signature: str = Field(min_length=16, max_length=256)
    step_id: str = Field(max_length=64)
    step_label: str = Field(max_length=128)
    status: str = Field(pattern=r"^(pending|detected|failed|complete)$")
    detail: str = Field(default="", max_length=512)
