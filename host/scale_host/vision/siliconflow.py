"""Ask SiliconFlow what is in a photo. The reply's price and nutrition are ignored."""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from scale_host.domain import ProductRecognition
from scale_host.providers import MissingApiKey

_PROMPT = (
    'Name the food in this photo. Reply with one JSON object only: {"label":"banana"}. '
    "Do not include price, calories, or nutrients."
)


def label_from_reply(text: str) -> str:
    """Keep the food name. Ignore a price or nutrition the model added."""
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`").strip()
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        label = payload.get("label")
        if isinstance(label, str) and label.strip():
            return label.strip()
    first = raw.splitlines()[0].strip() if raw else ""
    for separator in ("，", ",", "。", "；", ";"):
        first = first.split(separator)[0].strip()
    if not first:
        raise RuntimeError("vision reply had no label")
    return first


class SiliconFlowVision:
    name = "siliconflow"

    def recognize(self, image_path: str) -> ProductRecognition:
        key = os.getenv("SILICONFLOW_API_KEY", "").strip()
        if not key:
            raise MissingApiKey("SILICONFLOW_API_KEY")
        model = os.getenv("SILICONFLOW_VISION_MODEL", "").strip()
        if not model:
            raise MissingApiKey("SILICONFLOW_VISION_MODEL")
        base = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1").rstrip("/")
        body = _request_body(model, image_path)
        request = urllib.request.Request(
            f"{base}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"siliconflow vision failed: HTTP {exc.code}") from exc
        content = payload["choices"][0]["message"]["content"]
        return ProductRecognition(
            label=label_from_reply(content),
            confidence=1.0,
            source="siliconflow",
            image_id=image_path,
        )


def _request_body(model: str, image_path: str) -> dict[str, object]:
    path = Path(image_path)
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    suffix = path.suffix.lower().lstrip(".")
    media = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp", "gif": "gif"}.get(
        suffix, "jpeg"
    )
    return {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/{media};base64,{encoded}"},
                    },
                    {"type": "text", "text": _PROMPT},
                ],
            }
        ],
    }
