"""Read and write V1 protocol lines. Opening a COM port is separate from parsing."""

from __future__ import annotations

from typing import Protocol
from uuid import uuid4

from scale_host.device.interface import CommandResult, DeviceLink, DisplayRequest
from scale_host.domain import ScaleStatus, WeightReading
from scale_host.protocol.messages import (
    AckMessage,
    CommandMessage,
    DisplayResultMessage,
    ProtocolError,
    StatusMessage,
    WeightMessage,
    parse_line,
)

_MAX_LINE_BYTES = 512


class LinePort(Protocol):
    def write(self, data: bytes) -> None:
        """Send bytes to the peer."""

    def readline(self) -> bytes:
        """Return one line including its newline, or empty bytes when the peer closes."""


class SerialScaleDevice:
    def __init__(self, port: LinePort) -> None:
        self._port = port
        self._connected = False
        self._state: ScaleStatus | None = None

    async def connect(self) -> None:
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    async def events(self):
        if not self._connected:
            yield DeviceLink(connected=False, detail="serial disconnected")
            return
        while self._connected:
            message = self._read_message()
            if message is _CLOSED:
                yield DeviceLink(connected=False, detail="serial disconnected")
                self._connected = False
                return
            if isinstance(message, StatusMessage):
                self._state = ScaleStatus(message.state)
                continue
            if isinstance(message, WeightMessage):
                yield _reading(message, self._state)

    async def tare(self) -> CommandResult:
        if not self._connected:
            return CommandResult(command="tare", status="error")
        self._write(CommandMessage(v=1, type="command", command="tare"))
        message = self._read_message()
        while message is None and self._connected:
            message = self._read_message()
        if isinstance(message, AckMessage) and message.status == "ok":
            return CommandResult(command="tare", status="ok")
        return CommandResult(command="tare", status="error")

    async def display(self, request: DisplayRequest) -> None:
        if not self._connected:
            return
        self._write(
            DisplayResultMessage(
                v=1,
                type="display_result",
                request_id=uuid4().hex[:8],
                product=request.product,
                weight_g=request.weight_g,
                price=request.price,
            )
        )

    def _write(self, message: CommandMessage | DisplayResultMessage) -> None:
        self._port.write(message.model_dump_json().encode("utf-8") + b"\n")

    def _read_message(self):
        while self._connected:
            raw = self._port.readline()
            if raw == b"":
                return _CLOSED
            if len(raw) > _MAX_LINE_BYTES + 2:
                continue
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                continue
            try:
                message = parse_line(text)
            except ProtocolError:
                continue
            if message is None or isinstance(message, (WeightMessage, StatusMessage, AckMessage)):
                return message
        return _CLOSED


class _Closed:
    pass


_CLOSED = _Closed()


def _reading(message: WeightMessage, state: ScaleStatus | None) -> WeightReading:
    return WeightReading(
        seq=message.seq,
        timestamp_ms=message.timestamp_ms,
        weight_g=message.weight_g,
        stable=message.stable,
        tare_g=message.tare_g,
        status=message.status,
        state=state,
    )


class SerialOpenError(Exception):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"cannot open serial port: {name}")


class PyserialPort:
    def __init__(self, handle: object) -> None:
        self._handle = handle

    def write(self, data: bytes) -> None:
        self._handle.write(data)  # type: ignore[attr-defined]

    def readline(self) -> bytes:
        return self._handle.readline()  # type: ignore[attr-defined]

    def close(self) -> None:
        self._handle.close()  # type: ignore[attr-defined]


def open_system_port(name: str) -> PyserialPort:
    import serial

    try:
        handle = serial.Serial(
            port=name,
            baudrate=115200,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1,
            write_timeout=1,
        )
    except (serial.SerialException, OSError) as exc:
        raise SerialOpenError(name) from exc
    return PyserialPort(handle)

