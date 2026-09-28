import asyncio
import json
import tempfile
from pathlib import Path

from scale_host.bad_line import BAD_LINE_SESSION_ID, BAD_THEN_STABLE, main
from scale_host.serial_replay import ScriptedPort
from scale_host.serial_reply import price_scripted_replies
from scale_host.storage import SqliteRepository


def test_bad_line_is_dropped_and_the_stable_weight_is_priced() -> None:
    port = ScriptedPort(BAD_THEN_STABLE)
    with tempfile.TemporaryDirectory() as folder:
        repository = SqliteRepository(Path(folder) / "scale.db")
        stored, display_price, skipped = asyncio.run(
            price_scripted_replies(port, repository, session_id=BAD_LINE_SESSION_ID)
        )
    sent = json.loads(port.outgoing[-1].decode("utf-8"))
    assert b"123.45" not in port.outgoing[-1]
    assert skipped == 0
    assert len(port.outgoing) == 1
    assert sent["product"] == "banana"
    assert sent["weight_g"] == 326.4
    assert sent["price"] == display_price == stored.amount_yuan == 3.92


def test_bad_line_command_stays_offline(capsys, monkeypatch) -> None:
    def _blocked(*_args, **_kwargs):
        raise AssertionError("network opened")

    def _com_opened(*_args, **_kwargs):
        raise AssertionError("com opened")

    monkeypatch.setattr("urllib.request.urlopen", _blocked)
    monkeypatch.setattr("serial.Serial", _com_opened)
    main()
    text = capsys.readouterr().out
    assert "123.45" not in text
    assert text.splitlines() == [
        "bad_line: dropped",
        "weight_g: 326.4",
        "display_price: 3.92",
        f"stored: {BAD_LINE_SESSION_ID}",
        "sent_to_internet: no",
    ]
