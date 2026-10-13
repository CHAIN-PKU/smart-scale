import pytest

from scale_host.catalog import TableProductInfo
from scale_host.domain import ProductRecognition, ScaleStatus, WeightReading
from scale_host.fusion import PlacementPricer, fuse
from scale_host.quote import identify_and_price
from scale_host.vision import MockVision


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


def _banana_quote():
    return identify_and_price("banana.jpg", MockVision(), TableProductInfo())


def test_stable_banana_uses_the_table_standards() -> None:
    sale = fuse(_reading(), _banana_quote())
    assert sale.amount_yuan == 3.92
    assert sale.portion_kcal == 297.0
    assert sale.portion_carb_g == 71.8
    assert sale.info_source == "table"


def test_creep_back_to_stable_does_not_price_again() -> None:
    pricer = PlacementPricer()
    quote = _banana_quote()
    first = pricer.consider(_reading(), quote)
    skipped = pricer.consider(
        _reading(seq=2, weight_g=327.2, stable=False, state=ScaleStatus.WEIGHT_CHANGED),
        quote,
    )
    second = pricer.consider(
        _reading(seq=3, weight_g=327.2, state=ScaleStatus.WEIGHT_STABLE),
        quote,
    )
    assert first is not None
    assert first.amount_yuan == 3.92
    assert skipped is None
    assert second is None


def test_a_new_placement_after_removal_can_be_priced() -> None:
    pricer = PlacementPricer()
    quote = _banana_quote()
    pricer.consider(_reading(), quote)
    pricer.consider(_reading(seq=4, weight_g=0.2, state=ScaleStatus.WEIGHT_REMOVED), quote)
    again = pricer.consider(_reading(seq=5, weight_g=100.0), quote)
    assert again is not None
    assert again.amount_yuan == 1.20
    assert again.portion_kcal == 91.0
    assert again.portion_carb_g == 22.0


class _UnknownFood:
    name = "unknown"

    def recognize(self, image_path: str) -> ProductRecognition:
        return ProductRecognition(
            label="dragonfruit",
            confidence=0.5,
            source="unknown",
            image_id=image_path,
        )


def test_unknown_name_is_not_priced() -> None:
    with pytest.raises(RuntimeError, match="no unit price"):
        identify_and_price("fruit.jpg", _UnknownFood(), TableProductInfo())
