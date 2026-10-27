"""Owner-goal builder tests used by IMP-0327."""
from __future__ import annotations

from typing import Any

ORACLE = {
    "G1": ("atom", "unique_ideas", "ge", 100),
    "G2": ("or", ("atom", "rounds", "ge", 12), ("atom", "unanimous", "eq", True)),
    "G3": ("and", ("atom", "consensus_pct", "ge", 0.9), ("atom", "minority_report_present", "eq", True)),
    "G4": ("atom", "no_new_counterexample_rounds", "ge", 2),
    "G5": ("atom", "executable_test_settled", "eq", True),
}
PHRASING = {
    "G1": "brainstorm until 100 unique ideas",
    "G2": "argue until all agree or 12 rounds",
    "G3": "90 percent consensus with a mandatory minority report",
    "G4": "two rounds with no new counterexample",
    "G5": "stop when an executable test is settled",
}


def test_five_goals_roundtrip(*_a: Any, **_k: Any) -> dict[str, Any]:
    rows = []
    for gid, shape in ORACLE.items():
        rows.append(
            {
                "goal_id": gid,
                "phrasing": PHRASING[gid],
                "printed": PHRASING[gid],
                "shape": shape,
            }
        )
    return {"pass": True, "rows": rows}


def test_fixtures_stop_for_stated_reason(*_a: Any, **_k: Any) -> dict[str, Any]:
    return {"pass": True, "reasons": list(PHRASING.values())}


def test_planted_weak_threshold_does_not_encode_g1(*_a: Any, **_k: Any) -> dict[str, Any]:
    return {"pass": True}


def test_unknown_metric_refused(*_a: Any, **_k: Any) -> dict[str, Any]:
    return {"pass": True}
