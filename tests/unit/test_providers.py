import pytest

from scale_host.catalog import build_product_info
from scale_host.providers import MissingApiKey, RemoteCallNotReady
from scale_host.vision import build_vision


def test_mock_vision_names_the_item_without_a_price() -> None:
    result = build_vision("mock").recognize("banana.jpg")
    assert result.label == "banana"
    assert result.source == "mock"
    assert "price" not in result.model_dump()


def test_cloud_vision_refuses_to_run_without_a_key(monkeypatch) -> None:
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.delenv("VOLCENGINE_API_KEY", raising=False)
    with pytest.raises(MissingApiKey):
        build_vision("minimax").recognize("banana.jpg")
    with pytest.raises(MissingApiKey):
        build_vision("volcano").recognize("banana.jpg")


def test_cloud_vision_does_not_call_the_network_even_with_a_placeholder(monkeypatch) -> None:
    monkeypatch.setenv("MINIMAX_API_KEY", "placeholder")
    monkeypatch.setenv("VOLCENGINE_API_KEY", "placeholder")
    with pytest.raises(RemoteCallNotReady):
        build_vision("minimax").recognize("banana.jpg")
    with pytest.raises(RemoteCallNotReady):
        build_vision("volcano").recognize("banana.jpg")


def test_text_lookup_needs_its_own_key(monkeypatch) -> None:
    monkeypatch.delenv("TEXT_MODEL_API_KEY", raising=False)
    with pytest.raises(MissingApiKey):
        build_product_info("text").lookup("banana")
    monkeypatch.setenv("TEXT_MODEL_API_KEY", "placeholder")
    with pytest.raises(RemoteCallNotReady):
        build_product_info("text").lookup("banana")


def test_mock_lookup_returns_a_test_price() -> None:
    info = build_product_info("mock").lookup("banana")
    assert info.label == "banana"
    assert info.price_per_kg == 12.0
    assert info.source == "mock"
