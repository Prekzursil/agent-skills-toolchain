"""Tests that import the always-packaged module."""

from tst0128pkg.core import add


def test_add():
    assert add(2, 3) == 5


def test_add_zero():
    assert add(0, 0) == 0
