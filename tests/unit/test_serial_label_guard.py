import asyncio

from scale_host.serial_label_guard import main, stable_weight_with_mismatch
from scale_host.serial_replay import BANANA_LINES, ScriptedPort


def test_stable_serial_weight_is_not_displayed() -> None:
    port = ScriptedPort(BANANA_LINES)
    weight_g, mismatch = asyncio.run(stable_weight_with_mismatch(port))
    assert weight_g == 326.4
    assert mismatch.vision_label == "banana"
    assert mismatch.text_label == "apple"
    assert port.outgoing == []


def test_serial_label_guard_stays_offline(capsys, monkeypatch) -> None:
    def _blocked(*_args, **_kwargs):
        raise AssertionError("network opened")

    def _com_opened(*_args, **_kwargs):
        raise AssertionError("com opened")

    monkeypatch.setattr("urllib.request.urlopen", _blocked)
    monkeypatch.setattr("serial.Serial", _com_opened)
    main()
    text = capsys.readouterr().out
    assert "8.0" not in text
    assert "999" not in text
    assert "3.92" not in text
    assert text.splitlines() == [
        "weight_g: 326.4",
        "priced: no",
        "reason: label mismatch",
        "vision_label: banana",
        "text_label: apple",
        "display_sent: no",
        "sent_to_internet: no",
    ]
