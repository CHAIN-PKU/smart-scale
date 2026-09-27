"""Price the stable banana scenario with the mock recognizer. No network."""

from __future__ import annotations

import asyncio
import sys

from dotenv import load_dotenv

from scale_host.catalog.lookup import build_product_info
from scale_host.device.simulator import SimulatedScaleDevice
from scale_host.domain import ScaleStatus, WeightReading
from scale_host.fusion import Sale, fuse
from scale_host.providers import MissingApiKey, RemoteCallNotReady
from scale_host.quote import DEMO_IMAGE, identify_and_price
from scale_host.vision.interface import build_vision


async def price_stable_scenario(scenario: str = "banana") -> Sale:
    device = SimulatedScaleDevice(scenario)
    await device.connect()
    try:
        async for event in device.events():
            if isinstance(event, WeightReading) and event.state is ScaleStatus.WEIGHT_STABLE:
                quote = identify_and_price(DEMO_IMAGE, build_vision(), build_product_info())
                return fuse(event, quote)
    finally:
        await device.disconnect()
    raise RuntimeError("weight is not ready to price")


def main() -> None:
    load_dotenv(override=False)
    try:
        sale = asyncio.run(price_stable_scenario())
    except (RuntimeError, MissingApiKey, RemoteCallNotReady) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
    print(f"label: {sale.label}")
    print(f"weight_g: {sale.weight_g}")
    print(f"price_per_kg: {sale.price_per_kg}")
    print(f"amount_yuan: {sale.amount_yuan:.2f}")


if __name__ == "__main__":
    main()
