"""The live page reads the saved frame and the local database. No COM port."""

import json
from urllib.request import urlopen

from scale_host.desk import Desk, page_html
from scale_host.storage import SqliteRepository, WeighingSession


def test_page_names_the_live_view_and_the_two_lists() -> None:
    html = page_html()
    assert "OpenMV 实时画面" in html
    assert "称重记录" in html
    assert "清单" in html
    assert "/frame.jpg" in html


def test_local_page_serves_the_frame_records_and_receipt(tmp_path) -> None:
    frame = tmp_path / "last_frame.jpg"
    frame.write_bytes(b"\xff\xd8\xff\xd9")
    repository = SqliteRepository(tmp_path / "scale.db")
    repository.save_session(
        WeighingSession(
            id="banana-1",
            timestamp="2026-10-27T21:00:00",
            weight_g=221.4,
            label="banana",
            price_per_kg=12.0,
            amount_yuan=2.66,
        )
    )
    repository.replace_receipt_lines([("banana", 221.4, 2.66, 12.0)])
    desk = Desk(repository, frame, 0, "127.0.0.1")
    desk.start()
    try:
        page = urlopen(desk.url, timeout=2).read().decode("utf-8")
        picture = urlopen(desk.url + "/frame.jpg", timeout=2).read()
        records = json.loads(urlopen(desk.url + "/api/records", timeout=2).read().decode("utf-8"))
        receipt = json.loads(urlopen(desk.url + "/api/receipt", timeout=2).read().decode("utf-8"))
    finally:
        desk.stop()
    assert "OpenMV 实时画面" in page
    assert picture.startswith(b"\xff\xd8")
    assert records["items"][0]["name"] == "香蕉"
    assert receipt["total"] == 2.66
