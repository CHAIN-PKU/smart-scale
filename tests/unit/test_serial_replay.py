import json

from scale_host.serial_replay import main


def test_replay_prints_the_priced_line_and_writes_display(capsys, monkeypatch) -> None:
    monkeypatch.setenv("VISION_PROVIDER", "mock")
    monkeypatch.setenv("PRODUCT_INFO_PROVIDER", "mock")
    main()
    lines = capsys.readouterr().out.splitlines()
    assert lines == [
        "label: banana",
        "weight_g: 326.4",
        "price_per_kg: 12.0",
        "amount_yuan: 3.92",
        "stored: banana-replay",
    ]


def test_replay_sends_display_result(monkeypatch) -> None:
    import asyncio
    import tempfile
    from pathlib import Path

    from scale_host.pipeline import DEMO_TIMESTAMP, price_open_port
    from scale_host.serial_replay import BANANA_LINES, REPLAY_SESSION_ID, ScriptedPort
    from scale_host.storage import SqliteRepository

    monkeypatch.setenv("VISION_PROVIDER", "mock")
    monkeypatch.setenv("PRODUCT_INFO_PROVIDER", "mock")
    port = ScriptedPort(BANANA_LINES)
    with tempfile.TemporaryDirectory() as folder:
        repository = SqliteRepository(Path(folder) / "scale.db")
        asyncio.run(
            price_open_port(
                port,
                repository,
                session_id=REPLAY_SESSION_ID,
                timestamp=DEMO_TIMESTAMP,
            )
        )
    sent = json.loads(port.outgoing[0].decode("utf-8"))
    assert sent["type"] == "display_result"
    assert sent["product"] == "banana"
    assert sent["weight_g"] == 326.4
    assert sent["price"] == 3.92
