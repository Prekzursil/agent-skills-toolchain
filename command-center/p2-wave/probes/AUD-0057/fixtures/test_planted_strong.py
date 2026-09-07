"""AUD-0057 STRONG suite — exercises planted_exercised default.

Omits ``threshold`` so the signature default is live. Mutating
PLANTED_EXERCISED_DEFAULT must turn this suite RED (both-states control).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from planted_defaults import planted_exercised  # noqa: E402


def test_planted_exercised_uses_default():
    # Literal bounds pin the default itself (not the imported symbol).
    assert planted_exercised(64) is True
    assert planted_exercised(63) is False
    assert planted_exercised(65) is True


def test_planted_exercised_explicit_still_works():
    assert planted_exercised(32, threshold=32) is True
    assert planted_exercised(31, threshold=32) is False
