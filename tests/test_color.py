import pytest

from avell_rgb.color import Color


def test_rejects_out_of_range_channel():
    with pytest.raises(ValueError):
        Color(256, 0, 0)
    with pytest.raises(ValueError):
        Color(0, -1, 0)


def test_hex_roundtrip():
    assert Color(255, 128, 0).hex == "#FF8000"
    assert Color.from_hex("#ff8000") == Color(255, 128, 0)
    assert Color.from_hex("3D45F0") == Color(0x3D, 0x45, 0xF0)


def test_from_hex_rejects_bad_length():
    with pytest.raises(ValueError):
        Color.from_hex("#fff")


def test_named_primaries_from_hsv():
    assert Color.from_hsv(0, 1, 1) == Color(255, 0, 0)
    assert Color.from_hsv(120, 1, 1) == Color(0, 255, 0)
    assert Color.from_hsv(240, 1, 1) == Color(0, 0, 255)


@pytest.mark.parametrize("color", [Color(255, 0, 0), Color(10, 200, 130), Color(61, 69, 240)])
def test_hsv_roundtrip_is_stable(color):
    hue, sat, val = color.to_hsv()
    assert Color.from_hsv(hue, sat, val) == color


def test_from_triplet_clamps():
    assert Color.from_triplet((300, -5, 128)) == Color(255, 0, 128)


def test_is_black():
    assert Color(0, 0, 0).is_black
    assert not Color(0, 0, 1).is_black


def test_color_is_hashable_and_immutable():
    assert len({Color(1, 2, 3), Color(1, 2, 3)}) == 1
    with pytest.raises(AttributeError):
        Color(1, 2, 3).red = 9  # frozen
