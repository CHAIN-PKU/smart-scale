import asyncio

from scale_host.removed_guard import REMOVED_LINES, main, refusal_reason
from scale_host.serial_replay import ScriptedPort


def test_removed_item_writes_no_display_line() -> None:
    port = ScriptedPort(REMOVED_LINES)
    assert asyncio.run(refusal_reason(port)) == "removed"
    assert port.outgoing == []


def test_removed_command_stays_offline(capsys, monkeypatch) -> None:
    def _blocked(*_args, **_kwargs):
        raise AssertionError("network opened")

    def _com_opened(*_args, **_kwargs):
        raise AssertionError("com opened")

    def _priced(*_args, **_kwargs):
        raise AssertionError("priced a removed item")

    monkeypatch.setattr("urllib.request.urlopen", _blocked)
    monkeypatch.setattr("serial.Serial", _com_opened)
    monkeypatch.setattr("scale_host.reply_sale.sale_from_replies", _priced)
    main()
    assert capsys.readouterr().out.splitlines() == [
        "priced: no",
        "reason: removed",
        "display_sent: no",
        "sent_to_internet: no",
    ]
