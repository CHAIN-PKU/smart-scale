"""Skip rising serial weights, then price the stable line from the text reply."""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

from scale_host.serial_replay import ScriptedPort
from scale_host.serial_reply import price_scripted_replies
from scale_host.serial_sequence import rising_lines
from scale_host.storage import SqliteRepository

SEQUENCE_REPLY_SESSION_ID = "banana-serial-sequence"


def main() -> None:
    port = ScriptedPort(rising_lines())
    with tempfile.TemporaryDirectory() as folder:
        repository = SqliteRepository(Path(folder) / "scale.db")
        stored, display_price, skipped = asyncio.run(
            price_scripted_replies(
                port,
                repository,
                session_id=SEQUENCE_REPLY_SESSION_ID,
            )
        )
    same = stored.amount_yuan == display_price
    print(f"skipped: {skipped}")
    print(f"weight_g: {stored.weight_g}")
    print(f"display_price: {display_price:.2f}")
    print(f"stored: {stored.id}")
    print(f"same_amount: {'yes' if same else 'no'}")
    print("sent_to_internet: no")
    if not same:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
    sys.exit(0)
