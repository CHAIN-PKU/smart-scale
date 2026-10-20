"""Price the already recognized OpenMV banana. No new photo call and no COM port."""

from __future__ import annotations

import asyncio
import sys

from scale_host.catalog import TableProductInfo
from scale_host.device.simulator import SimulatedScaleDevice
from scale_host.domain import WeightReading
from scale_host.fusion import PlacementPricer, Sale
from scale_host.quote import ItemQuote

RECOGNIZED_IMAGE = "data/test_images/openmv_banana.jpg"
RECOGNIZED_LABEL = "banana"


def quote_for_recognized_banana() -> ItemQuote:
    info = TableProductInfo().lookup(RECOGNIZED_LABEL)
    if info.price_per_kg is None:
        raise RuntimeError(f"no unit price for {RECOGNIZED_LABEL}")
    return ItemQuote(
        label=info.label,
        confidence=1.0,
        price_per_kg=info.price_per_kg,
        kcal_per_100g=info.kcal_per_100g,
        carb_per_100g=info.carb_per_100g,
        summary=info.summary,
        vision_source="siliconflow",
        info_source=info.source,
        image_path=RECOGNIZED_IMAGE,
    )


async def price_simulated_banana() -> Sale:
    quote = quote_for_recognized_banana()
    device = SimulatedScaleDevice("banana")
    pricer = PlacementPricer()
    await device.connect()
    try:
        async for event in device.events():
            if not isinstance(event, WeightReading):
                continue
            sale = pricer.consider(event, quote)
            if sale is not None:
                return sale
    finally:
        await device.disconnect()
    raise RuntimeError("weight is not ready to price")


def main() -> None:
    try:
        sale = asyncio.run(price_simulated_banana())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
    print(f"label: {sale.label}")
    print(f"image: {sale.image_path}")
    print(f"weight_g: {sale.weight_g}")
    print(f"amount_yuan: {sale.amount_yuan:.2f}")
    print(f"portion_kcal: {sale.portion_kcal}")
    print(f"portion_carb_g: {sale.portion_carb_g}")
    print("sent_to_internet: no")
    print("com_open: no")
    if sale.amount_yuan != 3.92 or sale.weight_g != 326.4:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
    sys.exit(0)
