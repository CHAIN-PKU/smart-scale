"""Identify the item on the scale when this placement first becomes stable.

A saved photo is not a sale. Recognition runs on the current view at the
stable moment, then the short table prices that same weight. No network
and no COM port.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass

from scale_host.ask import answer
from scale_host.catalog import TableProductInfo
from scale_host.device.simulator import SimulatedScaleDevice
from scale_host.display_line import display_line
from scale_host.domain import ScaleStatus, WeightReading
from scale_host.fusion import PlacementPricer, Sale
from scale_host.pipeline import session_from_sale
from scale_host.quote import ItemQuote, identify_and_price
from scale_host.speech import announcement
from scale_host.storage import SqliteRepository, WeighingSession
from scale_host.vision.interface import MockVision, VisionProvider

LIVE_FRAME = "live-frame"


@dataclass(frozen=True)
class LiveResult:
    sale: Sale | None
    recognized_at: WeightReading | None


def _ready(reading: WeightReading) -> bool:
    return (
        reading.state is ScaleStatus.WEIGHT_STABLE
        and reading.stable
        and reading.status == "ok"
        and reading.weight_g > 0
    )


class _Watcher:
    """One look per placement. Removal clears it so the next item is seen again."""

    def __init__(self, vision: VisionProvider, frame_path) -> None:
        self.vision = vision
        self.frame_path = frame_path
        self.pricer = PlacementPricer()
        self.quote: ItemQuote | None = None
        self.looked = False
        self.recognized_at: WeightReading | None = None

    def observe(self, reading: WeightReading) -> Sale | None:
        if reading.state in (ScaleStatus.WEIGHT_REMOVED, ScaleStatus.ZERO):
            self.looked = False
            self.quote = None
            self.pricer.consider(reading, _reset_quote())
            return None
        if not self.looked and _ready(reading):
            self.looked = True
            self.recognized_at = reading
            try:
                self.quote = identify_and_price(
                    self.frame_path(), self.vision, TableProductInfo()
                )
            except RuntimeError:
                self.quote = None
                return None
        if self.quote is None:
            return None
        return self.pricer.consider(reading, self.quote)


def _reset_quote() -> ItemQuote:
    return ItemQuote(
        label="banana",
        confidence=1.0,
        price_per_kg=12.0,
        vision_source="mock",
        info_source="table",
        image_path=LIVE_FRAME,
    )


def placement_notices(sales: list[Sale]) -> list[tuple[str, str]]:
    """One display line and one spoken line per sale. Nutrition stays off both."""

    notices: list[tuple[str, str]] = []
    for index, sale in enumerate(sales, start=1):
        notices.append((display_line(sale, f"r_{index:03d}"), announcement(sale)))
    return notices


def remember_placements(
    readings: list[WeightReading],
    vision: VisionProvider,
    frames: list[str],
    repository: SqliteRepository,
) -> list[WeighingSession]:
    """Store one weighing per live sale. Nutrition stays in the record."""

    saved: list[WeighingSession] = []
    for index, sale in enumerate(watch_readings(readings, vision, frames), start=1):
        session = session_from_sale(
            sale,
            session_id=f"live-{index:03d}",
            timestamp=f"2026-10-20T20:32:{index:02d}",
        )
        repository.save_session(session)
        saved.append(session)
    return saved


def latest_answer(repository: SqliteRepository) -> str:
    """Read the newest stored weighing. This does not open the scale."""

    return answer("上次称了多少", repository.list_sessions(limit=1))


def watch_readings(
    readings: list[WeightReading],
    vision: VisionProvider,
    frames: list[str],
) -> list[Sale]:
    pending = iter(frames)
    watcher = _Watcher(vision, lambda: next(pending))
    sales: list[Sale] = []
    for reading in readings:
        sale = watcher.observe(reading)
        if sale is not None:
            sales.append(sale)
    return sales


async def price_current_view(
    device: SimulatedScaleDevice,
    vision: VisionProvider,
    frame_path: str = LIVE_FRAME,
) -> LiveResult:
    watcher = _Watcher(vision, lambda: frame_path)
    await device.connect()
    try:
        async for event in device.events():
            if not isinstance(event, WeightReading):
                continue
            sale = watcher.observe(event)
            if sale is not None:
                return LiveResult(sale, watcher.recognized_at)
    finally:
        await device.disconnect()
    return LiveResult(None, watcher.recognized_at)


def main() -> None:
    result = asyncio.run(
        price_current_view(SimulatedScaleDevice("banana"), MockVision())
    )
    sale = result.sale
    if sale is None or result.recognized_at is None:
        print("weight is not ready to price", file=sys.stderr)
        raise SystemExit(2)
    print("live: stable")
    print(f"label: {sale.label}")
    print(f"frame: {sale.image_path}")
    print(f"weight_g: {sale.weight_g}")
    print(f"price: {sale.amount_yuan:.2f}")
    print(f"recognized_state: {result.recognized_at.state}")
    print("sent_to_internet: no")
    print("com_open: no")


if __name__ == "__main__":
    main()
    sys.exit(0)
