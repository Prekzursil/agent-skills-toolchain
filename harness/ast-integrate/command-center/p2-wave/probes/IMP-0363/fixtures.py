"""Shared labelled corpus for IMP-0363 probes.

Hand-computed quotas (max_popularity=10, max_depth=2):
  quota = 1 + floor((max_depth-1) * popularity / max_popularity)
  P-dom 10 -> 2
  P-mid  5 -> 1
  P-weak 2 -> 1
  P-tiny 1 -> 1
  P-proc 0, non-substantive -> not scheduled
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from council.protocol.crossexam import Position  # noqa: E402

PARTICIPANTS = ("A", "B", "C", "D", "E")
MAX_DEPTH = 2
EXPECTED_QUOTA = {
    "P-dom": 2,
    "P-mid": 1,
    "P-weak": 1,
    "P-tiny": 1,
}


def labelled_positions() -> list[Position]:
    return [
        Position("P-dom", "A", 10.0, True, "majority: ship as-is"),
        Position("P-mid", "B", 5.0, True, "ship with rollback"),
        Position("P-weak", "C", 2.0, True, "delay the release"),
        Position("P-tiny", "D", 1.0, True, "rewrite from scratch"),
        Position("P-proc", "E", 0.0, False, "point of order"),
    ]
