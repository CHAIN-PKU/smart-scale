"""Save one stable weighing after recognition, price lookup, and fusion."""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv

from scale_host.fusion import Sale
from scale_host.providers import MissingApiKey, RemoteCallNotReady
from scale_host.sale import price_stable_scenario
from scale_host.storage import SqliteRepository, WeighingSession

DEMO_SESSION_ID = "banana-demo"
DEMO_TIMESTAMP = "2026-09-27T12:00:00"


def session_from_sale(sale: Sale, *, session_id: str, timestamp: str) -> WeighingSession:
    return WeighingSession(
        id=session_id,
        timestamp=timestamp,
        weight_g=sale.weight_g,
        image_path=sale.image_path,
        confidence=sale.confidence,
        model_name=sale.vision_source,
        label=sale.label,
        price_per_kg=sale.price_per_kg,
        amount_yuan=sale.amount_yuan,
    )


async def record_stable_sale(
    repository: SqliteRepository,
    *,
    session_id: str,
    timestamp: str,
) -> WeighingSession:
    sale = await price_stable_scenario()
    session = session_from_sale(sale, session_id=session_id, timestamp=timestamp)
    repository.save_session(session)
    return session


def main() -> None:
    load_dotenv(override=False)
    with tempfile.TemporaryDirectory() as folder:
        repository = SqliteRepository(Path(folder) / "scale.db")
        try:
            asyncio.run(
                record_stable_sale(
                    repository,
                    session_id=DEMO_SESSION_ID,
                    timestamp=DEMO_TIMESTAMP,
                )
            )
            stored = repository.get_session(DEMO_SESSION_ID)
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
