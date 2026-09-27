import json

import pytest

from scale_host.device.interface import DisplayRequest
from scale_host.device.serial_device import SerialScaleDevice
from scale_host.domain import ScaleStatus


class MemoryPort:
    def __init__(self, incoming: list[bytes]) -> None:
        self.incoming = list(incoming)
        self.outgoing: list[bytes] = []

    def write(self, data: bytes) -> None:
        self.outgoing.append(data)

    def readline(self) -> bytes:
        if not self.incoming:
            return b""
        return self.incoming.pop(0)


def _weight_line() -> bytes:
    return (
        b'{"v":1,"type":"weight","seq":2,"timestamp_ms":20,'
        b'"weight_g":326.4,"stable":true,"tare_g":0,"status":"ok"}\n'
    )


async def test_serial_reads_a_stable_weight_and_drops_a_bad_line() -> None:
    port = MemoryPort(
        [
            b'{"v":1,"type":"status","seq":1,"timestamp_ms":10,"state":"WEIGHT_STABLE"}\n',
            b"123.45\n",
            b"\n",
            _weight_line(),
        ]
    )
    device = SerialScaleDevice(port)
    await device.connect()
    events = [event async for event in device.events()]
    assert events[0].weight_g == 326.4
    assert events[0].stable is True
    assert events[0].state is ScaleStatus.WEIGHT_STABLE
    assert events[1].connected is False


async def test_tare_writes_the_v1_command_and_uses_the_ack() -> None:
    port = MemoryPort(
        [b'{"v":1,"type":"ack","seq":3,"timestamp_ms":30,"command":"tare","status":"ok"}\n']
    )
    device = SerialScaleDevice(port)
    await device.connect()
    result = await device.tare()
    sent = json.loads(port.outgoing[0].decode("utf-8"))
    assert sent == {"v": 1, "type": "command", "command": "tare"}
    assert result.status == "ok"


async def test_display_writes_price_in_yuan() -> None:
    port = MemoryPort([])
    device = SerialScaleDevice(port)
    await device.connect()
    await device.display(DisplayRequest(product="banana", weight_g=326.4, price=3.92))
    sent = json.loads(port.outgoing[0].decode("utf-8"))
    assert sent["type"] == "display_result"
    assert sent["product"] == "banana"
    assert sent["weight_g"] == 326.4
    assert sent["price"] == 3.92
    assert len(sent["request_id"]) <= 32


def test_unknown_port_name_is_rejected() -> None:
    from scale_host.device.serial_device import SerialOpenError, open_system_port

    with pytest.raises(SerialOpenError, match="COM_NOT_A_PORT"):
        open_system_port("COM_NOT_A_PORT")


def test_open_requests_115200_8n1(monkeypatch) -> None:
    import serial

    from scale_host.device.serial_device import open_system_port

    captured: dict[str, object] = {}

    class _FakeSerial:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

        def close(self) -> None:
            captured["closed"] = True

    monkeypatch.setattr(serial, "Serial", _FakeSerial)
    opened = open_system_port("COM3")
    opened.close()
    assert captured["port"] == "COM3"
    assert captured["baudrate"] == 115200
    assert captured["bytesize"] == serial.EIGHTBITS
    assert captured["parity"] == serial.PARITY_NONE
    assert captured["stopbits"] == serial.STOPBITS_ONE

