"""Save one stable weighing after recognition, price lookup, and fusion."""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv

from scale_host.catalog.lookup import build_product_info
from scale_host.device.interface import DisplayRequest
from scale_host.device.serial_device import LinePort, SerialScaleDevice
from scale_host.domain import ScaleStatus, WeightReading
from scale_host.fusion import Sale, fuse
from scale_host.providers import MissingApiKey, RemoteCallNotReady
from scale_host.quote import DEMO_IMAGE, identify_and_price
from scale_host.sale import price_stable_scenario
from scale_host.storage import SqliteRepository, WeighingSession
from scale_host.vision.interface import build_vision

DEMO_SESSION_ID = "banana-demo"
DEMO_TIMESTAMP = "2026-09-27T12:00:00"


def session_from_sale(sale: Sale, *, session_id: str, timestamp: str) -> WeighingSession:
    return WeighingSession(
        id=session_id,
        timestamp=timestamp,
        weight_g=sale.weight_g,
        image_path=sale.image_path,
        confidence=sale.confidence,
        model_name=sale.vision_source,
        label=sale.label,
        price_per_kg=sale.price_per_kg,
        amount_yuan=sale.amount_yuan,
    )


async def record_stable_sale(
    repository: SqliteRepository,
    *,
    session_id: str,
    timestamp: str,
) -> WeighingSession:
    sale = await price_stable_scenario()
    session = session_from_sale(sale, session_id=session_id, timestamp=timestamp)
    repository.save_session(session)
    return session


async def price_open_port(
    port: LinePort,
    repository: SqliteRepository,
    *,
    session_id: str,
    timestamp: str,
) -> tuple[WeighingSession, int]:
    device = SerialScaleDevice(port)
    await device.connect()
    reading: WeightReading | None = None
    skipped = 0
    try:
        async for event in device.events():
            if not isinstance(event, WeightReading):
                continue
            ready = (
                event.state is ScaleStatus.WEIGHT_STABLE
                and event.stable
                and event.status == "ok"
                and event.weight_g > 0
            )
            if not ready:
                skipped += 1
                continue
            reading = event
            break
        if reading is None:
            raise RuntimeError("no stable weight")
        quote = identify_and_price(DEMO_IMAGE, build_vision(), build_product_info())
        sale = fuse(reading, quote)
        await device.display(
            DisplayRequest(product=sale.label, weight_g=sale.weight_g, price=sale.amount_yuan)
        )
        session = session_from_sale(sale, session_id=session_id, timestamp=timestamp)
        repository.save_session(session)
        return session, skipped
    finally:
        await device.disconnect()


def main() -> None:
    load_dotenv(override=False)
    with tempfile.TemporaryDirectory() as folder:
        repository = SqliteRepository(Path(folder) / "scale.db")
        try:
            asyncio.run(
                record_stable_sale(
                    repository,
                    session_id=DEMO_SESSION_ID,
                    timestamp=DEMO_TIMESTAMP,
                )
            )
            stored = repository.get_session(DEMO_SESSION_ID)
        except (RuntimeError, MissingApiKey, RemoteCallNotReady) as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(2) from exc
    if stored is None or stored.amount_yuan is None:
        print("sale was not stored", file=sys.stderr)
        raise SystemExit(2)
    print(f"label: {stored.label}")
    print(f"weight_g: {stored.weight_g}")
    print(f"price_per_kg: {stored.price_per_kg}")
    print(f"amount_yuan: {stored.amount_yuan:.2f}")
    print(f"stored: {stored.id}")


if __name__ == "__main__":
    main()
