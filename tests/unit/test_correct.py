import pytest

from scale_host.correct import apply_correction, main
from scale_host.storage import SqliteRepository, WeighingSession


def test_correction_keeps_the_weighing(tmp_path) -> None:
    repository = SqliteRepository(tmp_path / "scale.db")
    repository.save_session(
        WeighingSession(
            id="s1",
            timestamp="2026-09-27T12:00:00",
            weight_g=326.4,
            image_path="banana.jpg",
            label="banana",
            price_per_kg=12.0,
            amount_yuan=3.92,
        )
    )
    stored = apply_correction(repository, "s1", "apple")
    assert stored.predicted_product == "banana"
    assert stored.correct_product == "apple"
    assert stored.weight_g == 326.4
    assert stored.image_path == "banana.jpg"


def test_missing_session_cannot_be_corrected(tmp_path) -> None:
    repository = SqliteRepository(tmp_path / "scale.db")
    with pytest.raises(KeyError):
        apply_correction(repository, "missing", "apple")


def test_correct_command_prints_the_saved_correction(capsys, monkeypatch) -> None:
    monkeypatch.setenv("VISION_PROVIDER", "mock")
    monkeypatch.setenv("PRODUCT_INFO_PROVIDER", "mock")
    main()
    assert capsys.readouterr().out.splitlines() == [
        "predicted: banana",
        "correct: apple",
        "weight_g: 326.4",
        "image_path: banana.jpg",
    ]
