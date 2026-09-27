"""Turn gross samples into the V1 weight states. No automatic tare."""

from __future__ import annotations

from scale_host.domain import ScaleStatus, WeightReading


class ScaleDynamics:
    def __init__(
        self,
        *,
        zero_band_g: float = 2.0,
        stable_delta_g: float = 0.5,
        stable_window_ms: int = 500,
        overload_g: float | None = None,
    ) -> None:
        self.zero_band_g = zero_band_g
        self.stable_delta_g = stable_delta_g
        self.stable_window_ms = stable_window_ms
        self.overload_g = overload_g
        self.tare_g = 0.0
        self.state = ScaleStatus.BOOT
        self._window: list[tuple[int, float]] = []
        self._had_object = False
        self._seq = 0

    def boot(self) -> None:
        self.state = ScaleStatus.BOOT

    def ready(self) -> None:
        self.state = ScaleStatus.READY

    def observe(self, timestamp_ms: int, gross_g: float) -> WeightReading:
        net_g = gross_g - self.tare_g
        self._window.append((timestamp_ms, net_g))
        start = timestamp_ms - self.stable_window_ms
        self._window = [(t, w) for t, w in self._window if t >= start]
        stable = self._is_stable(timestamp_ms)
        self.state = self._next_state(net_g, stable)
        if self.state in (ScaleStatus.WEIGHT_CHANGED, ScaleStatus.WEIGHT_STABLE):
            self._had_object = True
        if self.state in (ScaleStatus.ZERO, ScaleStatus.WEIGHT_REMOVED):
            self._had_object = False
        reading_stable = self.state in (
            ScaleStatus.ZERO,
            ScaleStatus.WEIGHT_STABLE,
            ScaleStatus.WEIGHT_REMOVED,
        )
        if self.state is ScaleStatus.OVERLOAD:
            status = "overload"
        elif self.state is ScaleStatus.ERROR:
            status = "error"
        else:
            status = "ok"
        self._seq += 1
        return WeightReading(
            seq=self._seq,
            timestamp_ms=timestamp_ms,
            weight_g=net_g,
            stable=reading_stable,
            tare_g=self.tare_g,
            status=status,
            state=self.state,
        )

    def fail(self, timestamp_ms: int) -> WeightReading:
        self.state = ScaleStatus.ERROR
        self._seq += 1
        return WeightReading(
            seq=self._seq,
            timestamp_ms=timestamp_ms,
            weight_g=0.0,
            stable=False,
            tare_g=self.tare_g,
            status="error",
            state=self.state,
        )

    def can_tare(self) -> bool:
        return self.state in (
            ScaleStatus.READY,
            ScaleStatus.ZERO,
            ScaleStatus.WEIGHT_CHANGED,
            ScaleStatus.WEIGHT_STABLE,
            ScaleStatus.WEIGHT_REMOVED,
        )

    def apply_tare(self, gross_g: float) -> None:
        self.tare_g = gross_g
        self._window.clear()
        self._had_object = False
        self.state = ScaleStatus.ZERO

    def _is_stable(self, timestamp_ms: int) -> bool:
        if not self._window:
            return False
        if timestamp_ms - self._window[0][0] < self.stable_window_ms:
            return False
        weights = [weight for _, weight in self._window]
        return max(weights) - min(weights) <= self.stable_delta_g

    def _next_state(self, net_g: float, stable: bool) -> ScaleStatus:
        if self.overload_g is not None and net_g > self.overload_g:
            return ScaleStatus.OVERLOAD
        empty = abs(net_g) <= self.zero_band_g
        if empty and stable and self._had_object:
            return ScaleStatus.WEIGHT_REMOVED
        if empty and stable:
            return ScaleStatus.ZERO
        if not stable and (self._had_object or not empty):
            return ScaleStatus.WEIGHT_CHANGED
        if empty:
            return ScaleStatus.READY
        if stable:
            return ScaleStatus.WEIGHT_STABLE
        return ScaleStatus.WEIGHT_CHANGED
