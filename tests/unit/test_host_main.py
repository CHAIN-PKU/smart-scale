from scale_host.main import main
from scale_host.device.serial_device import SerialOpenError
from scale_host.storage import SqliteRepository


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


def test_serial_replay_prices_the_stable_line(capsys, monkeypatch, tmp_path) -> None:
    from scale_host.serial_replay import BANANA_LINES, ScriptedPort

    monkeypatch.setenv("SCALE_DEVICE", "serial")
    monkeypatch.setenv("SERIAL_PORT", "COM3")
    monkeypatch.setenv("VISION_PROVIDER", "mock")
    monkeypatch.setenv("PRODUCT_INFO_PROVIDER", "mock")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "scale.db"))
    port = ScriptedPort(BANANA_LINES)
    monkeypatch.setattr("scale_host.main.open_system_port", lambda name: port)
    main()
    lines = capsys.readouterr().out.splitlines()
    assert lines[:10] == [
        "Smart Scale Host",
        "device: serial",
        "vision: mock",
        "product_info: mock",
        "serial_port: COM3",
        "serial_open: ok",
        "label: banana",
        "weight_g: 326.4",
        "price_per_kg: 12.0",
        "amount_yuan: 3.92",
    ]
    assert lines[10].startswith("stored: banana-")
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

