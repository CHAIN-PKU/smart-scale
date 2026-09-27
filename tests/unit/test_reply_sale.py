from scale_host.domain import ScaleStatus, WeightReading
from scale_host.reply_sale import main, sale_from_replies


def _stable() -> WeightReading:
    return WeightReading(
        seq=1,
        timestamp_ms=0,
        weight_g=326.4,
        stable=True,
        tare_g=0.0,
        status="ok",
        state=ScaleStatus.WEIGHT_STABLE,
    )


def test_vision_price_does_not_change_the_amount() -> None:
    sale = sale_from_replies(
        {"label": "banana", "confidence": 0.91, "price_per_kg": 999},
        {"label": "banana", "price_per_kg": 12.0, "summary": "loopback fixture"},
        "banana.jpg",
        _stable(),
    )
    assert sale.price_per_kg == 12.0
    assert sale.amount_yuan == 3.92
    assert sale.vision_source == "loopback"
    assert sale.info_source == "loopback"


def test_reply_sale_command_stays_offline(capsys, monkeypatch) -> None:
    def _blocked(*_args, **_kwargs):
        raise AssertionError("network opened")

    monkeypatch.setattr("urllib.request.urlopen", _blocked)
    main()
    assert capsys.readouterr().out.splitlines() == [
        "label: banana",
        "weight_g: 326.4",
        "price_from_vision: no",
        "price_per_kg: 12.0",
        "amount_yuan: 3.92",
        "source: loopback",
    ]
