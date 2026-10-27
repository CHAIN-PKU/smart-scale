"""Keep the newest OpenMV JPEG. The camera uses its own COM port, not the scale."""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path


def take_jpegs(buffer: bytearray) -> list[bytes]:
    frames: list[bytes] = []
    while True:
        marker = buffer.find(b"\xA5\x5A")
        if marker < 0:
            if len(buffer) > 1:
                del buffer[:-1]
            return frames
        if marker > 0:
            del buffer[:marker]
        if len(buffer) < 6:
            return frames
        length = int.from_bytes(buffer[2:6], "little")
        if length <= 0 or length > 300_000:
            del buffer[0]
            continue
        if len(buffer) < 6 + length:
            return frames
        frames.append(bytes(buffer[6 : 6 + length]))
        del buffer[: 6 + length]


class OpenMvCamera:
    def __init__(self, port: str, output_path: Path) -> None:
        self.port = port
        self.output_path = output_path
        self.buffer = bytearray()
        self.error: Exception | None = None
        self.stopped = threading.Event()
        self.ready = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.thread.start()
        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline:
            if self.ready.is_set():
                return
            time.sleep(0.05)
        if self.error is not None:
            raise RuntimeError(f"OpenMV camera error: {self.error}") from self.error
        raise TimeoutError("No camera frame received within 8 seconds")

    def stop(self) -> None:
        self.stopped.set()
        self.thread.join(timeout=1.0)

    def _publish(self, jpeg: bytes) -> None:
        temporary = self.output_path.with_suffix(".jpg.tmp")
        temporary.write_bytes(jpeg)
        for _ in range(5):
            try:
                os.replace(temporary, self.output_path)
                self.ready.set()
                return
            except OSError:
                time.sleep(0.02)

    def _run(self) -> None:
        import serial

        while not self.stopped.is_set():
            camera = None
            try:
                camera = serial.Serial(
                    self.port,
                    baudrate=115200,
                    timeout=0.2,
                    write_timeout=1.0,
                )
                camera.dtr = True
                camera.rts = True
                self.error = None
                self.buffer.clear()
                while not self.stopped.is_set():
                    chunk = camera.read(8192)
                    if chunk:
                        self.buffer.extend(chunk)
                    for jpeg in take_jpegs(self.buffer):
                        self._publish(jpeg)
            except Exception as exc:
                self.error = exc
                if self.stopped.is_set():
                    break
                time.sleep(0.5)
            finally:
                if camera is not None:
                    camera.close()
