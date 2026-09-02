"""Independent reviewer: re-run detector control before reading the receipt."""
from __future__ import annotations

from typing import Any

from gate import run_paths
from paths import (
    CLAIMS_CLEAN,
    CLAIMS_ORPHAN,
    GRAPH_CLEAN,
    GRAPH_CYCLE,
    RISKS,
    UNKNOWNS,
)


def evaluate_controls() -> dict[str, Any]:
    orphan = run_paths(GRAPH_CLEAN, CLAIMS_ORPHAN, RISKS, UNKNOWNS)
    cycle = run_paths(GRAPH_CYCLE, CLAIMS_CLEAN, RISKS, UNKNOWNS)
    clean = run_paths(GRAPH_CLEAN, CLAIMS_CLEAN, RISKS, UNKNOWNS)
    return {
        "planted_orphan": orphan.as_dict(),
        "planted_cycle": cycle.as_dict(),
        "clean": clean.as_dict(),
        "verdict": (
            "PASS"
            if orphan.observed == "FIRED"
            and cycle.observed == "FIRED"
            and clean.observed == "SILENT"
            else "FAIL"
        ),
    }
