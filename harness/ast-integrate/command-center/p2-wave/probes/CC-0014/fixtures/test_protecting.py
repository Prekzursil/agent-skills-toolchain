"""Tests that exercise accept() through the module default REQUIRED_MIN."""

from subject import accept


def test_default_floor_accepts_exact_minimum():
    assert accept(["a", "b", "c"]) is True


def test_default_floor_rejects_below_minimum():
    assert accept(["a", "b"]) is False
