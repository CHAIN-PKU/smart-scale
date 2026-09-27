"""Record that a stored weighing was given the wrong product name."""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv

from scale_host.pipeline import DEMO_TIMESTAMP, price_open_port
from scale_host.providers import MissingApiKey, RemoteCallNotReady
from scale_host.serial_replay import ScriptedPort
from scale_host.serial_sequence import SEQUENCE_SESSION_ID, rising_lines
from scale_host.storage import CorrectionRecord, SqliteRepository


def apply_correction(
    repository: SqliteRepository,
    session_id: str,
    correct_product: str,
) -> CorrectionRecord:
    session = repository.get_session(session_id)
    if session is None or session.label is None:
        raise KeyError(session_id)
    repository.add_correction(session_id, session.label, correct_product)
    stored = repository.get_correction(session_id)
    if stored is None:
        raise KeyError(session_id)
    return stored


def main() -> None:
    load_dotenv(override=False)
    port = ScriptedPort(rising_lines())
    with tempfile.TemporaryDirectory() as folder:
        repository = SqliteRepository(Path(folder) / "scale.db")
        try:
            asyncio.run(
                price_open_port(
                    port,
                    repository,
                    session_id=SEQUENCE_SESSION_ID,
                    timestamp=DEMO_TIMESTAMP,
                )
            )
            correction = apply_correction(repository, SEQUENCE_SESSION_ID, "apple")
        except (RuntimeError, MissingApiKey, RemoteCallNotReady, KeyError) as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(2) from exc
    print(f"predicted: {correction.predicted_product}")
    print(f"correct: {correction.correct_product}")
    print(f"weight_g: {correction.weight_g}")
    print(f"image_path: {correction.image_path}")


if __name__ == "__main__":
    main()
