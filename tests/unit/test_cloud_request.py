import pytest

from scale_host.cloud_request import main, text_request, vision_request
from scale_host.providers import RemoteCallNotReady
from scale_host.vision import build_vision


def test_vision_request_asks_for_identity_only() -> None:
    request = vision_request("minimax", "banana.jpg")
    assert request.task == "identify"
    assert request.image_path == "banana.jpg"
    assert request.label is None
    assert "price" not in request.model_dump()


def test_text_request_looks_up_a_name_without_an_image() -> None:
    request = text_request("banana")
    assert request.task == "price_lookup"
    assert request.label == "banana"
    assert request.image_path is None


def test_preview_does_not_send_or_print_a_key(capsys, monkeypatch) -> None:
    monkeypatch.setenv("MINIMAX_API_KEY", "secret-key")
    monkeypatch.setenv("VISION_PROVIDER", "minimax")
    main()
    output = capsys.readouterr().out
    assert "secret-key" not in output
    assert output.splitlines() == [
        "vision_task: identify",
        "vision_provider: minimax",
        "vision_image: banana.jpg",
        "text_task: price_lookup",
        "text_label: banana",
        "sent: no",
    ]
    with pytest.raises(RemoteCallNotReady):
        build_vision("minimax").recognize("banana.jpg")
