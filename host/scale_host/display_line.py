"""Turn a priced reply into the one display line the scale will receive."""

from __future__ import annotations

import sys

from scale_host.domain import ScaleStatus, WeightReading
from scale_host.fusion.price import Sale
from scale_host.protocol.messages import DisplayResultMessage
from scale_host.reply_sale import sale_from_replies

DEMO_REQUEST_ID = "r_001"
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


def display_line(sale: Sale, request_id: str) -> str:
    message = DisplayResultMessage(
        v=1,
        type="display_result",
        request_id=request_id,
        product=sale.label,
        weight_g=sale.weight_g,
        price=sale.amount_yuan,
    )
    return message.model_dump_json()


def main() -> None:
    sale = sale_from_replies(_IDENTIFY_REPLY, _PRICE_REPLY, "banana.jpg", _STABLE)
    print(display_line(sale, DEMO_REQUEST_ID))


if __name__ == "__main__":
    main()
    sys.exit(0)
