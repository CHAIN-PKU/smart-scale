"""Records stored by the scale. These objects do not open a database."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

_MODEL_CONFIG = ConfigDict(extra="forbid")


class WeighingSession(BaseModel):
    model_config = _MODEL_CONFIG
    id: str = Field(min_length=1)
    timestamp: str = Field(min_length=1)
    weight_g: float
    image_path: str | None = None
    product_id: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    model_name: str | None = None
    label: str | None = None
    price_per_kg: float | None = Field(default=None, ge=0)
    amount_yuan: float | None = Field(default=None, ge=0)


class CorrectionRecord(BaseModel):
    model_config = _MODEL_CONFIG
    session_id: str
    predicted_product: str
    correct_product: str
    weight_g: float
    image_path: str | None = None


class DeviceEvent(BaseModel):
    model_config = _MODEL_CONFIG
    timestamp: str
    device_id: str
    event_type: str
    payload: str
