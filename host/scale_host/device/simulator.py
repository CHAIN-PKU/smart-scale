"""Scale that replays scripted samples. It never opens a serial port."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence

from scale_host.device.dynamics import ScaleDynamics
from scale_host.device.interface import CommandResult, DeviceLink, DisplayRequest, ScaleEvent

_BANANA_GROSS_G = (0.0, 12.0, 145.0, 310.0, 326.0, 326.4)


class SimulatedScaleDevice:
    def __init__(
        self,
        scenario: str = "banana",
        *,
        sample_interval_ms: int = 100,
        overload_g: float | None = None,
    ) -> None:
        self.scenario = scenario
        self.sample_interval_ms = sample_interval_ms
        self._overload_g = overload_g
        self._connected = False
        self._dynamics = ScaleDynamics()
        self._gross_g = 0.0
        self.displayed: list[DisplayRequest] = []

    async def connect(self) -> None:
        self._connected = True
        self._dynamics = ScaleDynamics(overload_g=self._overload_limit())
        self._dynamics.boot()
        self._gross_g = 0.0

    async def disconnect(self) -> None:
        self._connected = False

    async def events(self) -> AsyncIterator[ScaleEvent]:
        if not self._connected:
            yield DeviceLink(connected=False, detail="serial disconnected")
            return
        self._dynamics.ready()
        if self.scenario == "sensor_error":
            yield self._dynamics.fail(0)
            return
        if self.scenario == "serial_disconnected":
            yield DeviceLink(connected=False, detail="serial disconnected")
            return
        for timestamp_ms, gross_g in self._script():
            if not self._connected:
                yield DeviceLink(connected=False, detail="serial disconnected")
                return
            self._gross_g = gross_g
            yield self._dynamics.observe(timestamp_ms, gross_g)

    async def tare(self) -> CommandResult:
        if not self._dynamics.can_tare():
            return CommandResult(command="tare", status="error")
        self._dynamics.apply_tare(self._gross_g)
        return CommandResult(command="tare", status="ok")

    async def display(self, request: DisplayRequest) -> None:
        self.displayed.append(request)

    def _overload_limit(self) -> float | None:
        if self.scenario == "overload":
            return 1000.0 if self._overload_g is None else self._overload_g
        return self._overload_g

    def _script(self) -> Sequence[tuple[int, float]]:
        if self.scenario == "banana":
            return _hold_last(_BANANA_GROSS_G, self.sample_interval_ms, hold_ms=600)
        if self.scenario == "noise":
            noisy = (20.0, 23.0, 19.0, 24.0, 18.0, 22.0, 19.5, 23.5)
            return _repeat(noisy, self.sample_interval_ms)
        if self.scenario == "removed":
            rising = _hold_last(_BANANA_GROSS_G, self.sample_interval_ms, hold_ms=600)
            start = rising[-1][0] + self.sample_interval_ms
            falling = _repeat((0.0,) * 9, self.sample_interval_ms)
            return [*rising, *[(start + t, w) for t, w in falling]]
        if self.scenario == "overload":
            return _repeat((0.0, 1200.0), self.sample_interval_ms)
        raise ValueError(f"unknown scenario: {self.scenario}")


def _repeat(weights: Sequence[float], interval_ms: int) -> list[tuple[int, float]]:
    return [(index * interval_ms, weight) for index, weight in enumerate(weights)]


def _hold_last(
    weights: Sequence[float],
    interval_ms: int,
    *,
    hold_ms: int,
) -> list[tuple[int, float]]:
    points = _repeat(weights, interval_ms)
    if not points:
        return []
    last_t, last_w = points[-1]
    extra = range(interval_ms, hold_ms + interval_ms, interval_ms)
    points.extend((last_t + offset, last_w) for offset in extra)
    return points
