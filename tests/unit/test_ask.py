from scale_host.ask import answer, main
from scale_host.storage import WeighingSession


def test_banana_price_comes_from_the_table(monkeypatch) -> None:
    def _opened(*_args, **_kwargs):
        raise AssertionError("network opened")

    monkeypatch.setattr("urllib.request.urlopen", _opened)
    assert answer("香蕉多少钱") == "香蕉：每千克 12 元，每 100 克 91 千卡，碳水 22 克。"


def test_grams_use_the_table_without_a_scale(monkeypatch) -> None:
    def _opened(*_args, **_kwargs):
        raise AssertionError("network opened")

    monkeypatch.setattr("urllib.request.urlopen", _opened)
    assert answer("326.4克香蕉多少钱") == "326.4 克香蕉：3.92 元，297 千卡，碳水 71.8 克。"


def test_latest_weighing_comes_from_the_saved_record() -> None:
    session = WeighingSession(
        id="banana-fcad6035",
        timestamp="2026-10-13T21:07:00",
        weight_g=220.3,
        label="banana",
        amount_yuan=2.64,
    )
    assert answer("上次称了多少", [session]) == "最近一次：banana，220.3 克，2.64 元。"


def test_unknown_name_is_not_priced() -> None:
    assert answer("苹果多少钱") == "短表里没有这个名字，不出价。"


def test_ask_command_stays_offline(capsys, monkeypatch) -> None:
    def _opened(*_args, **_kwargs):
        raise AssertionError("network opened")

    monkeypatch.setattr("urllib.request.urlopen", _opened)
    monkeypatch.setattr("sys.argv", ["ask", "香蕉多少钱"])
    main()
    assert capsys.readouterr().out.splitlines() == [
        "香蕉：每千克 12 元，每 100 克 91 千卡，碳水 22 克。",
        "sent_to_internet: no",
    ]
