"""Empty-parametrize planted tests. AST-only: this file imports pytest.

The suite would collect zero cases for each function, so neither can fail.
"""
import pytest

CASES = []


@pytest.mark.parametrize("case", [])
def test_r04_empty_parametrize(case):
    assert case == 1


@pytest.mark.parametrize("case", CASES)
def test_r06_empty_parametrize_name(case):
    assert case == "never"
