"""Pytest-shaped twins of the in-package runner nodeids."""

from pathlib import Path

import tst0333_crit
from tst0333_crit.core import PACKAGE_DATA_TOKEN, add


def test_add() -> None:
    assert add(2, 3) == 5


def test_token() -> None:
    assert PACKAGE_DATA_TOKEN == "tst0333-packaged"


def test_imported_from_real_file() -> None:
    assert Path(tst0333_crit.__file__).is_file()
