"""Local page: live OpenMV frame, weighing records, and the receipt.

A phone on the same network can open the page. This uses the computer's
network. It does not open the scale's COM port.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

from scale_host.remote_query import receipt_payload, records_payload
from scale_host.storage import SqliteRepository

_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>智能电子秤</title>
  <style>
    body { margin: 0; font-family: "Microsoft YaHei", sans-serif; background: #f4f7fb; color: #1c2833; }
    main { max-width: 920px; margin: 24px auto; padding: 0 20px 40px; }
    h1 { margin: 0 0 8px; color: #1f4e79; }
    h2 { margin: 24px 0 8px; font-size: 18px; color: #1f4e79; }
    .panel { background: white; border: 1px solid #d0d7de; border-radius: 12px; padding: 16px 20px; }
    .muted { color: #5b6770; }
    img { width: 100%; max-height: 420px; object-fit: contain; background: #111; border-radius: 8px; }
    table { width: 100%; border-collapse: collapse; }
    th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid #e6ebf0; }
    td.num, th.num { text-align: right; }
    .empty { color: #5b6770; margin: 8px 0; }
  </style>
</head>
<body>
  <main>
    <h1>智能电子秤</h1>
    <p class="muted">电脑上的实时画面。正式屏幕仍是秤上的 TFT。这一页同时给出称重记录和清单。</p>
    <h2>OpenMV 实时画面</h2>
    <section class="panel">
      <img id="frame" alt="OpenMV 当前画面">
      <p id="frame-note" class="muted">正在等待画面。</p>
    </section>
    <h2>称重记录</h2>
    <section class="panel" id="records"><p class="empty">正在读取。</p></section>
    <h2>清单</h2>
    <section class="panel" id="receipt"><p class="empty">正在读取。</p></section>
  </main>
  <script>
    const frame = document.getElementById("frame");
    const frameNote = document.getElementById("frame-note");
    function yuan(value) {
      if (value === null || value === undefined) return "";
      return Number(value).toFixed(2);
    }
    function grams(value) {
      if (value === null || value === undefined) return "";
      return String(value);
    }
    function refreshFrame() {
      frame.src = "/frame.jpg?t=" + Date.now();
    }
    frame.onload = function () { frameNote.textContent = "这是相机刚刚传来的一帧。"; };
    frame.onerror = function () { frameNote.textContent = "还没有画面。请让主机连着 OpenMV。"; };
    async function refreshRecords() {
      const response = await fetch("/api/records");
      const body = await response.json();
      const box = document.getElementById("records");
      const items = body.items || [];
      if (!items.length) {
        box.innerHTML = '<p class="empty">还没有称重记录。</p>';
        return;
      }
      const rows = items.map(function (item) {
        return "<tr><td>" + (item.name || item.product || "") +
          "</td><td class='num'>" + grams(item.weight_g) +
          "</td><td class='num'>" + yuan(item.price) +
          "</td><td class='num'>" + yuan(item.price_per_kg) +
          "</td><td>" + (item.timestamp || "") + "</td></tr>";
      }).join("");
      box.innerHTML = "<table><tr><th>名称</th><th class='num'>克</th><th class='num'>金额</th><th class='num'>元/kg</th><th>时间</th></tr>" + rows + "</table>";
    }
    async function refreshReceipt() {
      const response = await fetch("/api/receipt");
      const body = await response.json();
      const box = document.getElementById("receipt");
      const items = body.items || [];
      if (!items.length) {
        box.innerHTML = '<p class="empty">清单是空的。合计 0.00 元。</p>';
        return;
      }
      const rows = items.map(function (item) {
        return "<tr><td class='num'>" + item.n +
          "</td><td>" + (item.product || "") +
          "</td><td class='num'>" + yuan(item.price_per_kg) +
          "</td><td class='num'>" + grams(item.weight_g) +
          "</td><td class='num'>" + yuan(item.price) + "</td></tr>";
      }).join("");
      box.innerHTML = "<table><tr><th class='num'>序号</th><th>名称</th><th class='num'>元/kg</th><th class='num'>克</th><th class='num'>价格</th></tr>" +
        rows + "<tr><td></td><td>合计</td><td></td><td></td><td class='num'>" + yuan(body.total) + "</td></tr></table>";
    }
    refreshFrame();
    refreshRecords();
    refreshReceipt();
    setInterval(refreshFrame, 400);
    setInterval(refreshRecords, 1000);
    setInterval(refreshReceipt, 1000);
  </script>
</body>
</html>
"""


class Desk:
    def __init__(self, repository: SqliteRepository, frame_path: Path, port: int, host: str = "127.0.0.1") -> None:
        self.repository = repository
        self.frame_path = frame_path
        self.port = port
        self.host = host
        self.httpd: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        if self.httpd is None:
            return ""
        bound_host, bound_port = self.httpd.server_address[:2]
        shown = "127.0.0.1" if bound_host in ("0.0.0.0", "") else bound_host
        return f"http://{shown}:{bound_port}"

    @property
    def lan_urls(self) -> list[str]:
        if self.httpd is None or self.host != "0.0.0.0":
            return []
        port = self.httpd.server_address[1]
        urls = []
        for ip in _local_ips():
            urls.append(f"http://{ip}:{port}")
        return urls

    def start(self) -> None:
        handler = _handler(self.repository, self.frame_path)
        self.httpd = ThreadingHTTPServer((self.host, self.port), handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
        if self.thread is not None:
            self.thread.join(timeout=2.0)
            self.thread = None


def page_html() -> str:
    return _PAGE


def main() -> None:
    load_dotenv(override=False)
    frame = os.getenv("SCALE_FRAME", "").strip()
    if not frame:
        frame = str((Path.cwd() / "data" / "live" / "last_frame.jpg").resolve())
    port = int(os.getenv("DESK_PORT", "8765"))
    host = os.getenv("DESK_HOST", "0.0.0.0").strip() or "0.0.0.0"
    repository = SqliteRepository(os.getenv("DATABASE_PATH", "data/scale.db"))
    desk = Desk(repository, Path(frame), port, host)
    try:
        desk.start()
    except OSError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
    print(f"desk: {desk.url}", flush=True)
    for extra in desk.lan_urls:
        print(f"desk_lan: {extra}", flush=True)
    print("sent_to_internet: no", flush=True)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        desk.stop()


def _handler(repository: SqliteRepository, frame_path: Path) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path in ("/", "/index.html"):
                body = _PAGE.encode("utf-8")
                self._send(200, "text/html; charset=utf-8", body)
                return
            if path == "/frame.jpg":
                self._send_frame()
                return
            if path == "/api/records":
                self._send_json(records_payload(repository))
                return
            if path == "/api/receipt":
                self._send_json(receipt_payload(repository))
                return
            self._send(404, "text/plain; charset=utf-8", b"not found")

        def _send_frame(self) -> None:
            try:
                payload = frame_path.read_bytes()
            except OSError:
                self._send(404, "text/plain; charset=utf-8", b"no frame")
                return
            self._send(200, "image/jpeg", payload)

        def _send_json(self, payload: dict) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self._send(200, "application/json; charset=utf-8", body)

        def _send(self, status: int, content_type: str, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

    return Handler


def _local_ips() -> list[str]:
    found: list[str] = []
    try:
        infos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
    except OSError:
        return found
    for info in infos:
        ip = info[4][0]
        if ip.startswith("127.") or ip in found:
            continue
        found.append(ip)
    return found


if __name__ == "__main__":
    main()
