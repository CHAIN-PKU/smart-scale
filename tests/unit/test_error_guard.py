import asyncio

from scale_host.error_guard import ERROR_LINES, main, refusal_reason
from scale_host.serial_replay import ScriptedPort


def test_sensor_error_writes_no_display_line() -> None:
    port = ScriptedPort(ERROR_LINES)
    assert asyncio.run(refusal_reason(port)) == "error"
    assert port.outgoing == []


def test_error_command_stays_offline(capsys, monkeypatch) -> None:
    def _blocked(*_args, **_kwargs):
        raise AssertionError("network opened")

    def _com_opened(*_args, **_kwargs):
        raise AssertionError("com opened")

    def _priced(*_args, **_kwargs):
        raise AssertionError("priced a sensor error")

    monkeypatch.setattr("urllib.request.urlopen", _blocked)
    monkeypatch.setattr("serial.Serial", _com_opened)
    monkeypatch.setattr("scale_host.reply_sale.sale_from_replies", _priced)
    main()
    assert capsys.readouterr().out.splitlines() == [
        "priced: no",
        "reason: error",
        "display_sent: no",
        "sent_to_internet: no",
    ]
