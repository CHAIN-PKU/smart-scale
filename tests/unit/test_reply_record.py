from pathlib import Path

from scale_host.reply_record import REPLY_SESSION_ID, main, record_reply_sale
from scale_host.storage import SqliteRepository


def test_stored_amount_matches_the_display_price(tmp_path: Path) -> None:
    repository = SqliteRepository(tmp_path / "scale.db")
    stored_amount, display_price = record_reply_sale(repository)
    stored = repository.get_session(REPLY_SESSION_ID)
    assert stored is not None
    assert stored.label == "banana"
    assert stored.weight_g == 326.4
    assert stored.price_per_kg == 12.0
    assert stored_amount == 3.92
    assert display_price == 3.92
    assert stored_amount == display_price


def test_reply_record_command_stays_offline(capsys, monkeypatch) -> None:
    def _blocked(*_args, **_kwargs):
        raise AssertionError("network opened")

    monkeypatch.setattr("urllib.request.urlopen", _blocked)
    main()
    text = capsys.readouterr().out
    assert "999" not in text
    assert text.splitlines() == [
        f"stored: {REPLY_SESSION_ID}",
        "amount_yuan: 3.92",
        "display_price: 3.92",
        "same_amount: yes",
    ]
