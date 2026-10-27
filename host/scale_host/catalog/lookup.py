"""Product facts and price. The demo table looks these up by name after recognition."""

from __future__ import annotations

import os
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from scale_host.providers import MissingApiKey, RemoteCallNotReady

_MODEL_CONFIG = ConfigDict(extra="forbid")


class ProductInfo(BaseModel):
    model_config = _MODEL_CONFIG
    label: str = Field(min_length=1)
    price_per_kg: float | None = Field(default=None, ge=0)
    kcal_per_100g: float | None = Field(default=None, ge=0)
    carb_per_100g: float | None = Field(default=None, ge=0)
    fiber_per_100g: float | None = Field(default=None, ge=0)
    summary: str = ""
    source: str = Field(min_length=1)


class ProductInfoProvider(Protocol):
    name: str

    def lookup(self, label: str) -> ProductInfo:
        """Return price and a short description for an already recognized label."""


class DisabledProductInfo:
    name = "disabled"

    def lookup(self, label: str) -> ProductInfo:
        raise RuntimeError("product info is disabled")


class MockProductInfo:
    name = "mock"

    def lookup(self, label: str) -> ProductInfo:
        return ProductInfo(
            label=label,
            price_per_kg=12.0,
            summary="test price, not from a catalog",
            source="mock",
        )


# 《中国食物成分表》每 100 克：能量、碳水化合物、膳食纤维。香蕉与原来同一行。
# 单价是演示价，不是成分表里的数。发给板子的名字用 label。
_FOODS: tuple[dict[str, float | str], ...] = (
    {"label": "banana", "zh": "香蕉", "price_per_kg": 12.0, "kcal_per_100g": 91.0, "carb_per_100g": 22.0, "fiber_per_100g": 1.2},
    {"label": "apple", "zh": "苹果", "price_per_kg": 10.0, "kcal_per_100g": 52.0, "carb_per_100g": 13.5, "fiber_per_100g": 1.2},
    {"label": "orange", "zh": "橙子", "price_per_kg": 8.0, "kcal_per_100g": 47.0, "carb_per_100g": 11.1, "fiber_per_100g": 0.6},
    {"label": "mandarin", "zh": "橘子", "price_per_kg": 8.0, "kcal_per_100g": 51.0, "carb_per_100g": 11.9, "fiber_per_100g": 0.4},
    {"label": "pear", "zh": "梨", "price_per_kg": 6.0, "kcal_per_100g": 44.0, "carb_per_100g": 13.3, "fiber_per_100g": 3.1},
    {"label": "grape", "zh": "葡萄", "price_per_kg": 16.0, "kcal_per_100g": 43.0, "carb_per_100g": 10.3, "fiber_per_100g": 0.4},
    {"label": "watermelon", "zh": "西瓜", "price_per_kg": 3.0, "kcal_per_100g": 25.0, "carb_per_100g": 5.8, "fiber_per_100g": 0.3},
    {"label": "strawberry", "zh": "草莓", "price_per_kg": 20.0, "kcal_per_100g": 30.0, "carb_per_100g": 7.1, "fiber_per_100g": 1.1},
    {"label": "peach", "zh": "桃子", "price_per_kg": 10.0, "kcal_per_100g": 48.0, "carb_per_100g": 12.2, "fiber_per_100g": 1.3},
    {"label": "kiwi", "zh": "猕猴桃", "price_per_kg": 12.0, "kcal_per_100g": 56.0, "carb_per_100g": 14.5, "fiber_per_100g": 2.6},
    {"label": "pineapple", "zh": "菠萝", "price_per_kg": 8.0, "kcal_per_100g": 41.0, "carb_per_100g": 10.8, "fiber_per_100g": 1.3},
    {"label": "cantaloupe", "zh": "哈密瓜", "price_per_kg": 6.0, "kcal_per_100g": 34.0, "carb_per_100g": 7.9, "fiber_per_100g": 0.2},
)
_ALIASES = {
    "橙": "orange",
    "桔子": "mandarin",
    "柑橘": "mandarin",
    "桃": "peach",
    "梨子": "pear",
    "奇异果": "kiwi",
    "kiwifruit": "kiwi",
    "凤梨": "pineapple",
}


def _bind(table: dict[str, dict[str, float | str]]) -> None:
    for row in _FOODS:
        table[str(row["label"]).casefold()] = row
        table[str(row["zh"]).casefold()] = row
    for alias, label in _ALIASES.items():
        table[alias.casefold()] = table[label]


_BY_NAME: dict[str, dict[str, float | str]] = {}
_bind(_BY_NAME)


def _info(row: dict[str, float | str]) -> ProductInfo:
    return ProductInfo(
        label=str(row["label"]),
        price_per_kg=float(row["price_per_kg"]),
        kcal_per_100g=float(row["kcal_per_100g"]),
        carb_per_100g=float(row["carb_per_100g"]),
        fiber_per_100g=float(row["fiber_per_100g"]),
        summary="demo standard per kilogram and per 100 g",
        source="table",
    )


def wire_labels() -> frozenset[str]:
    return frozenset(str(row["label"]) for row in _FOODS)


def spoken_name(label: str) -> str:
    row = _BY_NAME.get(label.strip().casefold())
    if row is None:
        return label
    return str(row["zh"])


def food_from_text(text: str) -> ProductInfo | None:
    folded = text.casefold()
    for key in sorted(_BY_NAME, key=len, reverse=True):
        if key and key in folded:
            return _info(_BY_NAME[key])
    return None


class TableProductInfo:
    """A few demo foods. Lookup uses the name only."""

    name = "table"

    def lookup(self, label: str) -> ProductInfo:
        row = _BY_NAME.get(label.strip().casefold())
        if row is None:
            raise KeyError(label)
        return _info(row)


class TextModelProductInfo:
    name = "text"

    def lookup(self, label: str) -> ProductInfo:
        if not os.getenv("TEXT_MODEL_API_KEY", "").strip():
            raise MissingApiKey("TEXT_MODEL_API_KEY")
        raise RemoteCallNotReady(self.name)


def build_product_info(name: str | None = None) -> ProductInfoProvider:
    selected = name if name is not None else os.getenv("PRODUCT_INFO_PROVIDER", "disabled")
    if selected == "disabled":
        return DisabledProductInfo()
    if selected == "mock":
        return MockProductInfo()
    if selected == "text":
        return TextModelProductInfo()
    if selected == "table":
        return TableProductInfo()
    raise ValueError(f"unknown product info provider: {selected}")
