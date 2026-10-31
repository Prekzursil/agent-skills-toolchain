"""Owner-goal stopping-tree builder."""
from __future__ import annotations

from typing import Any

METRICS = ("unique_ideas", "rounds", "unanimous", "consensus_pct", "minority_report_present", "no_new_counterexample_rounds", "executable_test_settled")
SPEC_ANCHOR = "CNL-0128"

GOALS = {
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


def canonical_shape(spec: Any) -> tuple:
    if isinstance(spec, dict):
        expr = spec.get("expr") or spec.get("shape")
        if expr is not None:
            return tuple(expr) if isinstance(expr, (list, tuple)) else expr
        return GOALS.get(str(spec.get("id") or ""), ())
    if isinstance(spec, (list, tuple)):
        return tuple(spec)
    return GOALS.get(str(spec), ())


def build_all_owner_goals() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for gid, shape in GOALS.items():
        out[gid] = {
            "id": gid,
            "shape": shape,
            "stopping": {
                "expr": shape,
                "printed": PHRASING[gid],
            },
        }
    return out


def restate(gid: str) -> dict[str, Any]:
    return {"id": gid, "shape": GOALS[gid]}
