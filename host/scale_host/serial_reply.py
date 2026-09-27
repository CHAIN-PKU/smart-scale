"""Price a scripted serial weight from the text reply. No COM port is opened."""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

from scale_host.device.interface import DisplayRequest
from scale_host.device.serial_device import SerialScaleDevice
from scale_host.domain import ScaleStatus, WeightReading
from scale_host.pipeline import DEMO_TIMESTAMP, session_from_sale
from scale_host.reply_sale import sale_from_replies
from scale_host.serial_replay import BANANA_LINES, ScriptedPort
from scale_host.storage import SqliteRepository, WeighingSession

SERIAL_REPLY_SESSION_ID = "banana-serial-reply"
_IDENTIFY_REPLY = {"label": "banana", "confidence": 0.91, "price_per_kg": 999}
_PRICE_REPLY = {
    "label": "banana",
    "price_per_kg": 12.0,
    "summary": "loopback fixture",
}


async def price_scripted_replies(
    port: ScriptedPort,
    repository: SqliteRepository,
    *,
    session_id: str = SERIAL_REPLY_SESSION_ID,
) -> tuple[WeighingSession, float, int]:
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
        sale = sale_from_replies(_IDENTIFY_REPLY, _PRICE_REPLY, "banana.jpg", reading)
        await device.display(
            DisplayRequest(product=sale.label, weight_g=sale.weight_g, price=sale.amount_yuan)
        )
        session = session_from_sale(
            sale,
            session_id=session_id,
            timestamp=DEMO_TIMESTAMP,
        )
        repository.save_session(session)
        stored = repository.get_session(session_id)
        if stored is None or stored.amount_yuan is None:
            raise RuntimeError("sale was not stored")
        shown = json.loads(port.outgoing[-1].decode("utf-8"))["price"]
        return stored, float(shown), skipped
    finally:
        await device.disconnect()


def main() -> None:
    port = ScriptedPort(BANANA_LINES)
    with tempfile.TemporaryDirectory() as folder:
        repository = SqliteRepository(Path(folder) / "scale.db")
        stored, display_price, _skipped = asyncio.run(price_scripted_replies(port, repository))
    same = stored.amount_yuan == display_price
    print(f"weight_g: {stored.weight_g}")
    print(f"display_price: {display_price:.2f}")
    print(f"stored: {stored.id}")
    print(f"same_amount: {'yes' if same else 'no'}")
    print("sent_to_internet: no")
    if not same:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
    sys.exit(0)
