"""Drop a line longer than the V1 limit, then price the next stable weight."""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

from scale_host.serial_replay import ScriptedPort
from scale_host.serial_reply import price_scripted_replies
from scale_host.storage import SqliteRepository

LONG_LINE_SESSION_ID = "banana-long-line"


def overlong_line() -> bytes:
    """One serial line whose payload exceeds the 512-byte V1 limit."""
    body = b'{"v":1,"note":"' + (b"x" * 600) + b'"}\n'
    if len(body) <= 514:
        raise RuntimeError("fixture is not over the line limit")
    return body


def lines() -> tuple[bytes, ...]:
    return (
        b'{"v":1,"type":"status","seq":1,"timestamp_ms":10,"state":"WEIGHT_STABLE"}\n',
        overlong_line(),
        b'{"v":1,"type":"weight","seq":2,"timestamp_ms":20,"weight_g":326.4,"stable":true,"tare_g":0,"status":"ok"}\n',
    )


def main() -> None:
    port = ScriptedPort(lines())
    with tempfile.TemporaryDirectory() as folder:
        repository = SqliteRepository(Path(folder) / "scale.db")
        stored, display_price, _skipped = asyncio.run(
            price_scripted_replies(port, repository, session_id=LONG_LINE_SESSION_ID)
        )
    print("long_line: dropped")
    print(f"weight_g: {stored.weight_g}")
    print(f"display_price: {display_price:.2f}")
    print(f"stored: {stored.id}")
    print("sent_to_internet: no")
    if display_price != 3.92:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
    sys.exit(0)
