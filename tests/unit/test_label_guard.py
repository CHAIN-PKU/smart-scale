from scale_host.label_guard import main, mismatched_labels
from scale_host.reply_sale import LabelMismatch, sale_from_replies


def test_disagreement_is_not_priced() -> None:
    mismatch = mismatched_labels()
    assert isinstance(mismatch, LabelMismatch)
    assert mismatch.vision_label == "banana"
    assert mismatch.text_label == "apple"
    assert str(mismatch) == "label mismatch"


def test_matching_labels_still_price() -> None:
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
    sale = sale_from_replies(
        {"label": "banana", "confidence": 0.91, "price_per_kg": 999},
        {"label": "banana", "price_per_kg": 12.0, "summary": "loopback fixture"},
        "banana.jpg",
        reading,
    )
    assert sale.label == "banana"
    assert sale.price_per_kg == 12.0
    assert sale.amount_yuan == 3.92


def test_label_guard_command_stays_offline(capsys, monkeypatch) -> None:
    def _blocked(*_args, **_kwargs):
        raise AssertionError("network opened")

    monkeypatch.setattr("urllib.request.urlopen", _blocked)
    main()
    text = capsys.readouterr().out
    assert "8.0" not in text
    assert "999" not in text
    assert text.splitlines() == [
        "priced: no",
        "reason: label mismatch",
        "vision_label: banana",
        "text_label: apple",
        "display_sent: no",
        "sent_to_internet: no",
    ]
