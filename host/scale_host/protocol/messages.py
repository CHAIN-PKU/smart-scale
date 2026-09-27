"""V1 newline JSON messages. Unknown extra fields are ignored."""

from __future__ import annotations

import json
import math
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic.functional_validators import BeforeValidator

_MODEL_CONFIG = ConfigDict(extra="ignore")


class ProtocolError(Exception):
    """One line could not be turned into a V1 message."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def _as_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("integer required")
    return value


def _as_number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("number required")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("finite number required")
    return float(value)


def _as_bool(value: object) -> bool:
    if not isinstance(value, bool):
        raise ValueError("boolean required")
    return value


IntField = Annotated[int, BeforeValidator(_as_int)]
NumberField = Annotated[float, BeforeValidator(_as_number)]
BoolField = Annotated[bool, BeforeValidator(_as_bool)]
StateName = Literal[
    "BOOT",
    "READY",
    "ZERO",
    "WEIGHT_CHANGED",
    "WEIGHT_STABLE",
    "WEIGHT_REMOVED",
    "OVERLOAD",
    "ERROR",
]


class WeightMessage(BaseModel):
    model_config = _MODEL_CONFIG
    v: Literal[1]
    type: Literal["weight"]
    seq: IntField = Field(ge=0)
    timestamp_ms: IntField = Field(ge=0)
    weight_g: NumberField
    stable: BoolField
    tare_g: NumberField
    status: Literal["ok", "overload", "error"]


class StatusMessage(BaseModel):
    model_config = _MODEL_CONFIG
    v: Literal[1]
    type: Literal["status"]
    seq: IntField = Field(ge=0)
    timestamp_ms: IntField = Field(ge=0)
    state: StateName
    detail: str | None = Field(default=None, max_length=64)


class AckMessage(BaseModel):
    model_config = _MODEL_CONFIG
    v: Literal[1]
    type: Literal["ack"]
    seq: IntField = Field(ge=0)
    timestamp_ms: IntField = Field(ge=0)
    command: Literal["tare"]
    status: Literal["ok", "error"]


class CommandMessage(BaseModel):
    model_config = _MODEL_CONFIG
    v: Literal[1]
    type: Literal["command"]
    command: Literal["tare"]


class DisplayResultMessage(BaseModel):
    model_config = _MODEL_CONFIG
    v: Literal[1]
    type: Literal["display_result"]
    request_id: str = Field(min_length=1, max_length=32)
    product: str = Field(min_length=1, max_length=64)
    weight_g: NumberField
    price: NumberField = Field(ge=0)


Message = Union[
    WeightMessage,
    StatusMessage,
    AckMessage,
    CommandMessage,
    DisplayResultMessage,
]

_MODELS: dict[str, type[BaseModel]] = {
    "weight": WeightMessage,
    "status": StatusMessage,
    "ack": AckMessage,
    "command": CommandMessage,
    "display_result": DisplayResultMessage,
}


def parse_line(line: str) -> Message | None:
    """Parse one protocol line. Blank lines return None."""
    text = line.strip()
    if text == "":
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProtocolError("malformed") from exc
    if not isinstance(payload, dict):
        raise ProtocolError("not_object")
    if "v" not in payload or "type" not in payload:
        raise ProtocolError("missing_field")
    version = payload["v"]
    if isinstance(version, bool) or not isinstance(version, (int, float)) or version != 1:
        raise ProtocolError("bad_version")
    payload["v"] = 1
    message_type = payload["type"]
    model = _MODELS.get(message_type) if isinstance(message_type, str) else None
    if model is None:
        raise ProtocolError("unknown_type")
    try:
        return model.model_validate(payload)  # type: ignore[return-value]
    except ValidationError as exc:
        raise ProtocolError(_reason_from_validation(exc)) from exc


def _reason_from_validation(exc: ValidationError) -> str:
    for error in exc.errors():
        if error.get("type") == "missing":
            return "missing_field"
    return "bad_field"
