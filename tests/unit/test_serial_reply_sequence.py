import asyncio
import json

from scale_host.serial_replay import ScriptedPort
from scale_host.serial_reply import price_scripted_replies
from scale_host.serial_reply_sequence import SEQUENCE_REPLY_SESSION_ID, main
from scale_host.serial_sequence import rising_lines
from scale_host.storage import SqliteRepository


def test_rising_lines_price_only_the_stable_reply(tmp_path) -> None:
    port = ScriptedPort(rising_lines())
    repository = SqliteRepository(tmp_path / "scale.db")
    stored, display_price, skipped = asyncio.run(
        price_scripted_replies(
            port,
            repository,
            session_id=SEQUENCE_REPLY_SESSION_ID,
        )
    )
    sent = json.loads(port.outgoing[-1].decode("utf-8"))
    assert len(port.outgoing) == 1
    assert "999" not in port.outgoing[-1].decode("utf-8")
    assert skipped == 5
    assert sent["weight_g"] == 326.4
    assert sent["price"] == 3.92
    assert stored.amount_yuan == display_price == 3.92
    assert stored.id == SEQUENCE_REPLY_SESSION_ID


def test_sequence_reply_command_stays_offline(capsys, monkeypatch) -> None:
    def _blocked(*_args, **_kwargs):
        raise AssertionError("network opened")

    def _com_opened(*_args, **_kwargs):
        raise AssertionError("com opened")

    monkeypatch.setattr("urllib.request.urlopen", _blocked)
    monkeypatch.setattr("serial.Serial", _com_opened)
    main()
    assert capsys.readouterr().out.splitlines() == [
        "skipped: 5",
        "weight_g: 326.4",
        "display_price: 3.92",
        f"stored: {SEQUENCE_REPLY_SESSION_ID}",
        "same_amount: yes",
        "sent_to_internet: no",
    ]
