"""Tests that pass the floor explicitly and never read REQUIRED_MIN."""

from subject import accept


def test_explicit_minimum_ignores_module_default():
    assert accept(["a", "b", "c"], minimum=3) is True
    assert accept(["a", "b"], minimum=3) is False
