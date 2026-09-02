"""Planted oracle-strength controls for BLD-0040.

test_no_crash_only asserts only `is not None` (must grade NO-CRASH-ONLY).
test_exact_value asserts the computed sum (must grade EXACT-VALUE).
"""
from __future__ import annotations

from subject import compute_score


def test_no_crash_only():
    result = compute_score([1, 2, 3])
    assert result is not None


def test_exact_value():
    result = compute_score([1, 2, 3])
    assert result == 6
