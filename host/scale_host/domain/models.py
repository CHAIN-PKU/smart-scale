"""Internal objects passed between host modules.

Wire JSON stays in ``scale_host.protocol``. This module does not open ports, storage, cameras, or recognition libraries.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

_MODEL_CONFIG = ConfigDict(extra="forbid")


class ScaleStatus(str, Enum):
    BOOT = "BOOT"
    READY = "READY"
    ZERO = "ZERO"
    WEIGHT_CHANGED = "WEIGHT_CHANGED"
    WEIGHT_STABLE = "WEIGHT_STABLE"
    WEIGHT_REMOVED = "WEIGHT_REMOVED"
    OVERLOAD = "OVERLOAD"
    ERROR = "ERROR"


class WeightReading(BaseModel):
    model_config = _MODEL_CONFIG
    seq: int = Field(ge=0)
    timestamp_ms: int = Field(ge=0)
    weight_g: float
    stable: bool
    tare_g: float
    status: str = Field(pattern="^(ok|overload|error)$")
    state: ScaleStatus | None = None


class DeviceCommand(BaseModel):
    model_config = _MODEL_CONFIG
    command: str = Field(pattern="^tare$")


class ProductCandidate(BaseModel):
    model_config = _MODEL_CONFIG
    label: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class ProductRecognition(BaseModel):
    """Slot for a future vision provider. No model is called here."""

    model_config = _MODEL_CONFIG
    product_id: str | None = None
    label: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    candidates: list[ProductCandidate] = Field(default_factory=list)
    source: str = Field(min_length=1)
    image_id: str | None = None


class ProductObservation(BaseModel):
    """Slot for a future fusion result. No scoring is done here."""

    model_config = _MODEL_CONFIG
    label: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    weight_g: float
