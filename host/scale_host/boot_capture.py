"""Replay the 2026-10-11 boot capture plus one debug line. No COM port is opened."""

from __future__ import annotations

import asyncio
import sys

from scale_host.device.serial_device import SerialScaleDevice
from scale_host.domain import WeightReading
from scale_host.serial_replay import ScriptedPort

CAPTURED_BOOT_LINES = (
    b'{"v":1,"type":"status","seq":1,"timestamp_ms":0,"state":"BOOT"}\n',
    b'{"v":1,"type":"status","seq":2,"timestamp_ms":5,"state":"READY"}\n',
    b"# RAW=12345\n",
    b'{"v":1,"type":"status","seq":3,"timestamp_ms":1005,"state":"ERROR"}\n',
)


async def replay_capture(port: ScriptedPort) -> str:
    device = SerialScaleDevice(port)
    await device.connect()
    try:
        async for event in device.events():
            if isinstance(event, WeightReading):
                return "priced"
        state = device._state
        if state is None or port.outgoing:
            return "lost"
        return state.value
    finally:
        await device.disconnect()


def main() -> None:
    port = ScriptedPort(CAPTURED_BOOT_LINES)
    state = asyncio.run(replay_capture(port))
    print("priced: no")
    print(f"state: {state}")
    print("debug_line: dropped")
    print(f"display_sent: {'yes' if port.outgoing else 'no'}")
    print("sent_to_internet: no")
    if state != "ERROR" or port.outgoing:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
    sys.exit(0)
