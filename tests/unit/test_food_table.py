import pytest

from scale_host.catalog import build_product_info


def test_banana_comes_from_the_table_without_a_photo() -> None:
    info = build_product_info("table").lookup("banana")
    assert info.label == "banana"
    assert info.price_per_kg == 12.0
    assert info.kcal_per_100g == 91.0
    assert info.carb_per_100g == 22.0
    assert info.source == "table"


def test_chinese_banana_uses_the_same_row() -> None:
    info = build_product_info("table").lookup("香蕉")
    assert info.price_per_kg == 12.0
    assert info.kcal_per_100g == 91.0
    assert info.carb_per_100g == 22.0


def test_unknown_food_is_not_priced() -> None:
    with pytest.raises(KeyError):
        build_product_info("table").lookup("dragonfruit")


def test_table_lookup_does_not_open_the_network(monkeypatch) -> None:
    def _opened(*_args, **_kwargs):
        raise AssertionError("network opened")

    monkeypatch.setattr("urllib.request.urlopen", _opened)
    build_product_info("table").lookup("banana")
