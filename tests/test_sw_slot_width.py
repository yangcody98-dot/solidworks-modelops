"""Regression for the real 42x14 slot that was previously created 35x7."""
import math
from types import SimpleNamespace
import pytest
from scripts.sw_part import sketch_slot


@pytest.mark.parametrize('radius', [0.001, 0.007, 0.008])
def test_slot_radius_converts_to_sdk_width_and_retains_center_length(radius):
    captured = []
    slot = object()
    model = SimpleNamespace(SketchManager=SimpleNamespace(
        CreateSketchSlot=lambda *args: captured.append(args) or slot))
    assert sketch_slot(model, -0.014, 0, 0.014, 0, radius) is slot
    args = captured[0]
    assert args[0] == 0  # straight slot
    assert args[1] == 0  # CenterCenter, integer enum, never the radius
    assert args[2] == pytest.approx(2 * radius)  # full width in metres
    center_length = math.dist(args[3:6], args[6:9])
    assert center_length == pytest.approx(0.028)
    if radius == 0.007:
        assert center_length + args[2] == pytest.approx(0.042)
        assert center_length * args[2] + math.pi * radius**2 == pytest.approx((28*14+49*math.pi)*1e-6)
