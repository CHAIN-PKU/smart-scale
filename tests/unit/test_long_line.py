import asyncio
import json
import tempfile
from pathlib import Path

from scale_host.long_line import LONG_LINE_SESSION_ID, lines, main, overlong_line
from scale_host.serial_replay import ScriptedPort
from scale_host.serial_reply import price_scripted_replies
from scale_host.storage import SqliteRepository


def test_overlong_line_is_dropped_and_the_stable_weight_is_priced() -> None:
    assert len(overlong_line()) > 514
    port = ScriptedPort(lines())
    with tempfile.TemporaryDirectory() as folder:
        repository = SqliteRepository(Path(folder) / "scale.db")
        stored, display_price, _skipped = asyncio.run(
            price_scripted_replies(port, repository, session_id=LONG_LINE_SESSION_ID)
        )
    raw = port.outgoing[-1].decode("utf-8")
    sent = json.loads(raw)
    assert b"xxx" not in port.outgoing[-1]
    assert len(port.outgoing) == 1
    assert sent["product"] == "banana"
    assert sent["weight_g"] == 326.4
    assert sent["price"] == display_price == stored.amount_yuan == 3.92


def test_long_line_command_stays_offline(capsys, monkeypatch) -> None:
    def _blocked(*_args, **_kwargs):
        raise AssertionError("network opened")

    def _com_opened(*_args, **_kwargs):
        raise AssertionError("com opened")

    monkeypatch.setattr("urllib.request.urlopen", _blocked)
    monkeypatch.setattr("serial.Serial", _com_opened)
    main()
    assert capsys.readouterr().out.splitlines() == [
        "long_line: dropped",
        "weight_g: 326.4",
        "display_price: 3.92",
        f"stored: {LONG_LINE_SESSION_ID}",
        "sent_to_internet: no",
    ]
