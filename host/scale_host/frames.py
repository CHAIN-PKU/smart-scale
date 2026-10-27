"""The photo of this placement. The demo pictures are not this placement."""

from __future__ import annotations

import os
import time
from pathlib import Path

_OLD_PHOTOS = {"banana.jpg", "openmv.jpg", "openmv_banana.jpg"}


def current_frame() -> str | None:
    raw = os.getenv("SCALE_FRAME", "").strip()
    if not raw:
        return None
    path = Path(raw)
    if path.name in _OLD_PHOTOS or not path.is_file():
        return None
    raw_age = os.getenv("SCALE_FRAME_MAX_AGE_S", "").strip()
    if raw_age:
        age_s = time.time() - path.stat().st_mtime
        if age_s > float(raw_age):
            return None
    return str(path)
