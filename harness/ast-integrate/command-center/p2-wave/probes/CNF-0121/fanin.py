#!/usr/bin/env python3
"""Fan-in entry for completion-predicate condition 9.

The audit and both named probes import evaluate_condition_9 from this module
so condition 9 cannot be a separate audit-only rule.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from shared_reducer import (  # noqa: E402
    CONDITION_9_TEXT,
    CONDITION_INDEX,
    evaluate_condition_9,
    reducer_anchor,
)

__all__ = [
    "CONDITION_9_TEXT",
    "CONDITION_INDEX",
    "evaluate_condition_9",
    "reducer_anchor",
]
