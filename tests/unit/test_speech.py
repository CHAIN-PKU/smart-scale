from scale_host.domain import ScaleStatus, WeightReading
from scale_host.fusion import PlacementPricer, Sale
from scale_host.quote import identify_and_price
from scale_host.catalog import TableProductInfo
from scale_host.speech import RecordingSpeaker, announcement, deliver, main
from scale_host.vision import MockVision


def _sale() -> Sale:
    return Sale(
        label="banana",
        confidence=1.0,
        weight_g=326.4,
        price_per_kg=12.0,
        amount_yuan=3.92,
        portion_kcal=297.0,
        portion_carb_g=71.8,
        vision_source="siliconflow",
        info_source="table",
        image_path="data/test_images/openmv_banana.jpg",
    )


def _reading(**overrides: object) -> WeightReading:
    values = {
        "seq": 1,
        "timestamp_ms": 1000,
        "weight_g": 326.4,
        "stable": True,
        "tare_g": 0.0,
        "status": "ok",
        "state": ScaleStatus.WEIGHT_STABLE,
    }
    values.update(overrides)
    return WeightReading(**values)


def test_announcement_is_name_weight_and_price_only() -> None:
    text = announcement(_sale())
    assert text == "香蕉，326.4克，3.92元"
    assert "297" not in text
    assert "71.8" not in text
    assert "千卡" not in text
    assert "12" not in text


def test_a_failed_speaker_keeps_the_price() -> None:
    class _Silent:
        def say(self, text: str) -> None:
            raise RuntimeError("no speaker")

    spoken = deliver(_sale(), _Silent())
    assert spoken == ("香蕉，326.4克，3.92元", False)


def test_creep_back_to_stable_is_not_said_again() -> None:
    pricer = PlacementPricer()
    quote = identify_and_price("banana.jpg", MockVision(), TableProductInfo())
    speaker = RecordingSpeaker()
    first = deliver(pricer.consider(_reading(), quote), speaker)
    deliver(
        pricer.consider(
            _reading(seq=2, weight_g=327.2, stable=False, state=ScaleStatus.WEIGHT_CHANGED),
            quote,
        ),
        speaker,
    )
    again = deliver(
        pricer.consider(_reading(seq=3, weight_g=327.2, state=ScaleStatus.WEIGHT_STABLE), quote),
        speaker,
    )
    assert first == ("香蕉，326.4克，3.92元", True)
    assert again is None
    assert speaker.lines == ["香蕉，326.4克，3.92元"]


def test_speak_command_stays_offline(capsys, monkeypatch) -> None:
    said: list[str] = []

    def _opened(*_args, **_kwargs):
        raise AssertionError("network opened")

    def _say(self, text: str) -> None:
        said.append(text)

    monkeypatch.setattr("urllib.request.urlopen", _opened)
    monkeypatch.setattr("serial.Serial", _opened)
    monkeypatch.setattr("scale_host.speech.WindowsSpeaker.say", _say)
    main()
    lines = capsys.readouterr().out.splitlines()
    assert lines[:4] == [
        "product: banana",
        "weight_g: 326.4",
        "price: 3.92",
        "spoken_line: 香蕉，326.4克，3.92元",
    ]
    assert "spoken: yes" in lines
    assert "nutrition_spoken: no" in lines
    assert lines[-1] == "com_open: no"
    assert said == ["香蕉，326.4克，3.92元"]
