import pytest

from scale_host.storage import DeviceEvent, SqliteRepository, WeighingSession


def test_session_and_correction_round_trip(tmp_path) -> None:
    repository = SqliteRepository(tmp_path / "scale.db")
    repository.save_session(
        WeighingSession(
            id="s1",
            timestamp="2026-09-27T12:00:00",
            weight_g=326.4,
            image_path="data/test_images/banana.jpg",
            confidence=0.91,
            model_name="mock",
        )
    )
    stored = repository.get_session("s1")
    assert stored is not None
    assert stored.weight_g == 326.4
    assert stored.image_path == "data/test_images/banana.jpg"

    repository.add_correction("s1", predicted_product="apple", correct_product="banana")
    correction = repository.get_correction("s1")
    assert correction is not None
    assert correction.predicted_product == "apple"
    assert correction.correct_product == "banana"
    assert correction.weight_g == 326.4
    assert correction.image_path == "data/test_images/banana.jpg"


def test_missing_session_has_no_correction(tmp_path) -> None:
    repository = SqliteRepository(tmp_path / "scale.db")
    assert repository.get_session("missing") is None
    with pytest.raises(KeyError):
        repository.add_correction("missing", "apple", "banana")


def test_device_event_is_appended(tmp_path) -> None:
    repository = SqliteRepository(tmp_path / "scale.db")
    repository.add_device_event(
        DeviceEvent(
            timestamp="2026-09-27T12:00:01",
            device_id="simulator",
            event_type="WEIGHT_STABLE",
            payload='{"weight_g":326.4}',
        )
    )
    events = repository.list_device_events()
    assert len(events) == 1
    assert events[0].event_type == "WEIGHT_STABLE"


def test_older_database_can_store_a_sale_amount(tmp_path) -> None:
    import sqlite3

    path = tmp_path / "old.db"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE products (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price_per_kg REAL NOT NULL,
            nutrition_id TEXT
        );
        CREATE TABLE weighing_sessions (
            id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            weight_g REAL NOT NULL,
            image_path TEXT,
            product_id TEXT,
            confidence REAL,
            model_name TEXT
        );
        CREATE TABLE corrections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            predicted_product TEXT NOT NULL,
            correct_product TEXT NOT NULL
        );
        CREATE TABLE device_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            device_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            payload TEXT NOT NULL
        );
        """
    )
    connection.close()
    repository = SqliteRepository(path)
    repository.save_session(
        WeighingSession(
            id="s1",
            timestamp="2026-09-27T12:00:00",
            weight_g=326.4,
            label="banana",
            price_per_kg=12.0,
            amount_yuan=3.92,
        )
    )
    stored = repository.get_session("s1")
    assert stored is not None
    assert stored.amount_yuan == 3.92

