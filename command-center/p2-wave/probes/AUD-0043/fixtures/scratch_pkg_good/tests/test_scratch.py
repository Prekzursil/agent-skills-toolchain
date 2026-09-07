"""Baseline runner: python -m pytest against the SOURCE TREE.

Deliberately imports helper_mod the same way scratch_pkg.main does. This test passes
whether or not helper_mod is later dropped from the packaging manifest, because the
source tree always has the file on disk -- that is exactly the parity gap AUD-0043
measures (CWD-based import success does not prove packaged-import success).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from helper_mod.helper import compute
from scratch_pkg.main import main


def test_compute() -> None:
    assert compute(2, 3) == 5


def test_main_returns_zero() -> None:
    assert main() == 0
