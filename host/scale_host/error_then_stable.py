"""After a sensor error, price the next stable weight. No COM port is opened."""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

from scale_host.serial_replay import ScriptedPort
from scale_host.serial_reply import price_scripted_replies
from scale_host.storage import SqliteRepository

ERROR_THEN_STABLE = (
    b'{"v":1,"type":"status","seq":1,"timestamp_ms":10,"state":"ERROR","detail":"hx711"}\n',
    b'{"v":1,"type":"weight","seq":2,"timestamp_ms":20,"weight_g":0,"stable":false,"tare_g":12.7,"status":"error"}\n',
    b'{"v":1,"type":"status","seq":3,"timestamp_ms":30,"state":"READY"}\n',
    b'{"v":1,"type":"status","seq":4,"timestamp_ms":40,"state":"WEIGHT_STABLE"}\n',
    b'{"v":1,"type":"weight","seq":5,"timestamp_ms":50,"weight_g":326.4,"stable":true,"tare_g":0,"status":"ok"}\n',
)
AFTER_ERROR_SESSION_ID = "banana-after-error"


def main() -> None:
    port = ScriptedPort(ERROR_THEN_STABLE)
    with tempfile.TemporaryDirectory() as folder:
        repository = SqliteRepository(Path(folder) / "scale.db")
        stored, display_price, skipped = asyncio.run(
            price_scripted_replies(port, repository, session_id=AFTER_ERROR_SESSION_ID)
        )
    print(f"skipped: {skipped}")
    print(f"weight_g: {stored.weight_g}")
    print(f"display_price: {display_price:.2f}")
    print(f"stored: {stored.id}")
    print("sent_to_internet: no")
    if skipped != 1 or display_price != 3.92:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
    sys.exit(0)
