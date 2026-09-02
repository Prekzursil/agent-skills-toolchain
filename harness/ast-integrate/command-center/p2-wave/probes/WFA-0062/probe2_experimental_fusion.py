#!/usr/bin/env python3
"""Probe 2: independent experimental fusion (does not trust the author's edge list).

Recomputes exclusive pairs from slot assertions, constructs a fusion of
blind independent first pass with shared-context deliberation, observes
UNSAT, and checks the both-states control (drop either mechanism → SAT).
A SOFT pair must remain SAT. Artifact HARD edges must equal the
independently computed exclusive set.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from engine import (  # noqa: E402
    exclusive_pairs,
    fuse_same_stage,
    naive_union_today,
    soft_pairs,
)

ART = REPO / "command-center/wfa/WFA-0062-mechanism-conflicts.json"
SENTINEL = "SUCCESS:WFA-0062"
HARD_EXHIBIT = (
    "mech.blind_independent_first_pass",
    "mech.shared_context_deliberation",
)
SOFT_EXHIBIT = ("mech.sequential_stages", "mech.parallel_fanout")


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0062-probe2 {msg}")
    return 1


def pair_key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a <= b else (b, a)


def main() -> int:
    computed = {pair_key(p["left"], p["right"]) for p in exclusive_pairs()}
    if pair_key(*HARD_EXHIBIT) not in computed:
        return fail("named exhibit pair is not in independently computed exclusive set")

    both = fuse_same_stage(list(HARD_EXHIBIT))
    if both["sat"] or both["verdict"] != "UNSAT":
        return fail(f"exhibit fusion was SAT: {both}")
    if not both["clashes"]:
        return fail("UNSAT without a clash record")
    left_only = fuse_same_stage([HARD_EXHIBIT[0]])
    right_only = fuse_same_stage([HARD_EXHIBIT[1]])
    if not left_only["sat"] or not right_only["sat"]:
        return fail("both-states: dropping one mechanism did not restore SAT")

    soft = fuse_same_stage(list(SOFT_EXHIBIT))
    if not soft["sat"]:
        return fail("SOFT exhibit pair fused UNSAT")
    for s in soft_pairs():
        if pair_key(s["left"], s["right"]) in computed:
            return fail(f"SOFT friction pair is exclusive {s['left']} {s['right']}")

    today = naive_union_today(list(HARD_EXHIBIT))
    if today["gate_present"] is not False:
        return fail("gate_present must be false on this worktree")
    if today["fused"]["sat"]:
        return fail("naive union of exhibit pair was SAT")

    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if SENTINEL not in json.dumps(doc):
        return fail("sentinel absent")
    art_hard = {
        pair_key(e["source"], e["target"])
        for e in (doc.get("edges") or [])
        if e.get("kind") == "conflicts-with"
    }
    if art_hard != computed:
        missing = sorted(computed - art_hard)
        extra = sorted(art_hard - computed)
        return fail(f"HARD edge set mismatch missing={missing} extra={extra}")
    exhibit = doc.get("experimental_exhibition") or {}
    if exhibit.get("fusion", {}).get("sat") is not False:
        return fail("artifact exhibit fusion not UNSAT")
    bs = exhibit.get("both_states") or {}
    if not (
        bs.get("both_mechanisms_UNSAT")
        and bs.get("drop_right_SAT")
        and bs.get("drop_left_SAT")
    ):
        return fail("artifact both_states flags not live")

    print(
        json.dumps(
            {
                "probe": "probe2-experimental-fusion",
                "unit_id": "WFA-0062",
                "exhibit_pair": list(HARD_EXHIBIT),
                "exhibit_verdict": both["verdict"],
                "clashes": both["clashes"],
                "drop_left_sat": left_only["sat"],
                "drop_right_sat": right_only["sat"],
                "soft_exhibit_sat": soft["sat"],
                "independent_hard_n": len(computed),
                "naive_union_silent_unsat": (not today["fused"]["sat"]),
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:WFA-0062-probe2 experimental fusion UNSAT; both-states SAT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
