"""Identify an item, then look up its unit price. This step does not use weight."""

from __future__ import annotations

import sys

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field

from scale_host.catalog.lookup import ProductInfoProvider, build_product_info
from scale_host.providers import MissingApiKey, RemoteCallNotReady
from scale_host.vision.interface import VisionProvider, build_vision

_MODEL_CONFIG = ConfigDict(extra="forbid")
DEMO_IMAGE = "banana.jpg"


class ItemQuote(BaseModel):
    model_config = _MODEL_CONFIG
    label: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    price_per_kg: float = Field(ge=0)
    summary: str = ""
    vision_source: str = Field(min_length=1)
    info_source: str = Field(min_length=1)
    image_path: str = Field(min_length=1)


def identify_and_price(
    image_path: str,
    vision: VisionProvider,
    product_info: ProductInfoProvider,
) -> ItemQuote:
    recognition = vision.recognize(image_path)
    info = product_info.lookup(recognition.label)
    if info.price_per_kg is None:
        raise RuntimeError(f"no unit price for {recognition.label}")
    return ItemQuote(
        label=recognition.label,
        confidence=recognition.confidence,
        price_per_kg=info.price_per_kg,
        summary=info.summary,
        vision_source=recognition.source,
        info_source=info.source,
        image_path=image_path,
    )


def main() -> None:
    load_dotenv(override=False)
    try:
        quote = identify_and_price(DEMO_IMAGE, build_vision(), build_product_info())
    except (RuntimeError, MissingApiKey, RemoteCallNotReady) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
    print(f"label: {quote.label}")
    print(f"price_per_kg: {quote.price_per_kg}")


if __name__ == "__main__":
    main()
