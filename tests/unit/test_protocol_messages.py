import pytest

from scale_host.protocol import ProtocolError, parse_line

WEIGHT = (
    '{"v":1,"type":"weight","seq":182,"timestamp_ms":192839,'
    '"weight_g":326.4,"stable":true,"tare_g":12.7,"status":"ok"}'
)


def test_valid_weight_status_ack_command_and_display() -> None:
    weight = parse_line(WEIGHT)
    assert weight is not None
    assert weight.type == "weight"
    assert weight.weight_g == 326.4
    assert weight.stable is True

    status = parse_line('{"v":1,"type":"status","seq":2,"timestamp_ms":40,"state":"READY"}')
    assert status is not None
    assert status.state == "READY"

    ack = parse_line(
        '{"v":1,"type":"ack","seq":183,"timestamp_ms":193100,"command":"tare","status":"ok"}'
    )
    assert ack is not None
    assert ack.status == "ok"

    command = parse_line('{"v":1,"type":"command","command":"tare"}')
    assert command is not None
    assert command.command == "tare"

    display = parse_line(
        '{"v":1,"type":"display_result","request_id":"r_001",'
        '"product":"banana","weight_g":326.4,"price":3.92}'
    )
    assert display is not None
    assert display.product == "banana"
    assert display.price == 3.92
    assert display.portion_kcal is None

    nutrition = parse_line(
        '{"v":1,"type":"display_result","request_id":"r_002","product":"banana",'
        '"weight_g":326.4,"price":3.92,"portion_kcal":297,"portion_carb_g":71.8,'
        '"portion_fiber_g":3.9}'
    )
    assert nutrition is not None
    assert nutrition.portion_fiber_g == 3.9

    for name in ("save", "receipt", "clear"):
        command = parse_line('{"v":1,"type":"command","command":"%s"}' % name)
        assert command is not None
        assert command.command == name

    saved = parse_line(
        '{"v":1,"type":"ack","seq":0,"timestamp_ms":0,"command":"save","status":"error"}'
    )
    assert saved is not None
    assert saved.status == "error"

    receipt = parse_line(
        '{"v":1,"type":"receipt_result","items":[{"n":1,"product":"banana",'
        '"price_per_kg":12,"weight_g":326.4,"price":3.92}],"total":3.92}'
    )
    assert receipt is not None
    assert receipt.total == 3.92
    assert receipt.items[0].n == 1
    assert receipt.items[0].product == "banana"
    assert receipt.items[0].price_per_kg == 12


def test_blank_line_is_ignored() -> None:
    assert parse_line("   ") is None


def test_extra_field_is_ignored() -> None:
    message = parse_line(
        '{"v":1,"type":"weight","seq":1,"timestamp_ms":0,"weight_g":1,'
        '"stable":false,"tare_g":0,"status":"ok","note":"ignore-me"}'
    )
    assert message is not None
    assert not hasattr(message, "note")


@pytest.mark.parametrize(
    ("line", "reason"),
    [
        ("123.45", "not_object"),
        ("{", "malformed"),
        ("[]", "not_object"),
        ('{"type":"weight"}', "missing_field"),
        (
            '{"v":"1","type":"weight","seq":1,"timestamp_ms":0,"weight_g":1,'
            '"stable":true,"tare_g":0,"status":"ok"}',
            "bad_version",
        ),
        (
            '{"v":2,"type":"weight","seq":1,"timestamp_ms":0,"weight_g":1,'
            '"stable":true,"tare_g":0,"status":"ok"}',
            "bad_version",
        ),
        ('{"v":1,"type":"picture"}', "unknown_type"),
        (
            '{"v":1,"type":"weight","seq":1,"timestamp_ms":0,"weight_g":"326.4",'
            '"stable":true,"tare_g":0,"status":"ok"}',
            "bad_field",
        ),
        ('{"v":1,"type":"command","command":"reboot"}', "bad_field"),
        (WEIGHT + WEIGHT, "malformed"),
    ],
)
def test_rejects_bad_lines(line: str, reason: str) -> None:
    with pytest.raises(ProtocolError) as caught:
        parse_line(line)
    assert caught.value.reason == reason
