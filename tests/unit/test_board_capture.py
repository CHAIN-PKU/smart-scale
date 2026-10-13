import asyncio

from scale_host.board_capture import CAPTURED_PLACE_LINES, DRIFT_LINES, main, replay_placement
from scale_host.serial_replay import ScriptedPort


def test_captured_placement_is_priced_once(monkeypatch) -> None:
    def _opened(*_args, **_kwargs):
        raise AssertionError("network opened")

    def _com_opened(*_args, **_kwargs):
        raise AssertionError("com opened")

    monkeypatch.setattr("urllib.request.urlopen", _opened)
    monkeypatch.setattr("serial.Serial", _com_opened)
    port = ScriptedPort(CAPTURED_PLACE_LINES + DRIFT_LINES)
    sale = asyncio.run(replay_placement(port))
    assert sale is not None
    assert sale.label == "banana"
    assert sale.weight_g == 221.1
    assert sale.amount_yuan == 2.65
    assert sale.portion_kcal == 201.2
    assert sale.portion_carb_g == 48.6
    assert len(port.outgoing) == 1


def test_board_capture_command_stays_offline(capsys, monkeypatch) -> None:
    def _opened(*_args, **_kwargs):
        raise AssertionError("network opened")

    def _com_opened(*_args, **_kwargs):
        raise AssertionError("com opened")

    monkeypatch.setattr("urllib.request.urlopen", _opened)
    monkeypatch.setattr("serial.Serial", _com_opened)
    main()
    assert capsys.readouterr().out.splitlines() == [
        "label: banana",
        "weight_g: 221.1",
        "amount_yuan: 2.65",
        "portion_kcal: 201.2",
        "portion_carb_g: 48.6",
        "displays: 1",
        "sent_to_internet: no",
    ]
