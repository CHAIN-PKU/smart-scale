import asyncio

from scale_host.recognized_sale import main, price_simulated_banana


def test_recognized_banana_uses_the_simulated_weight(monkeypatch) -> None:
    def _opened(*_args, **_kwargs):
        raise AssertionError("network opened")

    def _com_opened(*_args, **_kwargs):
        raise AssertionError("com opened")

    monkeypatch.setattr("urllib.request.urlopen", _opened)
    monkeypatch.setattr("serial.Serial", _com_opened)
    sale = asyncio.run(price_simulated_banana())
    assert sale.label == "banana"
    assert sale.image_path == "data/test_images/openmv_banana.jpg"
    assert sale.vision_source == "siliconflow"
    assert sale.info_source == "table"
    assert sale.weight_g == 326.4
    assert sale.amount_yuan == 3.92
    assert sale.portion_kcal == 297.0
    assert sale.portion_carb_g == 71.8


def test_recognized_sale_command_stays_offline(capsys, monkeypatch) -> None:
    def _opened(*_args, **_kwargs):
        raise AssertionError("network opened")

    def _com_opened(*_args, **_kwargs):
        raise AssertionError("com opened")

    monkeypatch.setattr("urllib.request.urlopen", _opened)
    monkeypatch.setattr("serial.Serial", _com_opened)
    main()
    assert capsys.readouterr().out.splitlines() == [
        "label: banana",
        "image: data/test_images/openmv_banana.jpg",
        "weight_g: 326.4",
        "amount_yuan: 3.92",
        "portion_kcal: 297.0",
        "portion_carb_g: 71.8",
        "sent_to_internet: no",
        "com_open: no",
    ]
