"""Board checks stay out of the daily test run."""

import pytest

pytestmark = pytest.mark.hardware


@pytest.mark.skip(reason="connect a scale before running hardware tests")
def test_serial_scale_when_a_board_is_attached() -> None:
    """Placeholder until SerialScaleDevice is exercised on a real COM port."""
