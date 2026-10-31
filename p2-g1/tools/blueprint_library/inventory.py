"""Fixed inventory: 87 phase-7 records + 9 delegated protocol ids."""
from __future__ import annotations

PHASE7_RECORDS = tuple(f"P7-{i:03d}" for i in range(1, 88))
DELEGATED_IDS = (
    "oxford",
    "delphi",
    "redblue",
    "jury",
    "fishbowl",
    "ngt",
    "steelman",
    "premortem",
    "hats",
)
