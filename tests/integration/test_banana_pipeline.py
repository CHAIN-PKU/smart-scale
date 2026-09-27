from scale_host.pipeline import DEMO_SESSION_ID, DEMO_TIMESTAMP, main, record_stable_sale
from scale_host.storage import SqliteRepository


async def test_banana_sale_is_stored_and_read_back(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VISION_PROVIDER", "mock")
    monkeypatch.setenv("PRODUCT_INFO_PROVIDER", "mock")
    repository = SqliteRepository(tmp_path / "scale.db")
    await record_stable_sale(
        repository,
        session_id=DEMO_SESSION_ID,
        timestamp=DEMO_TIMESTAMP,
    )
    stored = repository.get_session(DEMO_SESSION_ID)
    assert stored is not None
    assert stored.label == "banana"
    assert stored.weight_g == 326.4
    assert stored.price_per_kg == 12.0
    assert stored.amount_yuan == 3.92
    assert stored.image_path == "banana.jpg"
    assert stored.model_name == "mock"


def test_record_command_prints_the_stored_sale(capsys, monkeypatch) -> None:
    monkeypatch.setenv("VISION_PROVIDER", "mock")
    monkeypatch.setenv("PRODUCT_INFO_PROVIDER", "mock")
    main()
    assert capsys.readouterr().out.splitlines() == [
        "label: banana",
        "weight_g: 326.4",
        "price_per_kg: 12.0",
        "amount_yuan: 3.92",
        "stored: banana-demo",
    ]
