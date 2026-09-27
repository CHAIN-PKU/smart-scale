"""Persistence boundary. The host depends on this, not on a database brand."""

from __future__ import annotations

from typing import Protocol

from scale_host.storage.records import CorrectionRecord, DeviceEvent, WeighingSession


class SessionRepository(Protocol):
    def save_session(self, session: WeighingSession) -> None:
        """Insert one weighing."""

    def get_session(self, session_id: str) -> WeighingSession | None:
        """Return the weighing, or None when it was never stored."""

    def add_correction(
        self,
        session_id: str,
        predicted_product: str,
        correct_product: str,
    ) -> None:
        """Store a human correction for an existing session."""

    def get_correction(self, session_id: str) -> CorrectionRecord | None:
        """Return the correction together with that session's weight and image."""

    def add_device_event(self, event: DeviceEvent) -> None:
        """Append one device event."""

    def list_device_events(self) -> list[DeviceEvent]:
        """Return device events in insert order."""
