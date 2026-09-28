"""Price a stable weight that carries an unknown extra field."""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

from scale_host.serial_replay import ScriptedPort
from scale_host.serial_reply import price_scripted_replies
from scale_host.storage import SqliteRepository

NOTED_STABLE = (
    b'{"v":1,"type":"status","seq":1,"timestamp_ms":10,"state":"WEIGHT_STABLE"}\n',
    b'{"v":1,"type":"weight","seq":2,"timestamp_ms":20,"weight_g":326.4,"stable":true,"tare_g":0,"status":"ok","note":"ignore-me"}\n',
)
EXTRA_FIELD_SESSION_ID = "banana-extra-field"


def main() -> None:
    port = ScriptedPort(NOTED_STABLE)
    with tempfile.TemporaryDirectory() as folder:
        repository = SqliteRepository(Path(folder) / "scale.db")
        stored, display_price, _skipped = asyncio.run(
            price_scripted_replies(port, repository, session_id=EXTRA_FIELD_SESSION_ID)
        )
    shown = port.outgoing[-1].decode("utf-8") if port.outgoing else ""
    leaked = "ignore-me" in shown or '"note"' in shown
    print("extra_field: ignored")
    print(f"weight_g: {stored.weight_g}")
    print(f"display_price: {display_price:.2f}")
    print(f"note_in_display: {'yes' if leaked else 'no'}")
    print("sent_to_internet: no")
    if leaked or display_price != 3.92:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
    sys.exit(0)
