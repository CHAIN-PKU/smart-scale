import asyncio
import json

from scale_host.domain import ScaleStatus
from scale_host.serial_replay import ScriptedPort
from scale_host.tare_roundtrip import TARE_LINES, main, tare_then_zero


def test_tare_is_acked_and_the_next_weight_is_zero() -> None:
    port = ScriptedPort(TARE_LINES)
    ack, reading = asyncio.run(tare_then_zero(port))
    sent = json.loads(port.outgoing[0].decode("utf-8"))
    assert sent == {"v": 1, "type": "command", "command": "tare"}
    assert len(port.outgoing) == 1
    assert ack == "ok"
    assert reading.state is ScaleStatus.ZERO
    assert reading.weight_g == 0
    assert reading.tare_g == 12.7
    assert reading.stable is True


def test_tare_command_stays_offline(capsys, monkeypatch) -> None:
    def _blocked(*_args, **_kwargs):
        raise AssertionError("network opened")

    def _com_opened(*_args, **_kwargs):
        raise AssertionError("com opened")

    monkeypatch.setattr("urllib.request.urlopen", _blocked)
    monkeypatch.setattr("serial.Serial", _com_opened)
    main()
    assert capsys.readouterr().out.splitlines() == [
        "command: tare",
        "ack: ok",
        "next_state: ZERO",
        "weight_g: 0.0",
        "tare_g: 12.7",
        "display_sent: no",
        "sent_to_internet: no",
    ]
