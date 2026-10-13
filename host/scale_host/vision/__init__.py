"""Vision providers. They identify an item and do not choose the price."""

from scale_host.vision.interface import (
    MiniMaxVision,
    MockVision,
    VisionProvider,
    VolcanoVision,
    build_vision,
)
from scale_host.vision.siliconflow import SiliconFlowVision, label_from_reply

__all__ = [
    "MiniMaxVision",
    "MockVision",
    "SiliconFlowVision",
    "VisionProvider",
    "VolcanoVision",
    "build_vision",
    "label_from_reply",
]
