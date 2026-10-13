"""Turn a stable weight and table standards into one sale. No network."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from pydantic import BaseModel, ConfigDict, Field

from scale_host.domain import ScaleStatus, WeightReading
from scale_host.quote import ItemQuote

_MODEL_CONFIG = ConfigDict(extra="forbid")
_FEN = Decimal("0.01")
_TENTH = Decimal("0.1")


class Sale(BaseModel):
    model_config = _MODEL_CONFIG
    label: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    weight_g: float = Field(gt=0)
    price_per_kg: float = Field(ge=0)
    amount_yuan: float = Field(ge=0)
    portion_kcal: float | None = Field(default=None, ge=0)
    portion_carb_g: float | None = Field(default=None, ge=0)
    vision_source: str = Field(min_length=1)
    info_source: str = Field(min_length=1)
    image_path: str = Field(min_length=1)


def yuan_amount(weight_g: float, price_per_kg: float) -> float:
    grams = Decimal(str(weight_g))
    price = Decimal(str(price_per_kg))
    amount = (grams / Decimal("1000")) * price
    return float(amount.quantize(_FEN, rounding=ROUND_HALF_UP))


def portion_from_100g(weight_g: float, per_100g: float) -> float:
    grams = Decimal(str(weight_g))
    rate = Decimal(str(per_100g))
    amount = (grams / Decimal("100")) * rate
    return float(amount.quantize(_TENTH, rounding=ROUND_HALF_UP))


def fuse(reading: WeightReading, quote: ItemQuote) -> Sale:
    ready = (
        reading.state is ScaleStatus.WEIGHT_STABLE
        and reading.stable
        and reading.status == "ok"
        and reading.weight_g > 0
    )
    if not ready:
        raise RuntimeError("weight is not ready to price")
    portion_kcal = None
    portion_carb_g = None
    if quote.kcal_per_100g is not None:
        portion_kcal = portion_from_100g(reading.weight_g, quote.kcal_per_100g)
    if quote.carb_per_100g is not None:
        portion_carb_g = portion_from_100g(reading.weight_g, quote.carb_per_100g)
    return Sale(
        label=quote.label,
        confidence=quote.confidence,
        weight_g=reading.weight_g,
        price_per_kg=quote.price_per_kg,
        amount_yuan=yuan_amount(reading.weight_g, quote.price_per_kg),
        portion_kcal=portion_kcal,
        portion_carb_g=portion_carb_g,
        vision_source=quote.vision_source,
        info_source=quote.info_source,
        image_path=quote.image_path,
    )


class PlacementPricer:
    """One sale per placement. A later stable reading on the same item is ignored."""

    def __init__(self) -> None:
        self._priced = False

    def consider(self, reading: WeightReading, quote: ItemQuote) -> Sale | None:
        if reading.state in (ScaleStatus.WEIGHT_REMOVED, ScaleStatus.ZERO):
            self._priced = False
            return None
        if self._priced:
            return None
        try:
            sale = fuse(reading, quote)
        except RuntimeError:
            return None
        self._priced = True
        return sale
