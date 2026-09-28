"""Refuse a price when the scale reports a sensor error. No COM port is opened."""

from __future__ import annotations

import asyncio
import sys

from scale_host.device.serial_device import SerialScaleDevice
from scale_host.domain import ScaleStatus, WeightReading
from scale_host.serial_replay import ScriptedPort

ERROR_LINES = (
    b'{"v":1,"type":"status","seq":1,"timestamp_ms":10,"state":"ERROR","detail":"hx711"}\n',
    b'{"v":1,"type":"weight","seq":2,"timestamp_ms":20,"weight_g":0,"stable":false,"tare_g":12.7,"status":"error"}\n',
)


async def refusal_reason(port: ScriptedPort) -> str:
    device = SerialScaleDevice(port)
    await device.connect()
    try:
        async for event in device.events():
            if not isinstance(event, WeightReading):
                continue
            if event.state is ScaleStatus.ERROR or event.status == "error":
                return "error"
        return "no stable weight"
    finally:
        await device.disconnect()


def main() -> None:
    port = ScriptedPort(ERROR_LINES)
    reason = asyncio.run(refusal_reason(port))
    print("priced: no")
    print(f"reason: {reason}")
    print(f"display_sent: {'yes' if port.outgoing else 'no'}")
    print("sent_to_internet: no")
    if reason != "error" or port.outgoing:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
    sys.exit(0)
