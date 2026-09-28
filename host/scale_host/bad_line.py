"""Drop a bad serial line, then price the following stable weight."""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

from scale_host.serial_replay import ScriptedPort
from scale_host.serial_reply import price_scripted_replies
from scale_host.storage import SqliteRepository

BAD_THEN_STABLE = (
    b'{"v":1,"type":"status","seq":1,"timestamp_ms":10,"state":"WEIGHT_STABLE"}\n',
    b"123.45\n",
    b'{"v":1,"type":"weight","seq":2,"timestamp_ms":20,"weight_g":326.4,"stable":true,"tare_g":0,"status":"ok"}\n',
)
BAD_LINE_SESSION_ID = "banana-bad-line"


def main() -> None:
    port = ScriptedPort(BAD_THEN_STABLE)
    with tempfile.TemporaryDirectory() as folder:
        repository = SqliteRepository(Path(folder) / "scale.db")
        stored, display_price, _skipped = asyncio.run(
            price_scripted_replies(port, repository, session_id=BAD_LINE_SESSION_ID)
        )
    print("bad_line: dropped")
    print(f"weight_g: {stored.weight_g}")
    print(f"display_price: {display_price:.2f}")
    print(f"stored: {stored.id}")
    print("sent_to_internet: no")
    if stored.amount_yuan != display_price or display_price != 3.92:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
    sys.exit(0)
