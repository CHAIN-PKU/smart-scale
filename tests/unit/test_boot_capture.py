import asyncio

from scale_host.boot_capture import CAPTURED_BOOT_LINES, main, replay_capture
from scale_host.serial_replay import ScriptedPort


def test_boot_capture_prices_nothing() -> None:
    port = ScriptedPort(CAPTURED_BOOT_LINES)
    assert asyncio.run(replay_capture(port)) == "ERROR"
    assert port.outgoing == []
    assert port.incoming == []


def test_boot_capture_command_stays_offline(capsys, monkeypatch) -> None:
    def _blocked(*_args, **_kwargs):
        raise AssertionError("network opened")

    def _com_opened(*_args, **_kwargs):
        raise AssertionError("com opened")

    def _priced(*_args, **_kwargs):
        raise AssertionError("priced the boot capture")

    monkeypatch.setattr("urllib.request.urlopen", _blocked)
    monkeypatch.setattr("serial.Serial", _com_opened)
    monkeypatch.setattr("scale_host.reply_sale.sale_from_replies", _priced)
    main()
    assert capsys.readouterr().out.splitlines() == [
        "priced: no",
        "state: ERROR",
        "debug_line: dropped",
        "display_sent: no",
        "sent_to_internet: no",
    ]
