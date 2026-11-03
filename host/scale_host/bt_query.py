"""HC-05 transparent serial. The module is Bluetooth, not WiFi.

Data mode is 9600 8N1 unless the module was reconfigured. A phone serial
app sends one line and receives one JSON line. This does not open the
scale's COM port.
"""

from __future__ import annotations

import threading

from scale_host.remote_query import reply_line
from scale_host.storage import SqliteRepository


class BluetoothQuery:
    def __init__(self, repository: SqliteRepository, port: str, baud: int = 9600) -> None:
        self.repository = repository
        self.port = port
        self.baud = baud
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.error: Exception | None = None

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.stopped.set()
        self.thread.join(timeout=2.0)

    def _run(self) -> None:
        import serial

        link = None
        try:
            link = serial.Serial(self.port, baudrate=self.baud, timeout=0.3, write_timeout=1.0)
            while not self.stopped.is_set():
                raw = link.readline()
                if not raw:
                    continue
                try:
                    text = raw.decode("utf-8")
                except UnicodeDecodeError:
                    continue
                answer = reply_line(self.repository, text)
                if answer is None:
                    continue
                link.write((answer + "\n").encode("utf-8"))
        except Exception as exc:
            self.error = exc
        finally:
            if link is not None:
                link.close()
