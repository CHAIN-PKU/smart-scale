import asyncio
import json

from scale_host.place_and_remove import PLACE_AND_REMOVE_LINES, main, price_once_then_stop
from scale_host.serial_replay import ScriptedPort


def test_one_display_then_silence_after_removal() -> None:
    port = ScriptedPort(PLACE_AND_REMOVE_LINES)
    displays, price, saw_removed = asyncio.run(price_once_then_stop(port))
    sent = json.loads(port.outgoing[0].decode("utf-8"))
    assert displays == 1
    assert saw_removed is True
    assert "999" not in port.outgoing[0].decode("utf-8")
    assert sent["type"] == "display_result"
    assert sent["product"] == "banana"
    assert sent["weight_g"] == 326.4
    assert sent["price"] == price == 3.92


def test_place_and_remove_command_stays_offline(capsys, monkeypatch) -> None:
    def _blocked(*_args, **_kwargs):
        raise AssertionError("network opened")

    def _com_opened(*_args, **_kwargs):
        raise AssertionError("com opened")

    monkeypatch.setattr("urllib.request.urlopen", _blocked)
    monkeypatch.setattr("serial.Serial", _com_opened)
    main()
    assert capsys.readouterr().out.splitlines() == [
        "displays: 1",
        "display_price: 3.92",
        "after_remove: no",
        "sent_to_internet: no",
    ]
