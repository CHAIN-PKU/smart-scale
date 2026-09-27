"""Print a scripted weighing. No serial port is opened."""

from __future__ import annotations

import argparse
import asyncio
import sys

from scale_host.device import DeviceLink, SimulatedScaleDevice
from scale_host.domain import ScaleStatus, WeightReading


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Replay a scale scenario.")
    parser.add_argument("--scenario", default="banana")
    args = parser.parse_args(argv)
    try:
        asyncio.run(_replay(args.scenario))
    except ValueError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(2) from exc


async def _replay(scenario: str) -> None:
    device = SimulatedScaleDevice(scenario)
    await device.connect()
    last_weight: str | None = None
    async for event in device.events():
        if isinstance(event, DeviceLink):
            print(event.detail or "serial disconnected")
            return
        if not isinstance(event, WeightReading):
            continue
        shown = f"{event.weight_g:g} g"
        if shown != last_weight:
            print(shown)
            last_weight = shown
        if event.stable and event.state is ScaleStatus.WEIGHT_STABLE:
            print(f"{event.weight_g:g} g STABLE")
            return


if __name__ == "__main__":
    main()
