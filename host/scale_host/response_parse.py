"""Turn loopback JSON into host objects. Vision replies do not set the price."""

from __future__ import annotations

import sys

from scale_host.catalog.lookup import ProductInfo
from scale_host.domain import ProductRecognition

_IDENTIFY_REPLY = {"label": "banana", "confidence": 0.91, "price_per_kg": 999}
_PRICE_REPLY = {
    "label": "banana",
    "price_per_kg": 12.0,
    "summary": "loopback fixture",
}


def parse_identify(payload: dict[str, object], image_path: str) -> ProductRecognition:
    label = payload.get("label")
    confidence = payload.get("confidence")
    if not isinstance(label, str) or label == "":
        raise ValueError("missing label")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise ValueError("missing confidence")
    return ProductRecognition(
        label=label,
        confidence=float(confidence),
        source="loopback",
        image_id=image_path,
    )


def parse_price(payload: dict[str, object]) -> ProductInfo:
    label = payload.get("label")
    price = payload.get("price_per_kg")
    summary = payload.get("summary", "")
    if not isinstance(label, str) or label == "":
        raise ValueError("missing label")
    if isinstance(price, bool) or not isinstance(price, (int, float)):
        raise ValueError("missing price")
    if not isinstance(summary, str):
        raise ValueError("bad summary")
    return ProductInfo(
        label=label,
        price_per_kg=float(price),
        summary=summary,
        source="loopback",
    )


def main() -> None:
    recognition = parse_identify(_IDENTIFY_REPLY, "banana.jpg")
    info = parse_price(_PRICE_REPLY)
    print(f"label: {recognition.label}")
    print(f"confidence: {recognition.confidence}")
    print("price_from_vision: no")
    print(f"text_price_per_kg: {info.price_per_kg}")
    print(f"source: {info.source}")


if __name__ == "__main__":
    main()
    sys.exit(0)
