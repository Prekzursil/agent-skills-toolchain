"""AUD-0057 WEAK suite — never exercises planted_unexercised default.

Always passes ``threshold`` explicitly. Mutating PLANTED_UNEXERCISED_DEFAULT
must leave this suite GREEN (the hole the census exists to catch).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from planted_defaults import planted_unexercised  # noqa: E402


def test_planted_unexercised_always_explicit():
    assert planted_unexercised(2048, threshold=512) is True
    assert planted_unexercised(100, threshold=512) is False
