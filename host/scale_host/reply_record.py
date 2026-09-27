"""Store the reply-priced sale and check it matches the display line."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from scale_host.display_line import DEMO_REQUEST_ID, display_line
from scale_host.domain import ScaleStatus, WeightReading
from scale_host.pipeline import session_from_sale
from scale_host.reply_sale import sale_from_replies
from scale_host.storage import SqliteRepository

REPLY_SESSION_ID = "banana-reply"
REPLY_TIMESTAMP = "2026-09-27T12:00:00"
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


def record_reply_sale(repository: SqliteRepository) -> tuple[float, float]:
    sale = sale_from_replies(_IDENTIFY_REPLY, _PRICE_REPLY, "banana.jpg", _STABLE)
    session = session_from_sale(
        sale,
        session_id=REPLY_SESSION_ID,
        timestamp=REPLY_TIMESTAMP,
    )
    repository.save_session(session)
    stored = repository.get_session(REPLY_SESSION_ID)
    if stored is None or stored.amount_yuan is None:
        raise RuntimeError("sale was not stored")
    shown = json.loads(display_line(sale, DEMO_REQUEST_ID))["price"]
    return stored.amount_yuan, float(shown)


def main() -> None:
    with tempfile.TemporaryDirectory() as folder:
        repository = SqliteRepository(Path(folder) / "scale.db")
        stored_amount, display_price = record_reply_sale(repository)
    same = stored_amount == display_price
    print(f"stored: {REPLY_SESSION_ID}")
    print(f"amount_yuan: {stored_amount:.2f}")
    print(f"display_price: {display_price:.2f}")
    print(f"same_amount: {'yes' if same else 'no'}")
    if not same:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
    sys.exit(0)
