"""Price a stable weight from parsed loopback replies. No socket is opened."""

from __future__ import annotations

import sys

from scale_host.domain import ScaleStatus, WeightReading
from scale_host.fusion.price import Sale, fuse
from scale_host.quote import ItemQuote
from scale_host.response_parse import parse_identify, parse_price

_IDENTIFY_REPLY = {"label": "banana", "confidence": 0.91, "price_per_kg": 999}
_PRICE_REPLY = {
    "label": "banana",
    "price_per_kg": 12.0,
    "summary": "loopback fixture",
}
_STABLE = WeightReading(
    seq=1,
    timestamp_ms=0,
    weight_g=326.4,
    stable=True,
    tare_g=0.0,
    status="ok",
    state=ScaleStatus.WEIGHT_STABLE,
)


class LabelMismatch(RuntimeError):
    def __init__(self, vision_label: str, text_label: str) -> None:
        self.vision_label = vision_label
        self.text_label = text_label
        super().__init__("label mismatch")


def sale_from_replies(
    identify_payload: dict[str, object],
    price_payload: dict[str, object],
    image_path: str,
    reading: WeightReading,
) -> Sale:
    recognition = parse_identify(identify_payload, image_path)
    info = parse_price(price_payload)
    if info.label != recognition.label:
        raise LabelMismatch(recognition.label, info.label)
    if info.price_per_kg is None:
        raise RuntimeError(f"no unit price for {recognition.label}")
    quote = ItemQuote(
        label=recognition.label,
        confidence=recognition.confidence,
        price_per_kg=info.price_per_kg,
        summary=info.summary,
        vision_source=recognition.source,
        info_source=info.source,
        image_path=image_path,
    )
    return fuse(reading, quote)


def main() -> None:
    sale = sale_from_replies(_IDENTIFY_REPLY, _PRICE_REPLY, "banana.jpg", _STABLE)
    print(f"label: {sale.label}")
    print(f"weight_g: {sale.weight_g}")
    print("price_from_vision: no")
    print(f"price_per_kg: {sale.price_per_kg}")
    print(f"amount_yuan: {sale.amount_yuan:.2f}")
    print(f"source: {sale.info_source}")


if __name__ == "__main__":
    main()
    sys.exit(0)
