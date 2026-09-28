import asyncio
import json

from scale_host.boot_tare import BOOT_TARE_LINES, main, tare_while_booting
from scale_host.domain import ScaleStatus
from scale_host.serial_replay import ScriptedPort


def test_boot_rejects_tare_and_keeps_a_zero_offset() -> None:
    port = ScriptedPort(BOOT_TARE_LINES)
    ack, reading = asyncio.run(tare_while_booting(port))
    sent = json.loads(port.outgoing[0].decode("utf-8"))
    assert sent == {"v": 1, "type": "command", "command": "tare"}
    assert len(port.outgoing) == 1
    assert ack == "error"
    assert reading.state is ScaleStatus.BOOT
    assert reading.stable is False
    assert reading.tare_g == 0


def test_boot_tare_command_stays_offline(capsys, monkeypatch) -> None:
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
        "state: BOOT",
        "tare_g: 0.0",
        "display_sent: no",
        "sent_to_internet: no",
    ]
