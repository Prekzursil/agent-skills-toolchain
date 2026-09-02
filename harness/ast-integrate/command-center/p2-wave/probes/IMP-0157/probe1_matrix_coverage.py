#!/usr/bin/env python3
"""Probe 1: licence matrix is exhaustive over the COMPUTED observed set.

Signal 1 of IMP-0157: (observed canonical ∪ unidentified spellings) vs axes.
Both-states: a planted SPDX id that is not on the lattice makes exhaustive=False;
removing it restores exhaustive=True. 'unlicensed' must map to UNKNOWN, not MIT.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from workflow_foundry import licence_matrix as lm  # noqa: E402
from workflow_foundry.registry import observed_raw  # noqa: E402


def _fail(msg: str, payload: dict | None = None) -> int:
    if payload:
        print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"FAIL:IMP-0157-probe1 {msg}")
    return 1


def main() -> int:
    raw = observed_raw(REPO)
    gap = lm.coverage_gap(raw)
    axes = lm.matrix_axes()
    cells = list(lm.iter_cells())
    n = len(axes)
    if len(cells) != n * n:
        return _fail(
            f"matrix not square: cells={len(cells)} axes={n}",
            {"cells": len(cells), "axes": n},
        )

    # Both-states plant: a real SPDX identifier the lattice does not list.
    planted = "Python-2.0"
    planted_canon = lm.canonical_licence(planted)
    if planted_canon != "UNKNOWN" and planted in axes:
        return _fail("plant is already on the matrix; control cannot fire")
    dirty = lm.coverage_gap(list(raw) + [planted])
    if dirty["exhaustive"]:
        return _fail(
            "planted Python-2.0 did not open a coverage hole (control silent)",
            dirty,
        )
    if planted not in dirty["unidentified_spellings"] and planted_canon not in dirty["missing_from_matrix"]:
        return _fail("planted id not reported in gap", dirty)

    clean = lm.coverage_gap(raw)
    if not clean["exhaustive"]:
        return _fail("live observed set is not covered by the matrix", clean)

    # Fail-closed: unlicensed is UNKNOWN, never MIT.
    u = lm.canonical_licence("unlicensed")
    if u != "UNKNOWN":
        return _fail(f"unlicensed canonicalized to {u!r}, not UNKNOWN")
    mit_pair = lm.solve_pair("MIT", "MIT")
    if not mit_pair.allowed or mit_pair.result_licence != "MIT":
        return _fail("MIT+MIT should be allowed as MIT", mit_pair.as_dict())

    unknown_mit = lm.solve_pair("UNKNOWN", "MIT")
    if unknown_mit.allowed:
        return _fail("UNKNOWN+MIT must be refused (fail-closed)", unknown_mit.as_dict())

    report = {
        "probe": "probe1_matrix_coverage",
        "exhaustive": True,
        "observed_count": clean["observed_count"],
        "axis_count": clean["axis_count"],
        "cell_count": len(cells),
        "observed_canonical": clean["observed_canonical"],
        "missing_from_matrix": clean["missing_from_matrix"],
        "unidentified_spellings": clean["unidentified_spellings"],
        "plant_python_2_0_opened_hole": True,
        "unlicensed_is_unknown": True,
        "unknown_plus_mit_refused": True,
        "set_difference_empty": True,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(
        f"exhaustive observed={clean['observed_count']} axes={clean['axis_count']} "
        f"cells={len(cells)} plant_fired=True"
    )
    print("SUCCESS:IMP-0157-probe1 matrix exhaustive over observed set")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
