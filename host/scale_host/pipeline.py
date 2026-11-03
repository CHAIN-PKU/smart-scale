"""Save one stable weighing after recognition, price lookup, and fusion."""

from __future__ import annotations

import asyncio
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from dotenv import load_dotenv

from scale_host.catalog.lookup import build_product_info
from scale_host.device.interface import DisplayRequest
from scale_host.device.serial_device import LinePort, SerialScaleDevice
from scale_host.domain import ScaleStatus, WeightReading
from scale_host.fusion import PlacementPricer, Sale, fuse
from scale_host.frames import current_frame
from scale_host.protocol.messages import AckMessage, CommandMessage, QueryMessage
from scale_host.remote_query import wifi_page
from scale_host.providers import MissingApiKey, RemoteCallNotReady
from scale_host.quote import DEMO_IMAGE, identify_and_price
from scale_host.receipt import ReceiptBook
from scale_host.sale import price_stable_scenario
from scale_host.storage import SqliteRepository, WeighingSession
from scale_host.vision.interface import build_vision

DEMO_SESSION_ID = "banana-demo"
DEMO_TIMESTAMP = "2026-09-27T12:00:00"
_BOARD_COMMANDS = {"save", "receipt", "clear"}


def display_request_for(sale: Sale) -> DisplayRequest:
    return DisplayRequest(
        product=sale.label,
        weight_g=sale.weight_g,
        price=sale.amount_yuan,
        price_per_kg=sale.price_per_kg,
        portion_kcal=sale.portion_kcal,
        portion_carb_g=sale.portion_carb_g,
        portion_fiber_g=sale.portion_fiber_g,
    )


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
        portion_kcal=sale.portion_kcal,
        portion_carb_g=sale.portion_carb_g,
        portion_fiber_g=sale.portion_fiber_g,
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
        await device.display(display_request_for(sale))
        session = session_from_sale(sale, session_id=session_id, timestamp=timestamp)
        repository.save_session(session)
        return session, skipped
    finally:
        await device.disconnect()


async def serve_open_port(
    port: LinePort,
    repository: SqliteRepository,
    *,
    session_id: str,
    timestamp: str,
    on_sale: Callable[[WeighingSession], None] | None = None,
) -> None:
    """Stay open after the first price so save, receipt, and clear can arrive."""
    device = SerialScaleDevice(port)
    book = ReceiptBook.from_rows(repository.list_receipt_lines())
    pricer = PlacementPricer()
    priced = 0
    answered = 0
    missed_frame: tuple[str, int] | None = None
    await device.connect()
    try:
        async for event in device.events():
            if isinstance(event, QueryMessage):
                device.write_json(wifi_page(repository, event.query))
                answered += 1
                continue
            if isinstance(event, CommandMessage):
                if event.command not in _BOARD_COMMANDS:
                    continue
                reply = book.apply(event.command)
                if event.command == "save" and isinstance(reply, AckMessage) and reply.status == "ok":
                    repository.replace_receipt_lines(book.rows())
                if event.command == "clear":
                    repository.replace_receipt_lines(book.rows())
                device.write_message(reply)
                continue
            if not isinstance(event, WeightReading):
                continue
            pricer.release_if_removed(event)
            if event.state in (ScaleStatus.WEIGHT_REMOVED, ScaleStatus.ZERO):
                missed_frame = None
            if not pricer.waiting_for_new_sale(event):
                continue
            frame = current_frame()
            if frame is None:
                book.forget()
                continue
            try:
                frame_stamp = (frame, Path(frame).stat().st_mtime_ns)
            except OSError:
                frame_stamp = (frame, None)
            if frame_stamp == missed_frame:
                continue
            try:
                quote = identify_and_price(frame, build_vision(), build_product_info())
            except RuntimeError:
                missed_frame = frame_stamp
                book.forget()
                continue
            except OSError:
                book.forget()
                continue
            sale = pricer.consider(event, quote)
            if sale is None:
                continue
            book.remember(sale)
            await device.display(display_request_for(sale))
            priced += 1
            this_id = session_id if priced == 1 else f"{session_id}-{priced}"
            session = session_from_sale(sale, session_id=this_id, timestamp=timestamp)
            repository.save_session(session)
            if on_sale is not None:
                on_sale(session)
        if priced == 0 and answered == 0:
            raise RuntimeError("no stable weight")
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
