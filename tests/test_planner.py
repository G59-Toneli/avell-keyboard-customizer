"""Unit tests for the pure write-planning logic (no threads, no I/O)."""

from avell_rgb.color import Color
from avell_rgb.controller import OpKind, plan_transition
from avell_rgb.state import BacklightState, Mode

RED = Color(255, 0, 0)
BLUE = Color(0, 0, 255)


def static(color=RED, brightness=4, speed=0x80):
    return BacklightState(Mode.STATIC, color, brightness, speed)


def rainbow(brightness=4, speed=0x80, color=RED):
    return BacklightState(Mode.RAINBOW, color, brightness, speed)


def kinds(previous, target):
    return [op.kind for op in plan_transition(previous, target)]


def test_no_change_plans_nothing():
    assert plan_transition(static(), static()) == []


def test_color_change_writes_only_color():
    assert kinds(static(RED), static(BLUE)) == [OpKind.SET_COLOR]


def test_brightness_change_writes_only_brightness():
    assert kinds(static(brightness=4), static(brightness=2)) == [OpKind.SET_BRIGHTNESS]


def test_turning_off_does_not_write_color():
    # going to brightness 0: no point pushing a color, just the brightness
    assert kinds(static(brightness=4), static(brightness=0)) == [OpKind.SET_BRIGHTNESS]


def test_entering_rainbow_sets_speed_brightness_then_enables():
    assert kinds(static(), rainbow()) == [
        OpKind.SET_RAINBOW_SPEED, OpKind.SET_BRIGHTNESS, OpKind.ENABLE_RAINBOW,
    ]


def test_changing_speed_while_cycling_writes_only_speed():
    assert kinds(rainbow(speed=0x80), rainbow(speed=0x20)) == [OpKind.SET_RAINBOW_SPEED]


def test_leaving_rainbow_disables_then_restores_color_and_brightness():
    assert kinds(rainbow(), static(BLUE)) == [
        OpKind.DISABLE_RAINBOW, OpKind.SET_COLOR, OpKind.SET_BRIGHTNESS,
    ]


def test_speed_value_is_carried_through():
    ops = plan_transition(static(), rainbow(speed=0xD0))
    speed_op = next(op for op in ops if op.kind is OpKind.SET_RAINBOW_SPEED)
    assert speed_op.value == 0xD0
