"""Vision providers. Recognition returns a product guess, never a price."""

from __future__ import annotations

import os
from typing import Protocol

from scale_host.domain import ProductRecognition
from scale_host.providers import MissingApiKey, RemoteCallNotReady


class VisionProvider(Protocol):
    name: str

    def recognize(self, image_path: str) -> ProductRecognition:
        """Identify the item in a saved image."""


class DisabledVision:
    name = "disabled"

    def recognize(self, image_path: str) -> ProductRecognition:
        raise RuntimeError("vision is disabled")


class MockVision:
    name = "mock"

    def recognize(self, image_path: str) -> ProductRecognition:
        return ProductRecognition(
            label="banana",
            confidence=0.91,
            source="mock",
            image_id=image_path,
        )


class _KeyedVision:
    def __init__(self, name: str, key_env: str, model_env: str, base_url_env: str) -> None:
        self.name = name
        self.key_env = key_env
        self.model_env = model_env
        self.base_url_env = base_url_env

    def recognize(self, image_path: str) -> ProductRecognition:
        if not os.getenv(self.key_env, "").strip():
            raise MissingApiKey(self.key_env)
        raise RemoteCallNotReady(self.name)


class MiniMaxVision(_KeyedVision):
    def __init__(self) -> None:
        super().__init__(
            "minimax",
            "MINIMAX_API_KEY",
            "MINIMAX_VISION_MODEL",
            "MINIMAX_BASE_URL",
        )


class VolcanoVision(_KeyedVision):
    def __init__(self) -> None:
        super().__init__(
            "volcano",
            "VOLCENGINE_API_KEY",
            "VOLCENGINE_VISION_MODEL",
            "VOLCENGINE_BASE_URL",
        )


def build_vision(name: str | None = None) -> VisionProvider:
    selected = name if name is not None else os.getenv("VISION_PROVIDER", "disabled")
    if selected == "disabled":
        return DisabledVision()
    if selected == "mock":
        return MockVision()
    if selected == "minimax":
        return MiniMaxVision()
    if selected == "volcano":
        return VolcanoVision()
    raise ValueError(f"unknown vision provider: {selected}")
