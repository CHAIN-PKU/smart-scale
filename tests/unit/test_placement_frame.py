"""This placement's photo names the item. The serial weight sets the amount."""

import asyncio
import json

from scale_host.domain import ProductRecognition
from scale_host.frames import current_frame
from scale_host.pipeline import DEMO_TIMESTAMP, serve_open_port
from scale_host.serial_replay import ScriptedPort
from scale_host.storage import SqliteRepository


class _NamedFrames:
    name = "scripted"

    def __init__(self) -> None:
        self.paths: list[str] = []

    def recognize(self, image_path: str) -> ProductRecognition:
        self.paths.append(image_path)
        return ProductRecognition(
            label="banana",
            confidence=1.0,
            source="scripted",
            image_id=image_path,
        )


def _line(payload: dict) -> bytes:
    return (json.dumps(payload, separators=(",", ":")) + "\n").encode()


def _stable(weight_g: float, seq: int) -> list[bytes]:
    return [
        _line({"v": 1, "type": "status", "seq": seq - 1, "timestamp_ms": seq, "state": "WEIGHT_STABLE"}),
        _line(
            {
                "v": 1,
                "type": "weight",
                "seq": seq,
                "timestamp_ms": seq + 1,
                "weight_g": weight_g,
                "stable": True,
                "tare_g": 0,
                "status": "ok",
            }
        ),
    ]


def test_old_demo_photos_are_not_this_placement(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("SCALE_FRAME", raising=False)
    assert current_frame() is None
    for name in ("banana.jpg", "openmv.jpg", "openmv_banana.jpg"):
        photo = tmp_path / name
        photo.write_bytes(b"jpg")
        monkeypatch.setenv("SCALE_FRAME", str(photo))
        assert current_frame() is None
    live = tmp_path / "placement.jpg"
    live.write_bytes(b"jpg")
    monkeypatch.setenv("SCALE_FRAME", str(live))
    assert current_frame() == str(live)


def test_each_placement_uses_its_own_photo_and_the_serial_weight(tmp_path, monkeypatch) -> None:
    def _opened(*_args, **_kwargs):
        raise AssertionError("network opened")

    monkeypatch.setattr("urllib.request.urlopen", _opened)
    monkeypatch.setattr("serial.Serial", _opened)
    monkeypatch.setenv("PRODUCT_INFO_PROVIDER", "table")
    vision = _NamedFrames()
    frames = iter([str(tmp_path / "first.jpg"), str(tmp_path / "second.jpg")])
    monkeypatch.setattr("scale_host.pipeline.build_vision", lambda: vision)
    monkeypatch.setattr("scale_host.pipeline.current_frame", lambda: next(frames))
    port = ScriptedPort(
        [
            *_stable(200.0, 2),
            _line(
                {
                    "v": 1,
                    "type": "weight",
                    "seq": 4,
                    "timestamp_ms": 40,
                    "weight_g": 200.4,
                    "stable": True,
                    "tare_g": 0,
                    "status": "ok",
                }
            ),
            _line({"v": 1, "type": "status", "seq": 5, "timestamp_ms": 50, "state": "WEIGHT_REMOVED"}),
            _line(
                {
                    "v": 1,
                    "type": "weight",
                    "seq": 6,
                    "timestamp_ms": 60,
                    "weight_g": 0.4,
                    "stable": True,
                    "tare_g": 0,
                    "status": "ok",
                }
            ),
            *_stable(100.0, 8),
        ]
    )
    repository = SqliteRepository(tmp_path / "scale.db")
    asyncio.run(
        serve_open_port(port, repository, session_id="banana-live", timestamp=DEMO_TIMESTAMP)
    )
    sent = [json.loads(line.decode("utf-8")) for line in port.outgoing]
    assert vision.paths == [str(tmp_path / "first.jpg"), str(tmp_path / "second.jpg")]
    assert [(item["weight_g"], item["price"]) for item in sent] == [(200.0, 2.4), (100.0, 1.2)]
    first = repository.get_session("banana-live")
    second = repository.get_session("banana-live-2")
    assert first is not None and second is not None
    assert first.image_path == str(tmp_path / "first.jpg")
    assert second.image_path == str(tmp_path / "second.jpg")
    assert first.portion_kcal == 182.0
    assert second.portion_kcal == 91.0
