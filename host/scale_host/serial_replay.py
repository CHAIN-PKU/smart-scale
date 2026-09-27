"""Replay one stable weight line without opening a COM port."""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv

from scale_host.pipeline import DEMO_TIMESTAMP, price_open_port
from scale_host.providers import MissingApiKey, RemoteCallNotReady
from scale_host.storage import SqliteRepository

REPLAY_SESSION_ID = "banana-replay"
BANANA_LINES = (
    b'{"v":1,"type":"status","seq":1,"timestamp_ms":10,"state":"WEIGHT_STABLE"}\n',
    b'{"v":1,"type":"weight","seq":2,"timestamp_ms":20,"weight_g":326.4,"stable":true,"tare_g":0,"status":"ok"}\n',
)


class ScriptedPort:
    def __init__(self, lines: tuple[bytes, ...] | list[bytes]) -> None:
        self.incoming = list(lines)
        self.outgoing: list[bytes] = []
        self.closed = False

    def write(self, data: bytes) -> None:
        self.outgoing.append(data)

    def readline(self) -> bytes:
        if not self.incoming:
            return b""
        return self.incoming.pop(0)

    def close(self) -> None:
        self.closed = True


def main() -> None:
    load_dotenv(override=False)
    port = ScriptedPort(BANANA_LINES)
    with tempfile.TemporaryDirectory() as folder:
        repository = SqliteRepository(Path(folder) / "scale.db")
        try:
            asyncio.run(
                price_open_port(
                    port,
                    repository,
                    session_id=REPLAY_SESSION_ID,
                    timestamp=DEMO_TIMESTAMP,
                )
            )
            stored = repository.get_session(REPLAY_SESSION_ID)
        except (RuntimeError, MissingApiKey, RemoteCallNotReady) as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(2) from exc
    if stored is None or stored.amount_yuan is None:
        print("sale was not stored", file=sys.stderr)
        raise SystemExit(2)
    print(f"label: {stored.label}")
    print(f"weight_g: {stored.weight_g}")
    print(f"price_per_kg: {stored.price_per_kg}")
    print(f"amount_yuan: {stored.amount_yuan:.2f}")
    print(f"stored: {stored.id}")


if __name__ == "__main__":
    main()
