"""Turn a stable weight and a unit price into an amount. No network and no catalog."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from pydantic import BaseModel, ConfigDict, Field

from scale_host.domain import ScaleStatus, WeightReading
from scale_host.quote import ItemQuote

_MODEL_CONFIG = ConfigDict(extra="forbid")
_FEN = Decimal("0.01")


class Sale(BaseModel):
    model_config = _MODEL_CONFIG
    label: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    weight_g: float = Field(gt=0)
    price_per_kg: float = Field(ge=0)
    amount_yuan: float = Field(ge=0)
    vision_source: str = Field(min_length=1)
    info_source: str = Field(min_length=1)
    image_path: str = Field(min_length=1)


def yuan_amount(weight_g: float, price_per_kg: float) -> float:
    grams = Decimal(str(weight_g))
    price = Decimal(str(price_per_kg))
    amount = (grams / Decimal("1000")) * price
    return float(amount.quantize(_FEN, rounding=ROUND_HALF_UP))


def fuse(reading: WeightReading, quote: ItemQuote) -> Sale:
    ready = (
        reading.state is ScaleStatus.WEIGHT_STABLE
        and reading.stable
        and reading.status == "ok"
        and reading.weight_g > 0
    )
    if not ready:
        raise RuntimeError("weight is not ready to price")
    return Sale(
        label=quote.label,
        confidence=quote.confidence,
        weight_g=reading.weight_g,
        price_per_kg=quote.price_per_kg,
        amount_yuan=yuan_amount(reading.weight_g, quote.price_per_kg),
        vision_source=quote.vision_source,
        info_source=quote.info_source,
        image_path=quote.image_path,
    )
