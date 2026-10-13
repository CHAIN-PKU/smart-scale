import json

import pytest

from scale_host.providers import MissingApiKey
from scale_host.vision import build_vision, label_from_reply


def test_json_reply_keeps_the_name_and_drops_price_and_nutrition() -> None:
    label = label_from_reply('{"label":"banana","price":999,"kcal":90,"carb":23}')
    assert label == "banana"
    assert "999" not in label
    assert "90" not in label


def test_plain_reply_keeps_the_name_before_the_price() -> None:
    assert label_from_reply("香蕉，每千克12元，热量90千卡") == "香蕉"


def test_siliconflow_posts_the_photo_and_returns_only_the_name(tmp_path, monkeypatch) -> None:
    image = tmp_path / "banana.jpg"
    image.write_bytes(b"not-a-real-photo")
    monkeypatch.setenv("SILICONFLOW_API_KEY", "test-key")
    monkeypatch.setenv("SILICONFLOW_VISION_MODEL", "zai-org/GLM-5.3-Flash")
    monkeypatch.setenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
    seen: dict[str, object] = {}

    class _Response:
        def read(self) -> bytes:
            body = {
                "choices": [
                    {
                        "message": {
                            "content": '{"label":"banana","price":999,"kcal":90,"carb":23}'
                        }
                    }
                ]
            }
            return json.dumps(body).encode("utf-8")

        def __enter__(self) -> "_Response":
            return self

        def __exit__(self, *_args: object) -> bool:
            return False

    def _opened(request, timeout=0):
        seen["url"] = request.full_url
        seen["timeout"] = timeout
        seen["auth"] = request.get_header("Authorization")
        seen["body"] = json.loads(request.data.decode("utf-8"))
        return _Response()

    monkeypatch.setattr("urllib.request.urlopen", _opened)
    result = build_vision("siliconflow").recognize(str(image))
    assert result.label == "banana"
    assert result.source == "siliconflow"
    assert "price" not in result.model_dump()
    assert seen["url"] == "https://api.siliconflow.cn/v1/chat/completions"
    assert seen["auth"] == "Bearer test-key"
    assert seen["body"]["model"] == "zai-org/GLM-5.3-Flash"
    assert "999" not in json.dumps(result.model_dump())


def test_siliconflow_does_not_call_without_a_key(monkeypatch) -> None:
    monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)

    def _opened(*_args, **_kwargs):
        raise AssertionError("network opened")

    monkeypatch.setattr("urllib.request.urlopen", _opened)
    with pytest.raises(MissingApiKey):
        build_vision("siliconflow").recognize("banana.jpg")
