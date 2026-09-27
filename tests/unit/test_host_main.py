from scale_host.main import main


def test_default_banner_uses_the_simulator(capsys, monkeypatch) -> None:
    monkeypatch.setenv("SCALE_DEVICE", "simulator")
    monkeypatch.setenv("VISION_PROVIDER", "disabled")
    main()
    output = capsys.readouterr().out.splitlines()
    assert output == [
        "Smart Scale Host",
        "device: simulator",
        "vision: disabled",
    ]


def test_unknown_device_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("SCALE_DEVICE", "bluetooth")
    try:
        main()
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("expected SystemExit")
