"""Describe the two cloud calls. Nothing here opens a network connection."""

from __future__ import annotations

import os
import sys

from pydantic import BaseModel, ConfigDict

_MODEL_CONFIG = ConfigDict(extra="forbid")
_VISION_PROVIDERS = {"minimax", "volcano"}


class CloudRequest(BaseModel):
    model_config = _MODEL_CONFIG
    provider: str
    task: str
    image_path: str | None = None
    label: str | None = None


def vision_request(provider: str, image_path: str) -> CloudRequest:
    if provider not in _VISION_PROVIDERS:
        raise ValueError(f"unknown vision provider: {provider}")
    return CloudRequest(provider=provider, task="identify", image_path=image_path)


def text_request(label: str) -> CloudRequest:
    return CloudRequest(provider="text", task="price_lookup", label=label)


def preview_provider() -> str:
    selected = os.getenv("VISION_PROVIDER", "minimax")
    if selected in _VISION_PROVIDERS:
        return selected
    return "minimax"


def main() -> None:
    provider = preview_provider()
    vision = vision_request(provider, "banana.jpg")
    text = text_request("banana")
    print(f"vision_task: {vision.task}")
    print(f"vision_provider: {vision.provider}")
    print(f"vision_image: {vision.image_path}")
    print(f"text_task: {text.task}")
    print(f"text_label: {text.label}")
    print("sent: no")


if __name__ == "__main__":
    main()
    sys.exit(0)
