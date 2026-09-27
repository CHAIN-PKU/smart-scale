from scale_host.device.dynamics import ScaleDynamics
from scale_host.domain import ScaleStatus


def test_constant_weight_is_stable_after_half_a_second() -> None:
    dynamics = ScaleDynamics()
    dynamics.ready()
    reading = dynamics.observe(0, 326.4)
    for timestamp_ms in range(100, 601, 100):
        reading = dynamics.observe(timestamp_ms, 326.4)
    assert reading.stable is True
    assert reading.state is ScaleStatus.WEIGHT_STABLE


def test_half_gram_swings_do_not_count_as_stable() -> None:
    dynamics = ScaleDynamics()
    dynamics.ready()
    reading = dynamics.observe(0, 20.0)
    for index, grams in enumerate((23.0, 19.0, 24.0, 18.0, 22.0), start=1):
        reading = dynamics.observe(index * 100, grams)
    assert reading.stable is False
    assert reading.state is ScaleStatus.WEIGHT_CHANGED
