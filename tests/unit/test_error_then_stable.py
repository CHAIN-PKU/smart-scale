import asyncio
import json
import tempfile
from pathlib import Path

from scale_host.error_then_stable import AFTER_ERROR_SESSION_ID, ERROR_THEN_STABLE, main
from scale_host.serial_replay import ScriptedPort
from scale_host.serial_reply import price_scripted_replies
from scale_host.storage import SqliteRepository


def test_error_is_skipped_and_the_next_stable_weight_is_priced() -> None:
    port = ScriptedPort(ERROR_THEN_STABLE)
    with tempfile.TemporaryDirectory() as folder:
        repository = SqliteRepository(Path(folder) / "scale.db")
        stored, display_price, skipped = asyncio.run(
            price_scripted_replies(port, repository, session_id=AFTER_ERROR_SESSION_ID)
        )
    sent = json.loads(port.outgoing[-1].decode("utf-8"))
    assert skipped == 1
    assert len(port.outgoing) == 1
    assert "hx711" not in port.outgoing[-1].decode("utf-8")
    assert sent["product"] == "banana"
    assert sent["weight_g"] == 326.4
    assert sent["price"] == display_price == stored.amount_yuan == 3.92


def test_error_then_stable_command_stays_offline(capsys, monkeypatch) -> None:
    def _blocked(*_args, **_kwargs):
        raise AssertionError("network opened")

    def _com_opened(*_args, **_kwargs):
        raise AssertionError("com opened")

    monkeypatch.setattr("urllib.request.urlopen", _blocked)
    monkeypatch.setattr("serial.Serial", _com_opened)
    main()
    assert capsys.readouterr().out.splitlines() == [
        "skipped: 1",
        "weight_g: 326.4",
        "display_price: 3.92",
        f"stored: {AFTER_ERROR_SESSION_ID}",
        "sent_to_internet: no",
    ]
