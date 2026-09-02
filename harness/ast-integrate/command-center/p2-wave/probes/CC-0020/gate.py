"""Probe-local import shim for the shipped CC-0020 gate."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools" / "command-center"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from mechanism_dedup import (  # noqa: E402,F401
    EMB_FIRE,
    LEX_FIRE,
    compare,
    compare_records,
    cosine,
    caught,
    embed,
    embed_cosine,
    error_direction,
    false_merge,
    jaccard,
    pairwise,
    record_text,
    token_set,
    verdict,
)
