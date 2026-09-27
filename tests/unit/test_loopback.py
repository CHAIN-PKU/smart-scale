import urllib.request

from scale_host.loopback import LoopbackTransport, main, post_drafts


def test_loopback_records_both_drafts_without_a_price() -> None:
    transport = LoopbackTransport()
    post_drafts(transport, "volcano", "banana.jpg", "banana")
    assert transport.bodies[0]["task"] == "identify"
    assert transport.bodies[0]["provider"] == "volcano"
    assert "price" not in transport.bodies[0]
    assert transport.bodies[1]["task"] == "price_lookup"
    assert transport.bodies[1]["image_path"] is None


def test_loopback_command_does_not_touch_the_network(capsys, monkeypatch) -> None:
    monkeypatch.setenv("MINIMAX_API_KEY", "secret-key")

    def _blocked(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("network opened")

    monkeypatch.setattr(urllib.request, "urlopen", _blocked)
    main()
    output = capsys.readouterr().out
    assert "secret-key" not in output
    assert output.splitlines() == [
        "posted: 2",
        "vision_task: identify",
        "text_task: price_lookup",
        "remote: loopback",
        "sent_to_internet: no",
    ]


def test_key_is_not_copied_into_the_body(monkeypatch) -> None:
    monkeypatch.setenv("VOLCENGINE_API_KEY", "secret-key")
    transport = LoopbackTransport()
    post_drafts(transport, "volcano", "banana.jpg", "banana")
    assert all("secret-key" not in str(body) for body in transport.bodies)
