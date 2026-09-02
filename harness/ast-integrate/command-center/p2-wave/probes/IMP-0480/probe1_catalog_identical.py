#!/usr/bin/env python3
"""IMP-0480 probe 1: catalog injections are identical on the boundary.

Both-states: the naive concatenating consumer DIVERGES on every planted
injection, and a prompt-level plea still follows at least one of them.
Sensitivity control: a benign FACT score edit MUST change boundary output.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from artifact_boundary.consume import behavior_of  # noqa: E402
from artifact_boundary.corpus import (  # noqa: E402
    INJECTIONS,
    baseline_artifacts,
    benign_score_edit,
    planted_pairs,
)
from artifact_boundary.naive import naive_consume, plea_then_naive  # noqa: E402
from artifact_boundary.policy import TrustedPolicy  # noqa: E402

KINDS = ["transcript", "fetched_page", "peer_result", "participant_output"]


def main() -> int:
    policy = TrustedPolicy()
    baseline = baseline_artifacts()
    kinds_present = sorted({a.kind for a in baseline})
    wrapped_base = behavior_of(baseline, policy)
    naive_base = naive_consume(baseline, policy)
    plea_base = plea_then_naive(baseline, policy)

    rows = []
    identical = True
    naive_diverged = True
    for inj_id, clean, dirty in planted_pairs():
        w_clean = behavior_of(clean, policy)
        w_dirty = behavior_of(dirty, policy)
        n_dirty = naive_consume(dirty, policy)
        same = w_clean == w_dirty
        naive_changed = n_dirty != naive_base
        identical = identical and same
        naive_diverged = naive_diverged and naive_changed
        rows.append(
            {
                "id": inj_id,
                "boundary_identical": same,
                "naive_diverged": naive_changed,
                "naive_planted": n_dirty,
            }
        )

    plea_still_follows = False
    for _inj_id, _clean, dirty in planted_pairs():
        if plea_then_naive(dirty, policy) != plea_base:
            plea_still_follows = True
            break

    edited = behavior_of(benign_score_edit(baseline), policy)
    benign_changes = edited != wrapped_base and ["score", "9"] in edited["facts"]

    kinds_ok = kinds_present == sorted(KINDS)
    catalog_ok = {row["id"] for row in rows} == set(INJECTIONS)
    passed = (
        identical
        and naive_diverged
        and plea_still_follows
        and benign_changes
        and kinds_ok
        and catalog_ok
        and wrapped_base["verdict"] == "HOLD"
        and wrapped_base["role"] == "consumer"
        and "credential_read" not in wrapped_base["actions"]
    )
    report = {
        "probe": "probe1-catalog-identical",
        "unit_id": "IMP-0480",
        "artifact_kinds": kinds_present,
        "catalog_classes": [row["id"] for row in rows],
        "rows": rows,
        "boundary_baseline": wrapped_base,
        "naive_baseline": naive_base,
        "plea_still_follows": plea_still_follows,
        "benign_fact_edit_changes_output": benign_changes,
        "benign_edited": edited,
        "pass": passed,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if not passed:
        print("FAILED:IMP-0480-probe1 catalog injections not held")
        return 1
    print("SUCCESS:IMP-0480-probe1 catalog held; naive diverges; plea is not a boundary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
