"""Start the host from configuration. The default device is the simulator."""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime
from uuid import uuid4

from dotenv import load_dotenv

from scale_host.device.serial_device import LinePort, SerialOpenError, open_system_port
from scale_host.pipeline import price_open_port, record_stable_sale
from scale_host.providers import MissingApiKey, RemoteCallNotReady
from scale_host.storage import SqliteRepository, WeighingSession

_DEVICES = {"simulator", "serial"}
_VISION = {"disabled", "mock", "minimax", "volcano"}
_PRODUCT_INFO = {"disabled", "mock", "text"}


def main() -> None:
    load_dotenv(override=False)
    device_name = os.getenv("SCALE_DEVICE", "simulator")
    vision_name = os.getenv("VISION_PROVIDER", "mock")
    product_info_name = os.getenv("PRODUCT_INFO_PROVIDER", "mock")
    if device_name not in _DEVICES:
        print(f"unknown device: {device_name}", file=sys.stderr)
        raise SystemExit(2)
    if vision_name not in _VISION:
        print(f"unknown vision: {vision_name}", file=sys.stderr)
        raise SystemExit(2)
    if product_info_name not in _PRODUCT_INFO:
        print(f"unknown product info: {product_info_name}", file=sys.stderr)
        raise SystemExit(2)
    os.environ["SCALE_DEVICE"] = device_name
    os.environ["VISION_PROVIDER"] = vision_name
    os.environ["PRODUCT_INFO_PROVIDER"] = product_info_name
    if device_name == "serial" and not os.getenv("SERIAL_PORT", "").strip():
        print("missing serial port", file=sys.stderr)
        raise SystemExit(2)
    print("Smart Scale Host")
    print(f"device: {device_name}")
    print(f"vision: {vision_name}")
    print(f"product_info: {product_info_name}")
    if device_name == "serial":
        port_name = os.getenv("SERIAL_PORT", "").strip()
        print(f"serial_port: {port_name}")
        try:
            opened = open_system_port(port_name)
        except SerialOpenError:
            print(f"cannot open serial port: {port_name}", file=sys.stderr)
            raise SystemExit(2)
        print("serial_open: ok")
        if vision_name == "disabled" or product_info_name == "disabled":
            opened.close()
            return
        try:
            _print_recorded_sale_from_port(opened)
        finally:
            opened.close()
        return
    if device_name == "simulator" and vision_name != "disabled" and product_info_name != "disabled":
        _print_recorded_sale()


def _print_recorded_sale_from_port(port: LinePort) -> None:
    repository = SqliteRepository(os.getenv("DATABASE_PATH", "data/scale.db"))
    session_id = f"banana-{uuid4().hex[:8]}"
    timestamp = datetime.now().astimezone().replace(microsecond=0).isoformat()
    try:
        asyncio.run(
            price_open_port(port, repository, session_id=session_id, timestamp=timestamp)
        )
        stored = repository.get_session(session_id)
    except (RuntimeError, MissingApiKey, RemoteCallNotReady) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
    _print_stored(stored)


def _print_stored(stored: WeighingSession | None) -> None:
    if stored is None or stored.amount_yuan is None:
        print("sale was not stored", file=sys.stderr)
        raise SystemExit(2)
    print(f"label: {stored.label}")
    print(f"weight_g: {stored.weight_g}")
    print(f"price_per_kg: {stored.price_per_kg}")
    print(f"amount_yuan: {stored.amount_yuan:.2f}")
    print(f"stored: {stored.id}")


def _print_recorded_sale() -> None:
    repository = SqliteRepository(os.getenv("DATABASE_PATH", "data/scale.db"))
    session_id = f"banana-{uuid4().hex[:8]}"
    timestamp = datetime.now().astimezone().replace(microsecond=0).isoformat()
    try:
        asyncio.run(
            record_stable_sale(repository, session_id=session_id, timestamp=timestamp)
        )
        stored = repository.get_session(session_id)
    except (RuntimeError, MissingApiKey, RemoteCallNotReady) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
    _print_stored(stored)


if __name__ == "__main__":
    main()
