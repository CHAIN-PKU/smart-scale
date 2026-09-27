import asyncio
import json

from scale_host.serial_replay import BANANA_LINES, ScriptedPort
from scale_host.serial_reply import SERIAL_REPLY_SESSION_ID, main, price_scripted_replies
from scale_host.storage import SqliteRepository


def test_scripted_weight_is_priced_from_the_text_reply(tmp_path) -> None:
    port = ScriptedPort(BANANA_LINES)
    repository = SqliteRepository(tmp_path / "scale.db")
    stored, display_price = asyncio.run(price_scripted_replies(port, repository))
    sent = json.loads(port.outgoing[-1].decode("utf-8"))
    assert "999" not in port.outgoing[-1].decode("utf-8")
    assert sent["type"] == "display_result"
    assert sent["product"] == "banana"
    assert sent["weight_g"] == 326.4
    assert sent["price"] == 3.92
    assert stored.id == SERIAL_REPLY_SESSION_ID
    assert stored.amount_yuan == display_price == 3.92


def test_serial_reply_command_opens_no_port(capsys, monkeypatch) -> None:
    def _blocked(*_args, **_kwargs):
        raise AssertionError("network opened")

    def _com_opened(*_args, **_kwargs):
        raise AssertionError("com opened")

    monkeypatch.setattr("urllib.request.urlopen", _blocked)
    monkeypatch.setattr("serial.Serial", _com_opened)
    main()
    assert capsys.readouterr().out.splitlines() == [
        "weight_g: 326.4",
        "display_price: 3.92",
        f"stored: {SERIAL_REPLY_SESSION_ID}",
        "same_amount: yes",
        "sent_to_internet: no",
    ]
