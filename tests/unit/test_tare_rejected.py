import asyncio
import json

from scale_host.domain import ScaleStatus
from scale_host.serial_replay import ScriptedPort
from scale_host.tare_rejected import OVERLOAD_TARE_LINES, main, tare_while_overloaded


def test_overload_rejects_tare_and_keeps_the_offset() -> None:
    port = ScriptedPort(OVERLOAD_TARE_LINES)
    ack, reading = asyncio.run(tare_while_overloaded(port))
    sent = json.loads(port.outgoing[0].decode("utf-8"))
    assert sent == {"v": 1, "type": "command", "command": "tare"}
    assert len(port.outgoing) == 1
    assert ack == "error"
    assert reading.state is ScaleStatus.OVERLOAD
    assert reading.weight_g == 1
    assert reading.tare_g == 12.7
    assert reading.status == "overload"


def test_rejected_tare_command_stays_offline(capsys, monkeypatch) -> None:
    def _blocked(*_args, **_kwargs):
        raise AssertionError("network opened")

    def _com_opened(*_args, **_kwargs):
        raise AssertionError("com opened")

    monkeypatch.setattr("urllib.request.urlopen", _blocked)
    monkeypatch.setattr("serial.Serial", _com_opened)
    main()
    assert capsys.readouterr().out.splitlines() == [
        "command: tare",
        "ack: error",
        "state: OVERLOAD",
        "weight_g: 1.0",
        "tare_g: 12.7",
        "display_sent: no",
        "sent_to_internet: no",
    ]
