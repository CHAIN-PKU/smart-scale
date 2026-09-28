"""Price one stable placement, then stay silent after the item is removed."""

from __future__ import annotations

import asyncio
import json
import sys

from scale_host.device.interface import DisplayRequest
from scale_host.device.serial_device import SerialScaleDevice
from scale_host.domain import ScaleStatus, WeightReading
from scale_host.reply_sale import sale_from_replies
from scale_host.serial_replay import ScriptedPort

PLACE_AND_REMOVE_LINES = (
    b'{"v":1,"type":"status","seq":1,"timestamp_ms":10,"state":"WEIGHT_CHANGED"}\n',
    b'{"v":1,"type":"weight","seq":2,"timestamp_ms":20,"weight_g":145,"stable":false,"tare_g":0,"status":"ok"}\n',
    b'{"v":1,"type":"status","seq":3,"timestamp_ms":30,"state":"WEIGHT_STABLE"}\n',
    b'{"v":1,"type":"weight","seq":4,"timestamp_ms":40,"weight_g":326.4,"stable":true,"tare_g":0,"status":"ok"}\n',
    b'{"v":1,"type":"status","seq":5,"timestamp_ms":50,"state":"WEIGHT_REMOVED"}\n',
    b'{"v":1,"type":"weight","seq":6,"timestamp_ms":60,"weight_g":0.4,"stable":true,"tare_g":0,"status":"ok"}\n',
)
_IDENTIFY_REPLY = {"label": "banana", "confidence": 0.91, "price_per_kg": 999}
_PRICE_REPLY = {
    "label": "banana",
    "price_per_kg": 12.0,
    "summary": "loopback fixture",
}


async def price_once_then_stop(port: ScriptedPort) -> tuple[int, float, bool]:
    device = SerialScaleDevice(port)
    await device.connect()
    priced = False
    saw_removed = False
    try:
        async for event in device.events():
            if not isinstance(event, WeightReading):
                continue
            if event.state is ScaleStatus.WEIGHT_REMOVED:
                saw_removed = True
                continue
            if priced:
                continue
            ready = (
                event.state is ScaleStatus.WEIGHT_STABLE
                and event.stable
                and event.status == "ok"
                and event.weight_g > 0
            )
            if not ready:
                continue
            sale = sale_from_replies(_IDENTIFY_REPLY, _PRICE_REPLY, "banana.jpg", event)
            await device.display(
                DisplayRequest(
                    product=sale.label,
                    weight_g=sale.weight_g,
                    price=sale.amount_yuan,
                )
            )
            priced = True
        if not port.outgoing:
            raise RuntimeError("no display line")
        shown = float(json.loads(port.outgoing[0].decode("utf-8"))["price"])
        return len(port.outgoing), shown, saw_removed
    finally:
        await device.disconnect()


def main() -> None:
    port = ScriptedPort(PLACE_AND_REMOVE_LINES)
    displays, price, saw_removed = asyncio.run(price_once_then_stop(port))
    quiet_after_remove = saw_removed and displays == 1
    print(f"displays: {displays}")
    print(f"display_price: {price:.2f}")
    print(f"after_remove: {'yes' if not quiet_after_remove else 'no'}")
    print("sent_to_internet: no")
    if not quiet_after_remove or price != 3.92:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
    sys.exit(0)
