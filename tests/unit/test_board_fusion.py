import os
import time

import pytest

from scale_host.camera import take_jpegs
from scale_host.frames import current_frame
from scale_host.vision.interface import build_vision
from scale_host.vision.yolo import YoloVision, best_known


def test_yolo_provider_does_not_load_a_model() -> None:
    assert build_vision("yolo").name == "yolo"


def test_yolo_keeps_the_known_fruit_with_the_higher_confidence(monkeypatch) -> None:
    def _detect(_path, _confidence):
        return {
            "detections": [
                {"label": "person", "confidence": 0.99},
                {"label": "banana", "confidence": 0.2},
                {"label": "apple", "confidence": 0.4},
            ]
        }

    monkeypatch.setattr("scale_host.vision.yolo.detect", _detect)
    seen = YoloVision().recognize("frame.jpg")
    assert seen.label == "apple"
    assert seen.confidence == 0.4
    assert seen.source == "yolo"


def test_yolo_without_a_table_fruit_is_not_a_sale(monkeypatch) -> None:
    monkeypatch.setattr(
        "scale_host.vision.yolo.detect",
        lambda _path, _confidence: {"detections": [{"label": "bottle", "confidence": 0.8}]},
    )
    with pytest.raises(RuntimeError):
        YoloVision().recognize("frame.jpg")


def test_best_known_ignores_labels_outside_the_table() -> None:
    assert best_known([{"label": "broccoli", "confidence": 0.9}]) is None


def test_openmv_bytes_become_one_jpeg() -> None:
    payload = b"\xff\xd8\xff\xd9"
    buffer = bytearray(b"\x00\xa5\x5a" + len(payload).to_bytes(4, "little") + payload + b"\xa5")
    assert take_jpegs(buffer) == [payload]


def test_stale_live_frame_is_not_this_placement(tmp_path, monkeypatch) -> None:
    photo = tmp_path / "last_frame.jpg"
    photo.write_bytes(b"jpg")
    old = time.time() - 30
    os.utime(photo, (old, old))
    monkeypatch.setenv("SCALE_FRAME", str(photo))
    monkeypatch.setenv("SCALE_FRAME_MAX_AGE_S", "2")
    assert current_frame() is None
    fresh = time.time()
    os.utime(photo, (fresh, fresh))
    assert current_frame() == str(photo)
