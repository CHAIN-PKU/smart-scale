"""Device boundary. Implementations may be a simulator or a serial port."""

from __future__ import annotations

from typing import AsyncIterator, Protocol, Union

from pydantic import BaseModel, ConfigDict, Field

from scale_host.domain import WeightReading


class DeviceLink(BaseModel):
    model_config = ConfigDict(extra="forbid")
    connected: bool
    detail: str = Field(default="", max_length=64)


class DisplayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product: str = Field(min_length=1, max_length=64)
    weight_g: float
    price: float = Field(ge=0)


class CommandResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    command: str
    status: str = Field(pattern="^(ok|error)$")


ScaleEvent = Union[WeightReading, DeviceLink]


class ScaleDevice(Protocol):
    async def connect(self) -> None:
        """Open the device. Does not tare."""

    async def disconnect(self) -> None:
        """Close the device."""

    def events(self) -> AsyncIterator[ScaleEvent]:
        """Yield readings and link changes until the stream ends."""

    async def tare(self) -> CommandResult:
        """Zero the scale, or refuse while booting, overloaded, or in error."""

    async def display(self, request: DisplayRequest) -> None:
        """Accept a result for the scale display."""
