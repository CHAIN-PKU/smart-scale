"""Receipt commands on a scripted port. No COM port and no network."""

import asyncio
import json

import pytest

from scale_host.pipeline import DEMO_TIMESTAMP, serve_open_port
from scale_host.serial_replay import ScriptedPort
from scale_host.storage import SqliteRepository, WeighingSession


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


def _command(name: str) -> bytes:
    return f'{{"v":1,"type":"command","command":"{name}"}}\n'.encode()


def _stable(weight_g: float) -> list[bytes]:
    status = {"v": 1, "type": "status", "seq": 1, "timestamp_ms": 10, "state": "WEIGHT_STABLE"}
    weight = {
        "v": 1,
        "type": "weight",
        "seq": 2,
        "timestamp_ms": 20,
        "weight_g": weight_g,
        "stable": True,
        "tare_g": 0,
        "status": "ok",
    }
    return [
        (json.dumps(status, separators=(",", ":")) + "\n").encode(),
        (json.dumps(weight, separators=(",", ":")) + "\n").encode(),
    ]


def _messages(port: ScriptedPort) -> list[dict]:
    return [json.loads(line.decode("utf-8")) for line in port.outgoing]


def test_weighing_shows_nutrition_and_does_not_fill_the_receipt(tmp_path, monkeypatch) -> None:
    _block(monkeypatch, tmp_path)
    repository = SqliteRepository(tmp_path / "scale.db")
    repository.save_session(
        WeighingSession(
            id="banana-old",
            timestamp="2026-10-20T00:00:00",
            weight_g=100.0,
            label="banana",
            amount_yuan=1.2,
        )
    )
    port = ScriptedPort(_stable(326.4))
    asyncio.run(
        serve_open_port(
            port,
            repository,
            session_id="banana-now",
            timestamp=DEMO_TIMESTAMP,
        )
    )
    sent = _messages(port)
    assert [item["type"] for item in sent] == ["display_result"]
    assert sent[0]["product"] == "banana"
    assert sent[0]["weight_g"] == 326.4
    assert sent[0]["price"] == 3.92
    assert sent[0]["price_per_kg"] == 12.0
    assert sent[0]["portion_kcal"] == 297.0
    assert sent[0]["portion_carb_g"] == 71.8
    assert sent[0]["portion_fiber_g"] == 3.9
    assert repository.list_receipt_lines() == []
    assert repository.get_session("banana-old") is not None
    assert repository.get_session("banana-now") is not None


def test_save_receipt_and_clear_on_a_fake_port(tmp_path, monkeypatch) -> None:
    _block(monkeypatch, tmp_path)
    repository = SqliteRepository(tmp_path / "scale.db")
    port = ScriptedPort(
        [
            _command("save"),
            *_stable(326.4),
            _command("save"),
            _command("save"),
            _command("receipt"),
            _command("clear"),
            _command("receipt"),
        ]
    )
    asyncio.run(
        serve_open_port(
            port,
            repository,
            session_id="banana-ticket",
            timestamp=DEMO_TIMESTAMP,
        )
    )
    sent = _messages(port)
    assert [item["type"] for item in sent] == [
        "ack",
        "display_result",
        "ack",
        "ack",
        "receipt_result",
        "receipt_result",
        "receipt_result",
    ]
    assert sent[0] == {"v": 1, "type": "ack", "seq": 0, "timestamp_ms": 0, "command": "save", "status": "error"}
    assert sent[2]["command"] == "save" and sent[2]["status"] == "ok"
    assert sent[3]["status"] == "ok"
    assert sent[4]["total"] == 7.84
    assert sent[4]["items"] == [
        {"n": 1, "product": "banana", "price_per_kg": 12.0, "weight_g": 326.4, "price": 3.92},
        {"n": 2, "product": "banana", "price_per_kg": 12.0, "weight_g": 326.4, "price": 3.92},
    ]
    assert sent[5] == {"v": 1, "type": "receipt_result", "items": [], "total": 0.0}
    assert sent[6]["items"] == []
    assert sent[6]["total"] == 0.0
    assert repository.list_receipt_lines() == []


def test_saved_lines_remain_for_the_next_open(tmp_path, monkeypatch) -> None:
    _block(monkeypatch, tmp_path)
    repository = SqliteRepository(tmp_path / "scale.db")
    first = ScriptedPort([*_stable(221.4), _command("save")])
    asyncio.run(
        serve_open_port(
            first,
            repository,
            session_id="banana-keep",
            timestamp=DEMO_TIMESTAMP,
        )
    )
    assert repository.list_receipt_lines() == [("banana", 221.4, 2.66, 12.0)]
    second = ScriptedPort([_command("receipt")])
    with pytest.raises(RuntimeError, match="no stable weight"):
        asyncio.run(
            serve_open_port(
                second,
                repository,
                session_id="banana-again",
                timestamp=DEMO_TIMESTAMP,
            )
        )
    sent = _messages(second)
    assert sent == [
        {
            "v": 1,
            "type": "receipt_result",
            "items": [{"n": 1, "product": "banana", "price_per_kg": 12.0, "weight_g": 221.4, "price": 2.66}],
            "total": 2.66,
        }
    ]
    assert repository.get_session("banana-keep") is not None
    assert repository.list_receipt_lines() == [("banana", 221.4, 2.66, 12.0)]
