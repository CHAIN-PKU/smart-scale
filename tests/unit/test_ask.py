from scale_host.ask import answer, main
from scale_host.storage import WeighingSession


def test_banana_price_comes_from_the_table(monkeypatch) -> None:
    def _opened(*_args, **_kwargs):
        raise AssertionError("network opened")

    monkeypatch.setattr("urllib.request.urlopen", _opened)
    assert answer("香蕉多少钱") == "香蕉：每千克 12 元，每 100 克 91 千卡，碳水 22 克，膳食纤维 1.2 克。"


def test_grams_use_the_table_without_a_scale(monkeypatch) -> None:
    def _opened(*_args, **_kwargs):
        raise AssertionError("network opened")

    monkeypatch.setattr("urllib.request.urlopen", _opened)
    assert answer("326.4克香蕉多少钱") == "326.4 克香蕉：3.92 元，297 千卡，碳水 71.8 克，膳食纤维 3.9 克。"


def test_latest_weighing_comes_from_the_saved_record() -> None:
    session = WeighingSession(
        id="banana-fcad6035",
        timestamp="2026-10-13T21:07:00",
        weight_g=220.3,
        label="banana",
        amount_yuan=2.64,
    )
    assert answer("上次称了多少", [session]) == (
        "最近一次：banana，220.3 克，2.64 元，200.5 千卡，碳水 48.5 克，膳食纤维 2.6 克。"
    )


def test_saved_nutrition_is_repeated_as_stored() -> None:
    session = WeighingSession(
        id="banana-3264",
        timestamp="2026-10-20T12:00:00",
        weight_g=326.4,
        label="banana",
        amount_yuan=3.92,
        portion_kcal=297.0,
        portion_carb_g=71.8,
    )
    assert answer("上次称了多少", [session]) == (
        "最近一次：banana，326.4 克，3.92 元，297 千卡，碳水 71.8 克，膳食纤维 3.9 克。"
    )


def test_unknown_history_has_no_invented_nutrition() -> None:
    session = WeighingSession(
        id="other-1",
        timestamp="2026-10-20T12:00:00",
        weight_g=100.0,
        label="apple",
        amount_yuan=1.50,
    )
    assert answer("上次称了多少", [session]) == "最近一次：apple，100 克，1.50 元。"


def test_screen_question_uses_the_latest_sale() -> None:
    session = WeighingSession(
        id="banana-3264",
        timestamp="2026-10-27T16:40:00",
        weight_g=326.4,
        label="banana",
        amount_yuan=3.92,
        portion_kcal=297.0,
        portion_carb_g=71.8,
    )
    assert answer("屏幕上是什么", [session]) == (
        "香蕉、每千克12元、326.4克、3.92元、297千卡、碳水71.8克、膳食纤维3.9克"
    )
    assert answer("屏幕上是什么", []) == "屏幕上还没有结果。"


def test_screen_question_uses_the_table_name_and_keeps_stored_nutrition() -> None:
    session = WeighingSession(
        id="other-1",
        timestamp="2026-10-20T12:00:00",
        weight_g=100.0,
        label="apple",
        amount_yuan=1.50,
        portion_kcal=52.0,
        portion_carb_g=14.0,
    )
    assert answer("屏幕上是什么", [session]) == "苹果、100克、1.50元、52千卡、碳水14克"


def test_apple_price_comes_from_the_table() -> None:
    assert answer("苹果多少钱") == (
        "苹果：每千克 10 元，每 100 克 52 千卡，碳水 13.5 克，膳食纤维 1.2 克。"
    )
    assert answer("100克橙子") == "100 克橙子：0.80 元，47 千卡，碳水 11.1 克，膳食纤维 0.6 克。"


def test_unknown_name_is_not_priced() -> None:
    assert answer("火龙果多少钱") == "短表里没有这个名字，不出价。"


def test_ask_command_stays_offline(capsys, monkeypatch) -> None:
    def _opened(*_args, **_kwargs):
        raise AssertionError("network opened")

    monkeypatch.setattr("urllib.request.urlopen", _opened)
    monkeypatch.setattr("sys.argv", ["ask", "香蕉多少钱"])
    main()
    assert capsys.readouterr().out.splitlines() == [
        "香蕉：每千克 12 元，每 100 克 91 千卡，碳水 22 克，膳食纤维 1.2 克。",
        "sent_to_internet: no",
    ]
