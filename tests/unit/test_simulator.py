import pytest

from scale_host.device import DeviceLink, DisplayRequest, SimulatedScaleDevice
from scale_host.domain import ScaleStatus, WeightReading


async def _collect(scenario: str) -> list[WeightReading | DeviceLink]:
    device = SimulatedScaleDevice(scenario)
    await device.connect()
    return [item async for item in device.events()]


def _readings(events: list[WeightReading | DeviceLink]) -> list[WeightReading]:
    return [item for item in events if isinstance(item, WeightReading)]


def _states(readings: list[WeightReading]) -> list[ScaleStatus]:
    seen: list[ScaleStatus] = []
    for reading in readings:
        assert reading.state is not None
        if not seen or seen[-1] is not reading.state:
            seen.append(reading.state)
    return seen


@pytest.mark.asyncio
async def test_banana_ramps_then_becomes_stable() -> None:
    readings = _readings(await _collect("banana"))
    weights = [reading.weight_g for reading in readings]
    for expected in (0.0, 12.0, 145.0, 310.0, 326.0, 326.4):
        assert expected in weights
    assert readings[-1].weight_g == 326.4
    assert readings[-1].stable is True
    assert readings[-1].state is ScaleStatus.WEIGHT_STABLE
    assert readings[-1].tare_g == 0.0
    assert ScaleStatus.WEIGHT_CHANGED in _states(readings)


@pytest.mark.asyncio
async def test_connect_does_not_tare() -> None:
    device = SimulatedScaleDevice("banana")
    await device.connect()
    first = await anext(device.events())
    assert isinstance(first, WeightReading)
    assert first.tare_g == 0.0


@pytest.mark.asyncio
async def test_noise_does_not_stabilize() -> None:
    readings = _readings(await _collect("noise"))
    assert readings
    assert all(reading.state is not ScaleStatus.WEIGHT_STABLE for reading in readings)


@pytest.mark.asyncio
async def test_removed_returns_to_zero() -> None:
    states = _states(_readings(await _collect("removed")))
    assert states.index(ScaleStatus.WEIGHT_STABLE) < states.index(ScaleStatus.WEIGHT_REMOVED)
    assert states[-1] is ScaleStatus.ZERO


@pytest.mark.asyncio
async def test_overload_refuses_tare() -> None:
    device = SimulatedScaleDevice("overload")
    await device.connect()
    readings = _readings([item async for item in device.events()])
    assert readings[-1].state is ScaleStatus.OVERLOAD
    assert readings[-1].status == "overload"
    result = await device.tare()
    assert result.status == "error"


@pytest.mark.asyncio
async def test_sensor_error_and_serial_disconnect() -> None:
    sensor = _readings(await _collect("sensor_error"))
    assert sensor[-1].state is ScaleStatus.ERROR
    serial = await _collect("serial_disconnected")
    assert isinstance(serial[-1], DeviceLink)
    assert serial[-1].connected is False


@pytest.mark.asyncio
async def test_display_is_recorded_without_a_port() -> None:
    device = SimulatedScaleDevice("banana")
    await device.connect()
    request = DisplayRequest(product="banana", weight_g=326.4, price=3.92)
    await device.display(request)
    assert device.displayed == [request]
