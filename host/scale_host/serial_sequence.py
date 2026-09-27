"""Replay a rising weight, then price only the stable line. No COM port is opened."""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv

from scale_host.pipeline import DEMO_TIMESTAMP, price_open_port
from scale_host.providers import MissingApiKey, RemoteCallNotReady
from scale_host.serial_replay import ScriptedPort
from scale_host.storage import SqliteRepository

SEQUENCE_SESSION_ID = "banana-sequence"
_RISING = (
    (0.0, "ZERO", False),
    (12.0, "WEIGHT_CHANGED", False),
    (145.0, "WEIGHT_CHANGED", False),
    (310.0, "WEIGHT_CHANGED", False),
    (326.0, "WEIGHT_CHANGED", False),
    (326.4, "WEIGHT_STABLE", True),
)


def rising_lines() -> tuple[bytes, ...]:
    frames: list[bytes] = []
    seq = 1
    timestamp_ms = 0
    for weight_g, state, stable in _RISING:
        frames.append(_frame(seq, timestamp_ms, "status", state=state))
        seq += 1
        timestamp_ms += 100
        frames.append(
            _frame(
                seq,
                timestamp_ms,
                "weight",
                weight_g=weight_g,
                stable=stable,
                tare_g=0,
                status="ok",
            )
        )
        seq += 1
        timestamp_ms += 100
    return tuple(frames)


def _frame(seq: int, timestamp_ms: int, message_type: str, **fields: object) -> bytes:
    payload = {"v": 1, "type": message_type, "seq": seq, "timestamp_ms": timestamp_ms, **fields}
    return (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")


def main() -> None:
    load_dotenv(override=False)
    port = ScriptedPort(rising_lines())
    with tempfile.TemporaryDirectory() as folder:
        repository = SqliteRepository(Path(folder) / "scale.db")
        try:
            _session, skipped = asyncio.run(
                price_open_port(
                    port,
                    repository,
                    session_id=SEQUENCE_SESSION_ID,
                    timestamp=DEMO_TIMESTAMP,
                )
            )
            stored = repository.get_session(SEQUENCE_SESSION_ID)
        except (RuntimeError, MissingApiKey, RemoteCallNotReady) as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(2) from exc
    if stored is None or stored.amount_yuan is None:
        print("sale was not stored", file=sys.stderr)
        raise SystemExit(2)
    print(f"skipped: {skipped}")
    print(f"label: {stored.label}")
    print(f"weight_g: {stored.weight_g}")
    print(f"price_per_kg: {stored.price_per_kg}")
    print(f"amount_yuan: {stored.amount_yuan:.2f}")
    print(f"stored: {stored.id}")


if __name__ == "__main__":
    main()
