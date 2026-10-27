import pytest

from scale_host.catalog import build_product_info


def test_banana_comes_from_the_table_without_a_photo() -> None:
    info = build_product_info("table").lookup("banana")
    assert info.label == "banana"
    assert info.price_per_kg == 12.0
    assert info.kcal_per_100g == 91.0
    assert info.carb_per_100g == 22.0
    assert info.fiber_per_100g == 1.2
    assert info.source == "table"


def test_chinese_banana_uses_the_same_row() -> None:
    info = build_product_info("table").lookup("香蕉")
    assert info.label == "banana"
    assert info.price_per_kg == 12.0
    assert info.kcal_per_100g == 91.0
    assert info.carb_per_100g == 22.0
    assert info.fiber_per_100g == 1.2


def test_common_fruits_use_the_composition_table() -> None:
    table = build_product_info("table")
    expected = {
        "apple": (10.0, 52.0, 13.5, 1.2),
        "orange": (8.0, 47.0, 11.1, 0.6),
        "mandarin": (8.0, 51.0, 11.9, 0.4),
        "pear": (6.0, 44.0, 13.3, 3.1),
        "grape": (16.0, 43.0, 10.3, 0.4),
        "watermelon": (3.0, 25.0, 5.8, 0.3),
        "strawberry": (20.0, 30.0, 7.1, 1.1),
        "peach": (10.0, 48.0, 12.2, 1.3),
        "kiwi": (12.0, 56.0, 14.5, 2.6),
        "pineapple": (8.0, 41.0, 10.8, 1.3),
        "cantaloupe": (6.0, 34.0, 7.9, 0.2),
    }
    aliases = {
        "苹果": "apple",
        "橙子": "orange",
        "橙": "orange",
        "橘子": "mandarin",
        "柑橘": "mandarin",
        "梨": "pear",
        "葡萄": "grape",
        "西瓜": "watermelon",
        "草莓": "strawberry",
        "桃子": "peach",
        "桃": "peach",
        "猕猴桃": "kiwi",
        "奇异果": "kiwi",
        "菠萝": "pineapple",
        "凤梨": "pineapple",
        "哈密瓜": "cantaloupe",
    }
    for label, numbers in expected.items():
        info = table.lookup(label)
        assert info.label == label
        assert (info.price_per_kg, info.kcal_per_100g, info.carb_per_100g, info.fiber_per_100g) == numbers
    for alias, label in aliases.items():
        assert table.lookup(alias).label == label


def test_kiwi_is_not_priced_as_a_peach() -> None:
    assert build_product_info("table").lookup("猕猴桃").label == "kiwi"


def test_unknown_food_is_not_priced() -> None:
    with pytest.raises(KeyError):
        build_product_info("table").lookup("dragonfruit")


def test_table_lookup_does_not_open_the_network(monkeypatch) -> None:
    def _opened(*_args, **_kwargs):
        raise AssertionError("network opened")

    monkeypatch.setattr("urllib.request.urlopen", _opened)
    build_product_info("table").lookup("banana")
