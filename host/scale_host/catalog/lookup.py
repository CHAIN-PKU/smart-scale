"""Product facts and price. A text model looks these up after recognition."""

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
    raise ValueError(f"unknown product info provider: {selected}")
