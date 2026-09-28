import asyncio
import json
import tempfile
from pathlib import Path

from scale_host.extra_field import EXTRA_FIELD_SESSION_ID, NOTED_STABLE, main
from scale_host.serial_replay import ScriptedPort
from scale_host.serial_reply import price_scripted_replies
from scale_host.storage import SqliteRepository


def test_extra_field_is_not_copied_into_the_display() -> None:
    port = ScriptedPort(NOTED_STABLE)
    with tempfile.TemporaryDirectory() as folder:
        repository = SqliteRepository(Path(folder) / "scale.db")
        stored, display_price, _skipped = asyncio.run(
            price_scripted_replies(port, repository, session_id=EXTRA_FIELD_SESSION_ID)
        )
    raw = port.outgoing[-1].decode("utf-8")
    sent = json.loads(raw)
    assert "ignore-me" not in raw
    assert "note" not in sent
    assert sent["product"] == "banana"
    assert sent["weight_g"] == 326.4
    assert sent["price"] == display_price == stored.amount_yuan == 3.92


def test_extra_field_command_stays_offline(capsys, monkeypatch) -> None:
    def _blocked(*_args, **_kwargs):
        raise AssertionError("network opened")

    def _com_opened(*_args, **_kwargs):
        raise AssertionError("com opened")

    monkeypatch.setattr("urllib.request.urlopen", _blocked)
    monkeypatch.setattr("serial.Serial", _com_opened)
    main()
    text = capsys.readouterr().out
    assert "ignore-me" not in text
    assert text.splitlines() == [
        "extra_field: ignored",
        "weight_g: 326.4",
        "display_price: 3.92",
        "note_in_display: no",
        "sent_to_internet: no",
    ]
