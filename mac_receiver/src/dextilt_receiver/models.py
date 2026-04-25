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
