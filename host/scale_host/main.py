"""Start the host from configuration. The default device is the simulator."""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv


def main() -> None:
    load_dotenv(override=False)
    device_name = os.getenv("SCALE_DEVICE", "simulator")
    vision_name = os.getenv("VISION_PROVIDER", "disabled")
    if device_name not in {"simulator", "serial"}:
        print(f"unknown device: {device_name}", file=sys.stderr)
        raise SystemExit(2)
    print("Smart Scale Host")
    print(f"device: {device_name}")
    print(f"vision: {vision_name}")


if __name__ == "__main__":
    main()
