"""Records and receipt answers. No COM port and no network."""

import asyncio
import json

from scale_host.pipeline import serve_open_port
from scale_host.remote_query import receipt_payload, records_payload, reply_line, wifi_page
from scale_host.serial_replay import ScriptedPort
from scale_host.storage import SqliteRepository, WeighingSession


def _repository(tmp_path) -> SqliteRepository:
    repository = SqliteRepository(tmp_path / "scale.db")
    repository.save_session(
        WeighingSession(
            id="banana-1",
            timestamp="2026-10-27T21:00:00",
            weight_g=221.4,
            label="banana",
            price_per_kg=12.0,
            amount_yuan=2.66,
            portion_kcal=201.5,
            portion_carb_g=48.7,
            portion_fiber_g=2.7,
        )
    )
    repository.replace_receipt_lines([("banana", 221.4, 2.66, 12.0)])
    return repository


def test_records_use_the_saved_weighing(tmp_path) -> None:
    payload = records_payload(_repository(tmp_path))
    assert payload["type"] == "records_result"
    assert payload["items"][0]["name"] == "香蕉"
    assert payload["items"][0]["weight_g"] == 221.4
    assert payload["items"][0]["price"] == 2.66


def test_receipt_is_the_saved_list(tmp_path) -> None:
    payload = receipt_payload(_repository(tmp_path))
    assert payload["type"] == "receipt_result"
    assert payload["total"] == 2.66
    assert payload["items"][0]["product"] == "banana"


def test_plain_lines_answer_records_and_receipt(tmp_path) -> None:
    repository = _repository(tmp_path)
    records = json.loads(reply_line(repository, "记录\r\n"))
    receipt = json.loads(reply_line(repository, '{"v":1,"type":"query","query":"receipt"}'))
    assert records["items"][0]["product"] == "banana"
    assert receipt["total"] == 2.66


def test_wifi_page_is_one_short_line(tmp_path) -> None:
    page = wifi_page(_repository(tmp_path), "记录")
    assert page["type"] == "wifi_page"
    assert "香蕉|221.4|2.66" in page["text"]
    assert '"' not in page["text"]
    assert len(page["text"]) < 400


def test_scale_port_answers_a_query_without_a_new_weighing(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("serial.Serial", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("serial")))
    repository = _repository(tmp_path)
    port = ScriptedPort([b'{"v":1,"type":"query","query":"records"}\n'])
    asyncio.run(
        serve_open_port(
            port,
            repository,
            session_id="banana-1",
            timestamp="2026-10-27T21:00:00",
        )
    )
    sent = [json.loads(line.decode("utf-8")) for line in port.outgoing]
    assert sent[0]["type"] == "wifi_page"
    assert "香蕉|" in sent[0]["text"]


def test_unknown_and_blank_lines_do_not_invent_a_list(tmp_path) -> None:
    repository = _repository(tmp_path)
    assert reply_line(repository, "") is None
    assert reply_line(repository, "AT+NAME?") is None
    error = json.loads(reply_line(repository, '{"v":1,"type":"query","query":"reboot"}'))
    assert error == {"v": 1, "type": "query_result", "status": "error"}
