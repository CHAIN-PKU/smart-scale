"""Send tare on a scripted port and read the zeroed weight. No COM port is opened."""

from __future__ import annotations

import asyncio
import sys

from scale_host.device.serial_device import SerialScaleDevice
from scale_host.domain import ScaleStatus, WeightReading
from scale_host.serial_replay import ScriptedPort

TARE_LINES = (
    b'{"v":1,"type":"ack","seq":1,"timestamp_ms":10,"command":"tare","status":"ok"}\n',
    b'{"v":1,"type":"status","seq":2,"timestamp_ms":20,"state":"ZERO"}\n',
    b'{"v":1,"type":"weight","seq":3,"timestamp_ms":30,"weight_g":0,"stable":true,"tare_g":12.7,"status":"ok"}\n',
)


async def tare_then_zero(port: ScriptedPort) -> tuple[str, WeightReading]:
    device = SerialScaleDevice(port)
    await device.connect()
    try:
        result = await device.tare()
        async for event in device.events():
            if isinstance(event, WeightReading):
                return result.status, event
        raise RuntimeError("no weight after tare")
    finally:
        await device.disconnect()


def main() -> None:
    port = ScriptedPort(TARE_LINES)
    ack, reading = asyncio.run(tare_then_zero(port))
    print("command: tare")
    print(f"ack: {ack}")
    print(f"next_state: {reading.state.value if reading.state is not None else ''}")
    print(f"weight_g: {reading.weight_g}")
    print(f"tare_g: {reading.tare_g}")
    print(f"display_sent: {'yes' if len(port.outgoing) > 1 else 'no'}")
    print("sent_to_internet: no")
    if ack != "ok" or reading.state is not ScaleStatus.ZERO or len(port.outgoing) != 1:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
    sys.exit(0)
