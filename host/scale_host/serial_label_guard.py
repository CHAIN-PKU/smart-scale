"""A stable serial weight is not priced when the two labels disagree."""

from __future__ import annotations

import asyncio
import sys

from scale_host.device.serial_device import SerialScaleDevice
from scale_host.domain import ScaleStatus, WeightReading
from scale_host.reply_sale import LabelMismatch, sale_from_replies
from scale_host.serial_replay import BANANA_LINES, ScriptedPort

_VISION = {"label": "banana", "confidence": 0.91, "price_per_kg": 999}
_TEXT = {"label": "apple", "price_per_kg": 8.0, "summary": "loopback fixture"}


async def stable_weight_with_mismatch(port: ScriptedPort) -> tuple[float, LabelMismatch]:
    device = SerialScaleDevice(port)
    await device.connect()
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
                continue
            try:
                sale_from_replies(_VISION, _TEXT, "banana.jpg", event)
            except LabelMismatch as exc:
                return event.weight_g, exc
            raise RuntimeError("mismatched labels were priced")
        raise RuntimeError("no stable weight")
    finally:
        await device.disconnect()


def main() -> None:
    port = ScriptedPort(BANANA_LINES)
    weight_g, mismatch = asyncio.run(stable_weight_with_mismatch(port))
    print(f"weight_g: {weight_g}")
    print("priced: no")
    print("reason: label mismatch")
    print(f"vision_label: {mismatch.vision_label}")
    print(f"text_label: {mismatch.text_label}")
    print(f"display_sent: {'yes' if port.outgoing else 'no'}")
    print("sent_to_internet: no")
    if port.outgoing:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
    sys.exit(0)
