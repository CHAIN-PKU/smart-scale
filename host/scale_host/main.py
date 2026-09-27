"""Start the host from configuration. The default device is the simulator."""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv


_DEVICES = {"simulator", "serial"}
_VISION = {"disabled", "mock", "minimax", "volcano"}
_PRODUCT_INFO = {"disabled", "mock", "text"}


def main() -> None:
    load_dotenv(override=False)
    device_name = os.getenv("SCALE_DEVICE", "simulator")
    vision_name = os.getenv("VISION_PROVIDER", "disabled")
    product_info_name = os.getenv("PRODUCT_INFO_PROVIDER", "disabled")
    if device_name not in _DEVICES:
        print(f"unknown device: {device_name}", file=sys.stderr)
        raise SystemExit(2)
    if vision_name not in _VISION:
        print(f"unknown vision: {vision_name}", file=sys.stderr)
        raise SystemExit(2)
    if product_info_name not in _PRODUCT_INFO:
        print(f"unknown product info: {product_info_name}", file=sys.stderr)
        raise SystemExit(2)
    print("Smart Scale Host")
    print(f"device: {device_name}")
    print(f"vision: {vision_name}")
    print(f"product_info: {product_info_name}")


if __name__ == "__main__":
    main()
