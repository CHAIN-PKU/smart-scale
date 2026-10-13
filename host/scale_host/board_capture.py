"""Replay Zeng Yan's 2026-10-13 placement lines. No COM port and no network."""

from __future__ import annotations

import asyncio
import json
import sys

from scale_host.catalog import TableProductInfo
from scale_host.device.interface import DisplayRequest
from scale_host.device.serial_device import SerialScaleDevice
from scale_host.domain import WeightReading
from scale_host.fusion import PlacementPricer, Sale
from scale_host.quote import identify_and_price
from scale_host.serial_replay import ScriptedPort
from scale_host.vision import MockVision

# Copied from her evening note. The scale reported 221.1 g once it settled.
CAPTURED_PLACE_LINES = (
    b'{"v":1,"type":"status","seq":3305,"timestamp_ms":317761,"state":"WEIGHT_CHANGED"}\n',
    b'{"v":1,"type":"weight","seq":3306,"timestamp_ms":317769,"weight_g":3.9,"stable":false,"tare_g":0.0,"status":"ok"}\n',
    b'{"v":1,"type":"status","seq":3326,"timestamp_ms":319718,"state":"WEIGHT_STABLE"}\n',
    b'{"v":1,"type":"weight","seq":3327,"timestamp_ms":319725,"weight_g":221.1,"stable":true,"tare_g":0.0,"status":"ok"}\n',
)
# She warned that creep can leave WEIGHT_STABLE and come back. These lines are that case.
DRIFT_LINES = (
    b'{"v":1,"type":"status","seq":3400,"timestamp_ms":325000,"state":"WEIGHT_CHANGED"}\n',
    b'{"v":1,"type":"weight","seq":3401,"timestamp_ms":325100,"weight_g":221.8,"stable":false,"tare_g":0.0,"status":"ok"}\n',
    b'{"v":1,"type":"status","seq":3480,"timestamp_ms":330000,"state":"WEIGHT_STABLE"}\n',
    b'{"v":1,"type":"weight","seq":3481,"timestamp_ms":330100,"weight_g":221.8,"stable":true,"tare_g":0.0,"status":"ok"}\n',
)


async def replay_placement(port: ScriptedPort) -> Sale | None:
    device = SerialScaleDevice(port)
    quote = identify_and_price("banana.jpg", MockVision(), TableProductInfo())
    pricer = PlacementPricer()
    sale: Sale | None = None
    await device.connect()
    try:
        async for event in device.events():
            if not isinstance(event, WeightReading):
                continue
            priced = pricer.consider(event, quote)
            if priced is None:
                continue
            sale = priced
            await device.display(
                DisplayRequest(
                    product=sale.label,
                    weight_g=sale.weight_g,
                    price=sale.amount_yuan,
                )
            )
        return sale
    finally:
        await device.disconnect()


def main() -> None:
    port = ScriptedPort(CAPTURED_PLACE_LINES + DRIFT_LINES)
    sale = asyncio.run(replay_placement(port))
    shown = json.loads(port.outgoing[0].decode("utf-8")) if port.outgoing else None
    print(f"label: {sale.label if sale else ''}")
    print(f"weight_g: {sale.weight_g if sale else ''}")
    print(f"amount_yuan: {sale.amount_yuan if sale else ''}")
    print(f"portion_kcal: {sale.portion_kcal if sale else ''}")
    print(f"portion_carb_g: {sale.portion_carb_g if sale else ''}")
    print(f"displays: {len(port.outgoing)}")
    print("sent_to_internet: no")
    if (
        sale is None
        or shown is None
        or len(port.outgoing) != 1
        or sale.weight_g != 221.1
        or sale.amount_yuan != 2.65
        or shown["price"] != 2.65
    ):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
    sys.exit(0)
