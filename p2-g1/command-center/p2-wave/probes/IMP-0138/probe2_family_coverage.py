#!/usr/bin/env python3
"""IMP-0138 probe2: every taxonomy family maps to exactly ONE default policy,
and the boundary-pinned family resolver differs from a substring resolver on a
near-miss (rail-exiting)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.on_failure import DEFAULT_ON_FAILURE, family_of  # noqa: E402
from agentspec.taxonomy import REASONS, family  # noqa: E402


def substring_family(code: str) -> str:
    """The mutant: bare prefix containment, no hyphen boundary."""
    for member in REASONS:
        if code.startswith(member):
            return member
    return ""


def main() -> int:
    # every family exactly one policy
    fams: dict[str, list[str]] = {}
    for member in REASONS:
        fams.setdefault(family(member), []).append(member)
    fams.pop("", None)
    one_policy = all(
        (DEFAULT_ON_FAILURE.get(f) or "") in {"retry", "fanout-skip", "fail-workflow", "handoff"}
        for f in fams
    )
    coverage_complete = set(DEFAULT_ON_FAILURE) == set(fams)

    # near-miss discrimination: the real resolver refuses rail-exiting
    probe_codes = ["rail-exit-137", "rail-exiting", "timeout-1800s", "timeoutish"]
    rows = []
    for code in probe_codes:
        real = family_of(code)
        mutant = substring_family(code)
        rows.append({
            "code": code,
            "family_of": real,
            "substring_mutant": mutant,
            "differ": real != mutant,
        })
    # rail-exit-137 -> rail-exit in BOTH; rail-exiting/timeoutish -> "" in real,
    # a member in the mutant (near-miss accepted).
    discriminates = (
        rows[0]["family_of"] == "rail-exit"
        and rows[0]["substring_mutant"] == "rail-exit"
        and rows[1]["family_of"] == ""
        and rows[1]["substring_mutant"] == "rail-exit"
        and rows[3]["family_of"] == ""
        and rows[3]["substring_mutant"] == "timeout"
    )

    result = {
        "unit_id": "IMP-0138",
        "probe": "probe2-family-coverage",
        "family_count": len(fams),
        "one_policy_per_family": one_policy,
        "coverage_complete": coverage_complete,
        "resolver_rows": rows,
        "boundary_pinned_resolver_wins": discriminates,
        "pass": one_policy and coverage_complete and discriminates,
    }
    print("RESULT:" + json.dumps(result))
    tail = ("SUCCESS:IMP-0138-probe2 every family exactly one policy; boundary-pinned "
            "resolver beats substring mutant on near-miss"
            if result["pass"] else
            "FAILED:IMP-0138-probe2 family coverage/resolver contract broken")
    print(tail)
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
