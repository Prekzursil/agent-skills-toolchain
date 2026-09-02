"""Planted no-op shapes for TST-0126 (excluded from the live census).

These files are never the live suite. The census must still find each shape
by node id when this directory is scanned.
"""

from __future__ import annotations

import unittest

import pytest


def test_planted_assertionless_tst0126():
    value = 1 + 1
    return {"value": value}


@pytest.mark.skip(reason="TST-0126 planted unconditional skip")
def test_planted_unconditional_skip_tst0126():
    assert False


@pytest.mark.xfail(reason="TST-0126 planted always xfail")
def test_planted_always_xfail_tst0126():
    assert False


@pytest.mark.skipif(True, reason="TST-0126 planted skipif(True)")
def test_planted_skipif_true_tst0126():
    assert False


class PlantedSkipCase(unittest.TestCase):
    @unittest.skip("TST-0126 planted unittest.skip")
    def test_planted_unittest_skip_tst0126(self) -> None:
        self.assertTrue(False)

    @unittest.expectedFailure
    def test_planted_unittest_expected_failure_tst0126(self) -> None:
        self.assertTrue(False)
