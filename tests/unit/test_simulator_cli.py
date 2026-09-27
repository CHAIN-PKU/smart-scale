from simulator.__main__ import main


def test_banana_scenario_prints_the_ramp(capsys) -> None:
    main(["--scenario", "banana"])
    assert capsys.readouterr().out.splitlines() == [
        "0 g",
        "12 g",
        "145 g",
        "310 g",
        "326 g",
        "326.4 g",
        "326.4 g STABLE",
    ]


def test_unknown_scenario_exits(capsys) -> None:
    try:
        main(["--scenario", "missing"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("expected SystemExit")
    assert "unknown scenario" in capsys.readouterr().err
