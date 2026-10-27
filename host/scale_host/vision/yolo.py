"""Name a fruit with the local YOLO11n model. The short table still sets the price."""

from __future__ import annotations

import os
from pathlib import Path

from scale_host.catalog.lookup import wire_labels
from scale_host.domain import ProductRecognition

_SESSION = None


def model_path() -> Path:
    override = os.getenv("YOLO_MODEL", "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[3] / "models" / "yolo11n.onnx"


def best_known(detections: list[dict[str, object]]) -> dict[str, object] | None:
    allowed = wire_labels()
    known = [item for item in detections if item.get("label") in allowed]
    if not known:
        return None
    return max(known, key=lambda item: float(item["confidence"]))


def detect(image_path: Path, confidence_threshold: float) -> dict[str, object]:
    import numpy as np
    import onnxruntime as ort
    from PIL import Image

    weights = model_path()
    if not weights.is_file():
        raise RuntimeError(f"missing yolo model: {weights}")
    global _SESSION
    if _SESSION is None:
        _SESSION = ort.InferenceSession(str(weights), providers=["CPUExecutionProvider"])
    session = _SESSION
    input_name = session.get_inputs()[0].name
    with Image.open(image_path) as image:
        original_width, original_height = image.size
        tensor, scale, pad_x, pad_y = _letterbox(image)
    output = session.run(None, {input_name: tensor})[0][0]
    if output.shape[0] != 84:
        raise RuntimeError(f"Unexpected YOLO output shape: {output.shape}")
    detections: list[dict[str, object]] = []
    for class_index, label in enumerate(_COCO_LABELS):
        scores = output[4 + class_index]
        anchor = int(np.argmax(scores))
        score = float(scores[anchor])
        if score < confidence_threshold:
            continue
        center_x, center_y, box_width, box_height = (float(value) for value in output[:4, anchor])
        left = (center_x - box_width / 2.0 - pad_x) / scale
        top = (center_y - box_height / 2.0 - pad_y) / scale
        right = (center_x + box_width / 2.0 - pad_x) / scale
        bottom = (center_y + box_height / 2.0 - pad_y) / scale
        detections.append(
            {
                "label": label,
                "confidence": round(score, 6),
                "box": [
                    max(0, int(round(left))),
                    max(0, int(round(top))),
                    min(original_width, int(round(right))),
                    min(original_height, int(round(bottom))),
                ],
            }
        )
    detections.sort(key=lambda item: float(item["confidence"]), reverse=True)
    return {"detections": detections}


def _letterbox(image: object, size: int = 640) -> tuple[object, float, int, int]:
    import numpy as np
    from PIL import Image

    picture = image.convert("RGB")
    width, height = picture.size
    scale = min(size / width, size / height)
    new_width = int(round(width * scale))
    new_height = int(round(height * scale))
    resized = picture.resize((new_width, new_height), Image.Resampling.BILINEAR)
    canvas = Image.new("RGB", (size, size), (114, 114, 114))
    pad_x = (size - new_width) // 2
    pad_y = (size - new_height) // 2
    canvas.paste(resized, (pad_x, pad_y))
    pixels = np.asarray(canvas, dtype=np.float32) / 255.0
    tensor = np.transpose(pixels, (2, 0, 1))[None, :, :, :]
    return tensor, scale, pad_x, pad_y


class YoloVision:
    name = "yolo"

    def recognize(self, image_path: str) -> ProductRecognition:
        threshold = float(os.getenv("YOLO_CONFIDENCE", "0.15"))
        found = best_known(detect(Path(image_path), threshold)["detections"])
        if found is None:
            raise RuntimeError("no food visible in this image")
        return ProductRecognition(
            label=str(found["label"]),
            confidence=float(found["confidence"]),
            source=self.name,
            image_id=image_path,
        )


_COCO_LABELS = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck",
    "boat", "traffic light", "fire hydrant", "stop sign", "parking meter", "bench",
    "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra",
    "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
    "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove",
    "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup",
    "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
    "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear", "hair drier",
    "toothbrush",
]
