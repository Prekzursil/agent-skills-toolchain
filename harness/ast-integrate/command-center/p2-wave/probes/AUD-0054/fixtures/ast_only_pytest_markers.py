"""Source-only pytest.mark.skipif examples for the AST resolver.

Not collected as tests (no test_* names). Probe 1 must still resolve the
platform predicates on the helper functions if a caller ever names them;
the live scanner only inventories test_* / TestCase methods. Kept here so
the predicate evaluator is exercised against pytest.mark.skipif shape.
"""
from __future__ import annotations

import sys

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="windows-only helper")
def windows_only_helper() -> None:
    return None


@pytest.mark.skipif(sys.platform == "win32", reason="posix-only helper")
def posix_only_helper() -> None:
    return None
