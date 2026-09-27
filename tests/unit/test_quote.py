import pytest

from scale_host.catalog import MockProductInfo, ProductInfo
from scale_host.domain import ProductRecognition
from scale_host.quote import identify_and_price, main
from scale_host.vision import MockVision


class _NamedVision:
    name = "named"

    def recognize(self, image_path: str) -> ProductRecognition:
        return ProductRecognition(
            label="banana",
            confidence=0.8,
            source="named",
            image_id=image_path,
        )


class _RecordingInfo:
    name = "recording"

    def __init__(self) -> None:
        self.seen = ""

    def lookup(self, label: str) -> ProductInfo:
        self.seen = label
        return ProductInfo(
            label=label,
            price_per_kg=12.0,
            summary="looked up from the recognized name",
            source="recording",
        )


def test_price_lookup_uses_the_recognized_name() -> None:
    info = _RecordingInfo()
    quote = identify_and_price("banana.jpg", _NamedVision(), info)
    assert info.seen == "banana"
    assert quote.label == "banana"
    assert quote.price_per_kg == 12.0
    assert quote.vision_source == "named"
    assert quote.info_source == "recording"


def test_mock_quote_command_prints_banana_unit_price(capsys, monkeypatch) -> None:
    monkeypatch.setenv("VISION_PROVIDER", "mock")
    monkeypatch.setenv("PRODUCT_INFO_PROVIDER", "mock")
    main()
    assert capsys.readouterr().out.splitlines() == [
        "label: banana",
        "price_per_kg: 12.0",
    ]


def test_quote_command_stops_when_providers_are_disabled(monkeypatch) -> None:
    monkeypatch.setenv("VISION_PROVIDER", "disabled")
    monkeypatch.setenv("PRODUCT_INFO_PROVIDER", "disabled")
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2


def test_builtin_mocks_quote_banana() -> None:
    quote = identify_and_price("banana.jpg", MockVision(), MockProductInfo())
    assert quote.label == "banana"
    assert quote.price_per_kg == 12.0
