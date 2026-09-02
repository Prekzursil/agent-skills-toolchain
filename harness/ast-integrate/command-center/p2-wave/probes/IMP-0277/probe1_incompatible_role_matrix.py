#!/usr/bin/env python3
"""Probe 1: incompatible-role matrix, reconstructed independently of the author summary.

Expected cells are derived from the catalog row (proposer judging its own
proposal) plus CNL-0029 (critic voting on its own objection) and the
advocate/juror separation named in CNL-0026. Every other pair on the same
artifact, and every pair on different artifacts, must be accepted.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from tools.council.integrity import coi as C  # noqa: E402

# Independent expected forbidden pairs. Frozen sets so order does not matter.
PROPOSAL_FORBIDDEN = {
    frozenset({"proposer", "judge"}),
    frozenset({"proposer", "voter"}),
    frozenset({"proposer", "reviewer"}),
    frozenset({"proposer", "critic"}),
    frozenset({"proposer", "juror"}),
    frozenset({"advocate", "judge"}),
    frozenset({"advocate", "juror"}),
}
OBJECTION_FORBIDDEN = {
    frozenset({"critic", "voter"}),
    frozenset({"critic", "judge"}),
}


def expected_incompatible(role_a: str, role_b: str, kind: str, same: bool) -> bool:
    if not same or role_a == role_b:
        return False
    pair = frozenset({role_a, role_b})
    if kind == "proposal":
        return pair in PROPOSAL_FORBIDDEN
    if kind == "objection":
        return pair in OBJECTION_FORBIDDEN
    return False


def main() -> int:
    cells = C.enumerate_matrix()
    if len(cells) < 50:
        print(f"FAILED:IMP-0277-probe1 matrix too small n={len(cells)}")
        return 1
    mismatches = []
    forbidden_hit = 0
    allowed_hit = 0
    for cell in cells:
        want = expected_incompatible(
            cell["role_a"], cell["role_b"], cell["artifact_kind"], cell["same_artifact"]
        )
        got = bool(cell["incompatible"])
        if want != got:
            mismatches.append(
                {
                    "role_a": cell["role_a"],
                    "role_b": cell["role_b"],
                    "kind": cell["artifact_kind"],
                    "same_artifact": cell["same_artifact"],
                    "expected": want,
                    "got": got,
                    "constraint_ids": cell.get("constraint_ids"),
                }
            )
        elif want:
            forbidden_hit += 1
        else:
            allowed_hit += 1
    # Direct solver discharge of the catalog example, not via the matrix helper.
    pj = C.pair_is_incompatible({"proposer", "judge"}, artifact_kind="proposal")
    if not any(r["id"] == "IR-PROPOSER-JUDGE" for r in pj):
        print("FAILED:IMP-0277-probe1 proposer+judge did not discharge IR-PROPOSER-JUDGE")
        return 1
    # Compatible pair must not discharge any row.
    cv = C.pair_is_incompatible({"chair", "voter"}, artifact_kind="proposal")
    if cv:
        print(f"FAILED:IMP-0277-probe1 chair+voter falsely discharged {cv}")
        return 1
    # Different artifacts: proposer of A, judge of B is allowed.
    diff = C.matrix_cell("proposer", "judge", same_artifact=False)
    if diff["incompatible"]:
        print("FAILED:IMP-0277-probe1 proposer/judge on different artifacts refused")
        return 1
    if mismatches:
        print(json.dumps({"mismatches": mismatches[:20]}, indent=2))
        print(f"FAILED:IMP-0277-probe1 {len(mismatches)} matrix mismatches")
        return 1
    print(
        json.dumps(
            {
                "probe": "probe1-incompatible-role-matrix",
                "unit_id": "IMP-0277",
                "cells": len(cells),
                "forbidden_confirmed": forbidden_hit,
                "allowed_confirmed": allowed_hit,
                "proposer_judge_discharged": True,
                "chair_voter_silent": True,
                "cross_artifact_proposer_judge_allowed": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"cells={len(cells)} forbidden={forbidden_hit} allowed={allowed_hit} "
        "proposer+judge=DISCHARGED chair+voter=SILENT"
    )
    print("SUCCESS:IMP-0277-probe1 incompatible-role matrix")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
