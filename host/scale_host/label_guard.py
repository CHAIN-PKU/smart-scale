"""Refuse a sale when the vision label and the text label disagree."""

from __future__ import annotations

import sys

from scale_host.domain import ScaleStatus, WeightReading
from scale_host.reply_sale import LabelMismatch, sale_from_replies

_VISION = {"label": "banana", "confidence": 0.91, "price_per_kg": 999}
_TEXT = {"label": "apple", "price_per_kg": 8.0, "summary": "loopback fixture"}
_STABLE = WeightReading(
    seq=1,
    timestamp_ms=0,
    weight_g=326.4,
    stable=True,
    tare_g=0.0,
    status="ok",
    state=ScaleStatus.WEIGHT_STABLE,
)


def mismatched_labels() -> LabelMismatch:
    try:
        sale_from_replies(_VISION, _TEXT, "banana.jpg", _STABLE)
    except LabelMismatch as exc:
        return exc
    raise RuntimeError("mismatched labels were priced")


def main() -> None:
    mismatch = mismatched_labels()
    print("priced: no")
    print("reason: label mismatch")
    print(f"vision_label: {mismatch.vision_label}")
    print(f"text_label: {mismatch.text_label}")
    print("display_sent: no")
    print("sent_to_internet: no")


if __name__ == "__main__":
    main()
    sys.exit(0)
