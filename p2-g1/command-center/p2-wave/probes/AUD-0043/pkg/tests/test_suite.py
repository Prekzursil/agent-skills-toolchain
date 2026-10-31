"""Source-tree pytest suite. Imports core and extra from PYTHONPATH=src."""

from aud0043_extra import MARKER, marker
from aud0043_pkg.core import ping


def test_core_ping() -> None:
    assert ping() == "ok"


def test_extra_marker() -> None:
    assert MARKER == "AUD0043-EXTRA"
    assert marker() == "AUD0043-EXTRA"
