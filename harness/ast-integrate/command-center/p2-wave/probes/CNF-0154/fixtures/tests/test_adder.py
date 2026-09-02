"""Cited tests for CNF-0154 P0 claims. Import path is src/ next to tests/."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from adder import add, mul  # noqa: E402


def test_add():
    assert add(2, 3) == 5


def test_mul():
    assert mul(2, 3) == 6


if __name__ == "__main__":
    test_add()
    test_mul()
    print("OK")
