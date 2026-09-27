from scale_host.response_parse import main, parse_identify, parse_price


def test_vision_reply_drops_a_price() -> None:
    recognition = parse_identify(
        {"label": "banana", "confidence": 0.91, "price_per_kg": 999},
        "banana.jpg",
    )
    assert recognition.label == "banana"
    assert recognition.confidence == 0.91
    assert recognition.source == "loopback"
    assert "price" not in recognition.model_dump()


def test_text_reply_keeps_the_unit_price() -> None:
    info = parse_price(
        {"label": "banana", "price_per_kg": 12, "summary": "loopback fixture"}
    )
    assert info.price_per_kg == 12.0
    assert info.source == "loopback"
    assert info.summary == "loopback fixture"


def test_parse_command_prints_the_split(capsys) -> None:
    main()
    assert capsys.readouterr().out.splitlines() == [
        "label: banana",
        "confidence: 0.91",
        "price_from_vision: no",
        "text_price_per_kg: 12.0",
        "source: loopback",
    ]
