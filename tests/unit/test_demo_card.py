import asyncio

from scale_host.demo_card import card_lines, live_sale, main, render_page


def test_card_splits_the_screen_line_from_nutrition(monkeypatch) -> None:
    def _opened(*_args, **_kwargs):
        raise AssertionError("network opened")

    monkeypatch.setattr("urllib.request.urlopen", _opened)
    monkeypatch.setattr("serial.Serial", _opened)
    assert asyncio.run(card_lines()) == [
        "screen:",
        "product: banana",
        "weight_g: 326.4",
        "price: 3.92",
        "frame: live-frame",
        "recognized_when: WEIGHT_STABLE",
        "tft: 3.2 TFT SPI 240×320 v1.0",
        "formal_screen:",
        "香蕉",
        "326.4 克",
        "3.92 元",
        "computer:",
        "portion_kcal: 297.0",
        "portion_carb_g: 71.8",
        "spoken_line: 香蕉，326.4克，3.92元",
        "real_weight_g: 220.3",
        "real_amount_yuan: 2.64",
        "real_portion_kcal: 200.5",
        "real_portion_carb_g: 48.5",
        "sent_to_internet: no",
        "com_open: no",
    ]


def test_page_keeps_the_real_weighing_apart_from_the_simulated_one() -> None:
    sale = asyncio.run(live_sale())
    page = render_page(sale)
    assert sale.image_path == "live-frame"
    assert "正式屏幕" in page
    assert "326.4 克" in page
    assert "3.92 元" in page
    assert "发给板子的 product 仍是 banana" in page
    assert "电脑会念：香蕉，326.4克，3.92元" in page
    assert "热量和碳水不念" in page
    assert "220.3 克" in page
    assert "2.64 元" in page
    real = page.split("真秤已经测过", 1)[1]
    assert "200.5 千卡" in real
    assert "碳水 48.5 克" in real
    formal = page.split("这次模拟的一屏", 1)[0]
    assert "200.5" not in formal
    assert "当前画面" in formal
    assert "3.2 TFT SPI 240×320 v1.0" in formal
    assert "openmv_banana.jpg" not in formal
    assert "演示香蕉" in page
    assert "http://" not in page
    assert "https://" not in page


def test_demo_card_command_stays_offline(capsys, monkeypatch, tmp_path) -> None:
    def _opened(*_args, **_kwargs):
        raise AssertionError("network opened")

    monkeypatch.setattr("urllib.request.urlopen", _opened)
    monkeypatch.setattr("serial.Serial", _opened)
    monkeypatch.setattr("scale_host.demo_card.PAGE_PATH", tmp_path / "defense-card.html")
    main()
    lines = capsys.readouterr().out.splitlines()
    assert lines[:4] == [
        "product: banana",
        "weight_g: 326.4",
        "price: 3.92",
        "portion_kcal: 297.0",
    ]
    assert "spoken_line: 香蕉，326.4克，3.92元" in lines
    assert lines[-1] == "sent_to_internet: no"
