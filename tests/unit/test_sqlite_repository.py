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
