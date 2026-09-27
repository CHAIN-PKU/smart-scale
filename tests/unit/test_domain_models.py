from pathlib import Path

import pytest
from pydantic import ValidationError

from scale_host.domain import (
    DeviceCommand,
    ProductObservation,
    ProductRecognition,
    ScaleStatus,
    WeightReading,
)
from scale_host.protocol.messages import StateName
from typing import get_args


def test_scale_status_matches_protocol_states() -> None:
    assert {item.value for item in ScaleStatus} == set(get_args(StateName))


def test_weight_reading_holds_a_net_weight() -> None:
    reading = WeightReading(
        seq=182,
        timestamp_ms=192839,
        weight_g=326.4,
        stable=True,
        tare_g=12.7,
        status="ok",
        state=ScaleStatus.WEIGHT_STABLE,
    )
    assert reading.weight_g == 326.4
    assert reading.state is ScaleStatus.WEIGHT_STABLE


def test_device_command_accepts_only_tare() -> None:
    assert DeviceCommand(command="tare").command == "tare"
    with pytest.raises(ValidationError):
        DeviceCommand(command="reboot")


def test_vision_and_fusion_types_carry_no_logic() -> None:
    recognition = ProductRecognition(
        label="banana",
        confidence=0.91,
        source="mock",
        candidates=[],
    )
    observation = ProductObservation(label="banana", confidence=0.96, weight_g=326.4)
    assert recognition.source == "mock"
    assert observation.weight_g == 326.4


def test_domain_source_stays_away_from_devices_and_models() -> None:
    source = Path(__file__).parents[2].joinpath("host/scale_host/domain/models.py").read_text(
        encoding="utf-8"
    )
    imports = [
        line
        for line in source.splitlines()
        if line.startswith("import ") or line.startswith("from ")
    ]
    for name in ("pyserial", "serial", "sqlalchemy", "cv2", "torch", "transformers"):
        assert all(name not in line for line in imports)
