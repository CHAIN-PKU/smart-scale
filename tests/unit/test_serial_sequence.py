import json

from scale_host.serial_sequence import main


def test_sequence_prices_only_the_stable_line(capsys, monkeypatch) -> None:
    monkeypatch.setenv("VISION_PROVIDER", "mock")
    monkeypatch.setenv("PRODUCT_INFO_PROVIDER", "mock")
    main()
    assert capsys.readouterr().out.splitlines() == [
        "skipped: 5",
        "label: banana",
        "weight_g: 326.4",
        "price_per_kg: 12.0",
        "amount_yuan: 3.92",
        "stored: banana-sequence",
    ]


def test_display_uses_the_stable_weight(monkeypatch) -> None:
    import asyncio
    import tempfile
    from pathlib import Path

    from scale_host.pipeline import DEMO_TIMESTAMP, price_open_port
    from scale_host.serial_replay import ScriptedPort
    from scale_host.serial_sequence import SEQUENCE_SESSION_ID, rising_lines
    from scale_host.storage import SqliteRepository

    monkeypatch.setenv("VISION_PROVIDER", "mock")
    monkeypatch.setenv("PRODUCT_INFO_PROVIDER", "mock")
    port = ScriptedPort(rising_lines())
    with tempfile.TemporaryDirectory() as folder:
        repository = SqliteRepository(Path(folder) / "scale.db")
        _session, skipped = asyncio.run(
            price_open_port(
                port,
                repository,
                session_id=SEQUENCE_SESSION_ID,
                timestamp=DEMO_TIMESTAMP,
            )
        )
    sent = json.loads(port.outgoing[0].decode("utf-8"))
    assert skipped == 5
    assert sent["weight_g"] == 326.4
    assert sent["price"] == 3.92
