"""Planted default-exercise controls for BLD-0042.

These names are unique so AST call matching cannot collide with shipped APIs.
"""
from __future__ import annotations

import os

PLANTED_NEVER_OMITTED_DEFAULT = 99
PLANTED_EMPTY_TEST_DEFAULT = 5
PLANTED_EXERCISED_DEFAULT = 7
PLANTED_ENV_KEY = "BLD0042_PLANTED_ENV"


def planted_never_omitted(flag: int = PLANTED_NEVER_OMITTED_DEFAULT) -> int:
    return flag


def planted_empty_test_only(flag: int = PLANTED_EMPTY_TEST_DEFAULT) -> int:
    return flag


def planted_exercised(flag: int = PLANTED_EXERCISED_DEFAULT) -> int:
    return flag


def planted_env(flag: str = os.environ.get(PLANTED_ENV_KEY, "from-env")) -> str:
    return flag


def run_planted_assertions(expect_exercised: int = PLANTED_EXERCISED_DEFAULT) -> None:
    """Asserting tests. planted_never_omitted is always passed explicitly."""
    assert planted_never_omitted(flag=1) == 1
    assert planted_never_omitted(flag=2) == 2
    assert planted_exercised() == expect_exercised
    assert planted_env() == os.environ.get(PLANTED_ENV_KEY, "from-env")


def run_empty_test_only() -> None:
    """Omits the default and asserts nothing — must not count as exercise."""
    planted_empty_test_only()
