"""Test-only import of the same declared-dev package.

Probe 2 MUST NOT flag this: tests are outside the shippable package set.
"""

import pytest


def test_control_marker() -> None:
    assert pytest is not None
