"""A placement with no food or an unknown name is not priced. No COM port."""

import asyncio
import json

import pytest

from scale_host.pipeline import DEMO_TIMESTAMP, identify_and_price, serve_open_port
from scale_host.serial_replay import ScriptedPort
from scale_host.storage import SqliteRepository


def _block(monkeypatch, tmp_path) -> None:
    photo = tmp_path / "placement.jpg"
    photo.write_bytes(b"jpg")
    monkeypatch.setenv("SCALE_FRAME", str(photo))
    def _opened(*_args, **_kwargs):
        raise AssertionError("network opened")

    monkeypatch.setenv("VISION_PROVIDER", "mock")
    monkeypatch.setenv("PRODUCT_INFO_PROVIDER", "table")
    monkeypatch.setattr("urllib.request.urlopen", _opened)
    monkeypatch.setattr("serial.Serial", _opened)


def _line(payload: dict) -> bytes:
    return (json.dumps(payload, separators=(",", ":")) + "\n").encode()


def _stable(weight_g: float, seq: int = 2) -> list[bytes]:
    return [
        _line({"v": 1, "type": "status", "seq": seq - 1, "timestamp_ms": 10, "state": "WEIGHT_STABLE"}),
        _line(
            {
                "v": 1,
                "type": "weight",
                "seq": seq,
                "timestamp_ms": 20,
                "weight_g": weight_g,
                "stable": True,
                "tare_g": 0,
                "status": "ok",
            }
        ),
    ]


def _command(name: str) -> bytes:
    return _line({"v": 1, "type": "command", "command": name})


def _messages(port: ScriptedPort) -> list[dict]:
    return [json.loads(line.decode("utf-8")) for line in port.outgoing]


def test_no_food_sends_nothing_and_save_fails(tmp_path, monkeypatch) -> None:
    _block(monkeypatch, tmp_path)
    calls = {"n": 0}

    def _refuse(*_args, **_kwargs):
        calls["n"] += 1
        raise RuntimeError("no unit price for no food visible in this image")

    monkeypatch.setattr("scale_host.pipeline.identify_and_price", _refuse)
    port = ScriptedPort(
        [
            *_stable(100.0),
            _line(
                {
                    "v": 1,
                    "type": "weight",
                    "seq": 3,
                    "timestamp_ms": 30,
                    "weight_g": 100.2,
                    "stable": True,
                    "tare_g": 0,
                    "status": "ok",
                }
            ),
            _command("save"),
            _command("receipt"),
        ]
    )
    with pytest.raises(RuntimeError, match="no stable weight"):
        asyncio.run(
            serve_open_port(
                port,
                SqliteRepository(tmp_path / "scale.db"),
                session_id="none",
                timestamp=DEMO_TIMESTAMP,
            )
        )
    sent = _messages(port)
    assert calls["n"] == 1
    assert [item["type"] for item in sent] == ["ack", "receipt_result"]
    assert sent[0]["command"] == "save" and sent[0]["status"] == "error"
    assert sent[1]["items"] == []
    assert sent[1]["total"] == 0.0


def test_unknown_name_does_not_replace_a_saved_line(tmp_path, monkeypatch) -> None:
    _block(monkeypatch, tmp_path)
    real = identify_and_price
    calls = {"n": 0}

    def _then_unknown(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return real(*args, **kwargs)
        raise RuntimeError("no unit price for dragonfruit")

    monkeypatch.setattr("scale_host.pipeline.identify_and_price", _then_unknown)
    repository = SqliteRepository(tmp_path / "scale.db")
    port = ScriptedPort(
        [
            *_stable(326.4, seq=2),
            _command("save"),
            _line({"v": 1, "type": "status", "seq": 8, "timestamp_ms": 80, "state": "WEIGHT_REMOVED"}),
            _line(
                {
                    "v": 1,
                    "type": "weight",
                    "seq": 9,
                    "timestamp_ms": 90,
                    "weight_g": 0.4,
                    "stable": True,
                    "tare_g": 0,
                    "status": "ok",
                }
            ),
            *_stable(180.0, seq=11),
            _command("save"),
            _command("receipt"),
        ]
    )
    asyncio.run(
        serve_open_port(
            port,
            repository,
            session_id="banana-kept",
            timestamp=DEMO_TIMESTAMP,
        )
    )
    sent = _messages(port)
    assert [item["type"] for item in sent] == ["display_result", "ack", "ack", "receipt_result"]
    assert sent[1]["status"] == "ok"
    assert sent[2]["status"] == "error"
    assert sent[3]["items"] == [
        {"n": 1, "product": "banana", "price_per_kg": 12.0, "weight_g": 326.4, "price": 3.92}
    ]
    assert repository.list_receipt_lines() == [("banana", 326.4, 3.92, 12.0)]
