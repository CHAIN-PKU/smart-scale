import asyncio
import json

from scale_host.device.dynamics import ScaleDynamics
from scale_host.device.simulator import SimulatedScaleDevice
from scale_host.domain import ProductRecognition, ScaleStatus, WeightReading
from scale_host.live_view import (
    LIVE_FRAME,
    main,
    placement_notices,
    price_current_view,
    remember_placements,
    watch_readings,
)
from scale_host.storage import SqliteRepository


class RecordingVision:
    name = "mock"

    def __init__(self, labels: list[str] | None = None) -> None:
        self.paths: list[str] = []
        self.labels = labels

    def recognize(self, image_path: str) -> ProductRecognition:
        self.paths.append(image_path)
        label = "banana" if self.labels is None else self.labels[len(self.paths) - 1]
        return ProductRecognition(
            label=label,
            confidence=0.91,
            source="mock",
            image_id=image_path,
        )


def _samples(*groups: list[float]) -> list[WeightReading]:
    dynamics = ScaleDynamics()
    dynamics.ready()
    readings: list[WeightReading] = []
    timestamp_ms = 0
    for group in groups:
        for weight in group:
            readings.append(dynamics.observe(timestamp_ms, weight))
            timestamp_ms += 100
    return readings


def _hold(weight: float) -> list[float]:
    return [weight] * 8


def _block_network(monkeypatch) -> None:
    def _opened(*_args, **_kwargs):
        raise AssertionError("network opened")

    monkeypatch.setattr("urllib.request.urlopen", _opened)
    monkeypatch.setattr("serial.Serial", _opened)


def test_recognition_waits_for_the_stable_placement(monkeypatch) -> None:
    _block_network(monkeypatch)
    vision = RecordingVision()
    result = asyncio.run(price_current_view(SimulatedScaleDevice("banana"), vision))
    assert vision.paths == [LIVE_FRAME]
    assert result.sale is not None
    assert result.recognized_at is not None
    assert result.recognized_at.state is ScaleStatus.WEIGHT_STABLE
    assert result.recognized_at.weight_g == 326.4
    assert result.sale.label == "banana"
    assert result.sale.image_path == LIVE_FRAME
    assert result.sale.weight_g == 326.4
    assert result.sale.amount_yuan == 3.92
    assert result.sale.vision_source == "mock"


def test_drift_does_not_look_again_until_the_item_is_removed(monkeypatch) -> None:
    _block_network(monkeypatch)
    vision = RecordingVision()
    readings = _samples(_hold(326.4), _hold(328.0), _hold(0.0), _hold(200.0))
    sales = watch_readings(readings, vision, ["frame-a", "frame-b"])
    assert vision.paths == ["frame-a", "frame-b"]
    assert [(sale.weight_g, sale.amount_yuan, sale.image_path) for sale in sales] == [
        (326.4, 3.92, "frame-a"),
        (200.0, 2.40, "frame-b"),
    ]


def test_each_live_sale_sends_one_display_line_and_one_spoken_line(monkeypatch) -> None:
    _block_network(monkeypatch)
    vision = RecordingVision()
    readings = _samples(_hold(326.4), _hold(328.0), _hold(0.0), _hold(200.0))
    notices = placement_notices(watch_readings(readings, vision, ["frame-a", "frame-b"]))
    assert len(notices) == 2
    first, second = notices
    _assert_notice(first, "r_001", 326.4, 3.92, "香蕉，326.4克，3.92元")
    _assert_notice(second, "r_002", 200.0, 2.40, "香蕉，200克，2.40元")


def _assert_notice(notice: tuple[str, str], request_id: str, weight_g: float, price: float, spoken: str) -> None:
    line, speech = notice
    payload = json.loads(line)
    assert set(payload) == {"v", "type", "request_id", "product", "weight_g", "price"}
    assert payload["type"] == "display_result"
    assert payload["product"] == "banana"
    assert payload["request_id"] == request_id
    assert payload["weight_g"] == weight_g
    assert payload["price"] == price
    assert speech == spoken
    assert "千卡" not in line
    assert "千卡" not in speech
    assert "碳水" not in line
    assert "碳水" not in speech


def test_each_live_sale_is_stored_once_with_its_nutrition(tmp_path, monkeypatch) -> None:
    _block_network(monkeypatch)
    repository = SqliteRepository(tmp_path / "scale.db")
    vision = RecordingVision()
    readings = _samples(_hold(326.4), _hold(328.0), _hold(0.0), _hold(200.0))
    saved = remember_placements(readings, vision, ["frame-a", "frame-b"], repository)
    assert [(item.id, item.weight_g, item.amount_yuan) for item in saved] == [
        ("live-001", 326.4, 3.92),
        ("live-002", 200.0, 2.40),
    ]
    first = repository.get_session("live-001")
    second = repository.get_session("live-002")
    assert first is not None and second is not None
    assert first.portion_kcal == 297.0
    assert first.portion_carb_g == 71.8
    assert first.image_path == "frame-a"
    assert second.portion_kcal == 182.0
    assert second.portion_carb_g == 44.0
    assert second.image_path == "frame-b"
    assert len(repository.list_sessions()) == 2


def test_a_frame_without_food_is_not_priced(monkeypatch) -> None:
    _block_network(monkeypatch)
    vision = RecordingVision(["no food visible in this image", "banana"])
    readings = _samples(_hold(326.4), _hold(0.0), _hold(200.0))
    sales = watch_readings(readings, vision, ["frame-empty", "frame-banana"])
    assert vision.paths == ["frame-empty", "frame-banana"]
    assert len(sales) == 1
    assert sales[0].label == "banana"
    assert sales[0].weight_g == 200.0
    assert sales[0].amount_yuan == 2.40


def test_an_unsettled_scale_is_not_recognized(monkeypatch) -> None:
    _block_network(monkeypatch)
    vision = RecordingVision()
    result = asyncio.run(price_current_view(SimulatedScaleDevice("noise"), vision))
    assert vision.paths == []
    assert result.sale is None
    assert result.recognized_at is None


def test_live_view_command_stays_offline(capsys, monkeypatch) -> None:
    _block_network(monkeypatch)
    main()
    lines = capsys.readouterr().out.splitlines()
    assert lines == [
        "live: stable",
        "label: banana",
        "frame: live-frame",
        "weight_g: 326.4",
        "price: 3.92",
        "recognized_state: WEIGHT_STABLE",
        "sent_to_internet: no",
        "com_open: no",
    ]
