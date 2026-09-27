import pytest

from scale_host.domain import ScaleStatus, WeightReading
from scale_host.fusion import fuse, yuan_amount
from scale_host.quote import ItemQuote
from scale_host.sale import main


def _quote() -> ItemQuote:
    return ItemQuote(
        label="banana",
        confidence=0.91,
        price_per_kg=12.0,
        summary="test price",
        vision_source="mock",
        info_source="mock",
        image_path="banana.jpg",
    )


def _reading(**overrides: object) -> WeightReading:
    values = {
        "seq": 1,
        "timestamp_ms": 1000,
        "weight_g": 326.4,
        "stable": True,
        "tare_g": 0.0,
        "status": "ok",
        "state": ScaleStatus.WEIGHT_STABLE,
    }
    values.update(overrides)
    return WeightReading(**values)


def test_stable_banana_costs_three_yuan_ninety_two_fen() -> None:
    sale = fuse(_reading(), _quote())
    assert sale.label == "banana"
    assert sale.weight_g == 326.4
    assert sale.price_per_kg == 12.0
    assert sale.amount_yuan == 3.92


def test_amount_rounds_half_up_to_fen() -> None:
    assert yuan_amount(333.3, 3.0) == 1.00


def test_unstable_weight_is_not_priced() -> None:
    reading = _reading(stable=False, state=ScaleStatus.WEIGHT_CHANGED, weight_g=145.0)
    with pytest.raises(RuntimeError, match="not ready"):
        fuse(reading, _quote())


def test_overload_is_not_priced() -> None:
    reading = _reading(status="overload", state=ScaleStatus.OVERLOAD, weight_g=1200.0)
    with pytest.raises(RuntimeError, match="not ready"):
        fuse(reading, _quote())


def test_sale_command_prints_the_banana_amount(capsys, monkeypatch) -> None:
    monkeypatch.setenv("VISION_PROVIDER", "mock")
    monkeypatch.setenv("PRODUCT_INFO_PROVIDER", "mock")
    main()
    assert capsys.readouterr().out.splitlines() == [
        "label: banana",
        "weight_g: 326.4",
        "price_per_kg: 12.0",
        "amount_yuan: 3.92",
    ]
