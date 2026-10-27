from scale_host.main import main
from scale_host.device.serial_device import SerialOpenError
from scale_host.storage import SqliteRepository

import pytest


def test_default_banner_uses_the_simulator(capsys, monkeypatch) -> None:
    monkeypatch.setenv("SCALE_DEVICE", "simulator")
    monkeypatch.setenv("VISION_PROVIDER", "disabled")
    monkeypatch.setenv("PRODUCT_INFO_PROVIDER", "disabled")
    main()
    output = capsys.readouterr().out.splitlines()
    assert output == [
        "Smart Scale Host",
        "device: simulator",
        "vision: disabled",
        "product_info: disabled",
    ]


def test_unknown_device_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("SCALE_DEVICE", "bluetooth")
    try:
        main()
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("expected SystemExit")


def test_startup_prints_the_stored_banana_sale(capsys, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SCALE_DEVICE", "simulator")
    monkeypatch.setenv("VISION_PROVIDER", "mock")
    monkeypatch.setenv("PRODUCT_INFO_PROVIDER", "mock")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "scale.db"))
    main()
    lines = capsys.readouterr().out.splitlines()
    assert lines[:8] == [
        "Smart Scale Host",
        "device: simulator",
        "vision: mock",
        "product_info: mock",
        "label: banana",
        "weight_g: 326.4",
        "price_per_kg: 12.0",
        "amount_yuan: 3.92",
    ]
    assert lines[8].startswith("stored: banana-")
    stored = SqliteRepository(tmp_path / "scale.db").get_session(lines[8].split(": ", 1)[1])
    assert stored is not None
    assert stored.amount_yuan == 3.92


def test_table_startup_prints_portion_nutrition(capsys, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SCALE_DEVICE", "simulator")
    monkeypatch.setenv("VISION_PROVIDER", "mock")
    monkeypatch.setenv("PRODUCT_INFO_PROVIDER", "table")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "scale.db"))
    main()
    lines = capsys.readouterr().out.splitlines()
    assert lines[4:11] == [
        "label: banana",
        "weight_g: 326.4",
        "price_per_kg: 12.0",
        "amount_yuan: 3.92",
        "portion_kcal: 297.0",
        "portion_carb_g: 71.8",
        "portion_fiber_g: 3.9",
    ]
    stored = SqliteRepository(tmp_path / "scale.db").get_session(lines[11].split(": ", 1)[1])
    assert stored is not None
    assert stored.portion_kcal == 297.0
    assert stored.portion_carb_g == 71.8
    assert stored.portion_fiber_g == 3.9


def test_serial_without_a_port_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("SCALE_DEVICE", "serial")
    monkeypatch.setenv("SERIAL_PORT", "")
    monkeypatch.setenv("VISION_PROVIDER", "mock")
    try:
        main()
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("expected SystemExit")


def test_serial_without_this_placement_photo_does_not_invent_a_sale(capsys, monkeypatch, tmp_path) -> None:
    from scale_host.serial_replay import BANANA_LINES, ScriptedPort

    monkeypatch.setenv("SCALE_DEVICE", "serial")
    monkeypatch.setenv("SERIAL_PORT", "COM3")
    monkeypatch.setenv("VISION_PROVIDER", "mock")
    monkeypatch.setenv("PRODUCT_INFO_PROVIDER", "mock")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "scale.db"))
    monkeypatch.delenv("SCALE_FRAME", raising=False)
    port = ScriptedPort(BANANA_LINES)
    monkeypatch.setattr("scale_host.main.open_system_port", lambda name: port)
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert "no stable weight" in captured.err
    assert "label:" not in captured.out
    assert port.closed is True


def test_serial_prices_this_photo_with_the_scale_weight(capsys, monkeypatch, tmp_path) -> None:
    from scale_host.serial_replay import BANANA_LINES, ScriptedPort

    photo = tmp_path / "placement.jpg"
    photo.write_bytes(b"jpg")
    monkeypatch.setenv("SCALE_DEVICE", "serial")
    monkeypatch.setenv("SERIAL_PORT", "COM3")
    monkeypatch.setenv("VISION_PROVIDER", "mock")
    monkeypatch.setenv("PRODUCT_INFO_PROVIDER", "table")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "scale.db"))
    monkeypatch.setenv("SCALE_FRAME", str(photo))
    port = ScriptedPort(BANANA_LINES)
    monkeypatch.setattr("scale_host.main.open_system_port", lambda name: port)
    main()
    lines = capsys.readouterr().out.splitlines()
    assert "weight_g: 326.4" in lines
    assert "amount_yuan: 3.92" in lines
    assert "portion_fiber_g: 3.9" in lines
    stored_line = next(line for line in lines if line.startswith("stored: "))
    stored = SqliteRepository(tmp_path / "scale.db").get_session(stored_line.split(": ", 1)[1])
    assert stored is not None
    assert stored.image_path == str(photo)
    assert port.closed is True


def test_serial_open_failure_stops_the_host(monkeypatch, capsys) -> None:
    monkeypatch.setenv("SCALE_DEVICE", "serial")
    monkeypatch.setenv("SERIAL_PORT", "COM3")
    monkeypatch.setenv("VISION_PROVIDER", "disabled")

    def _fail(name: str) -> None:
        raise SerialOpenError(name)

    monkeypatch.setattr("scale_host.main.open_system_port", _fail)
    try:
        main()
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("expected SystemExit")
    assert "cannot open serial port: COM3" in capsys.readouterr().err

