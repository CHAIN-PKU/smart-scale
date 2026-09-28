"""Reject tare while the scale is still booting. The offset stays zero."""

from __future__ import annotations

import asyncio
import sys

from scale_host.device.serial_device import SerialScaleDevice
from scale_host.domain import ScaleStatus, WeightReading
from scale_host.serial_replay import ScriptedPort

BOOT_TARE_LINES = (
    b'{"v":1,"type":"ack","seq":1,"timestamp_ms":10,"command":"tare","status":"error"}\n',
    b'{"v":1,"type":"status","seq":2,"timestamp_ms":20,"state":"BOOT"}\n',
    b'{"v":1,"type":"weight","seq":3,"timestamp_ms":30,"weight_g":0,"stable":false,"tare_g":0,"status":"ok"}\n',
)


async def tare_while_booting(port: ScriptedPort) -> tuple[str, WeightReading]:
    device = SerialScaleDevice(port)
    await device.connect()
    try:
        result = await device.tare()
        async for event in device.events():
            if isinstance(event, WeightReading):
                return result.status, event
        raise RuntimeError("no weight after rejected tare")
    finally:
        await device.disconnect()


def main() -> None:
    port = ScriptedPort(BOOT_TARE_LINES)
    ack, reading = asyncio.run(tare_while_booting(port))
    print("command: tare")
    print(f"ack: {ack}")
    print(f"state: {reading.state.value if reading.state is not None else ''}")
    print(f"tare_g: {reading.tare_g}")
    print(f"display_sent: {'yes' if len(port.outgoing) > 1 else 'no'}")
    print("sent_to_internet: no")
    kept = (
        ack == "error"
        and reading.state is ScaleStatus.BOOT
        and reading.tare_g == 0
        and len(port.outgoing) == 1
    )
    if not kept:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
    sys.exit(0)
