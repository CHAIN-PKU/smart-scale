import json

from scale_host.display_line import DEMO_REQUEST_ID, display_line, main
from scale_host.protocol.messages import parse_line
from scale_host.reply_sale import sale_from_replies


def _sale():
    from scale_host.domain import ScaleStatus, WeightReading

    reading = WeightReading(
        seq=1,
        timestamp_ms=0,
        weight_g=326.4,
        stable=True,
        tare_g=0.0,
        status="ok",
        state=ScaleStatus.WEIGHT_STABLE,
    )
    return sale_from_replies(
        {"label": "banana", "confidence": 0.91, "price_per_kg": 999},
        {"label": "banana", "price_per_kg": 12.0, "summary": "loopback fixture"},
        "banana.jpg",
        reading,
    )


def test_display_line_uses_the_text_price() -> None:
    line = display_line(_sale(), DEMO_REQUEST_ID)
    assert "999" not in line
    message = parse_line(line)
    assert message is not None
    assert message.type == "display_result"
    assert message.product == "banana"
    assert message.weight_g == 326.4
    assert message.price == 3.92
    assert message.request_id == "r_001"


def test_display_command_prints_one_protocol_line(capsys, monkeypatch) -> None:
    def _blocked(*_args, **_kwargs):
        raise AssertionError("network opened")

    monkeypatch.setattr("urllib.request.urlopen", _blocked)
    main()
    text = capsys.readouterr().out.strip()
    payload = json.loads(text)
    assert payload == {
        "v": 1,
        "type": "display_result",
        "request_id": "r_001",
        "product": "banana",
        "weight_g": 326.4,
        "price": 3.92,
    }
