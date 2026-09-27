"""SQLite storage using the Python standard library."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from scale_host.storage.records import CorrectionRecord, DeviceEvent, WeighingSession


class SqliteRepository:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(_SCHEMA)

    def save_session(self, session: WeighingSession) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO weighing_sessions (
                    id, timestamp, weight_g, image_path, product_id, confidence, model_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.id,
                    session.timestamp,
                    session.weight_g,
                    session.image_path,
                    session.product_id,
                    session.confidence,
                    session.model_name,
                ),
            )

    def get_session(self, session_id: str) -> WeighingSession | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, timestamp, weight_g, image_path, product_id, confidence, model_name
                FROM weighing_sessions WHERE id = ?
                """,
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return WeighingSession(
            id=row[0],
            timestamp=row[1],
            weight_g=row[2],
            image_path=row[3],
            product_id=row[4],
            confidence=row[5],
            model_name=row[6],
        )

    def add_correction(
        self,
        session_id: str,
        predicted_product: str,
        correct_product: str,
    ) -> None:
        with self._connect() as connection:
            found = connection.execute(
                "SELECT 1 FROM weighing_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            if found is None:
                raise KeyError(session_id)
            connection.execute(
                """
                INSERT INTO corrections (session_id, predicted_product, correct_product)
                VALUES (?, ?, ?)
                """,
                (session_id, predicted_product, correct_product),
            )

    def get_correction(self, session_id: str) -> CorrectionRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT c.session_id, c.predicted_product, c.correct_product,
                       s.weight_g, s.image_path
                FROM corrections AS c
                JOIN weighing_sessions AS s ON s.id = c.session_id
                WHERE c.session_id = ?
                ORDER BY c.id DESC
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return CorrectionRecord(
            session_id=row[0],
            predicted_product=row[1],
            correct_product=row[2],
            weight_g=row[3],
            image_path=row[4],
        )

    def add_device_event(self, event: DeviceEvent) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO device_events (timestamp, device_id, event_type, payload)
                VALUES (?, ?, ?, ?)
                """,
                (event.timestamp, event.device_id, event.event_type, event.payload),
            )

    def list_device_events(self) -> list[DeviceEvent]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT timestamp, device_id, event_type, payload
                FROM device_events ORDER BY id
                """
            ).fetchall()
        return [
            DeviceEvent(timestamp=row[0], device_id=row[1], event_type=row[2], payload=row[3])
            for row in rows
        ]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


_SCHEMA = """
-- Optional cache only. Prices come from the text model, not from a full local catalog.
CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    price_per_kg REAL NOT NULL,
    nutrition_id TEXT
);

CREATE TABLE IF NOT EXISTS weighing_sessions (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    weight_g REAL NOT NULL,
    image_path TEXT,
    product_id TEXT,
    confidence REAL,
    model_name TEXT,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    predicted_product TEXT NOT NULL,
    correct_product TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES weighing_sessions(id)
);

CREATE TABLE IF NOT EXISTS device_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    device_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL
);
"""
