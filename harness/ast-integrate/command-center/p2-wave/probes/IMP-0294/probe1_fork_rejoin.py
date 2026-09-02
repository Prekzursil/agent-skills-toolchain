#!/usr/bin/env python3
"""Named probe 1: fork, mutate, rejoin four isolated scenario branches.

Signals:
  * isolation_test: mutate branch A, branch B snapshot hash unchanged
  * four distinct conclusions after rejoin
  * cross-branch token scan of delivered prompts is clean
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.protocol.scenario import (  # noqa: E402
    FOUR_LABELS,
    conclude,
    deliver_prompt,
    fork,
    isolation_test,
    mutate_workspace,
    rejoin,
    run_four_branch_wargame,
    seed_council,
    snapshot_hash,
    token_scan,
)

UID = "IMP-0294"


def fail(msg: str) -> int:
    print(f"FAILED:{UID}-probe1 {msg}")
    return 1


def main() -> int:
    live = run_four_branch_wargame()
    iso = live["isolation"]
    scan = live["token_scan"]
    joined = live["rejoin"]

    checks = {
        "four_branches": live["branch_count"] == 4,
        "four_labels": live["labels"] == list(FOUR_LABELS),
        "isolation_holds": iso["holds"] is True,
        "mutator_hash_changed": iso["mutator_hash_changed"] is True,
        "observer_hash_stable": iso["observer_hash_before"] == iso["observer_hash_after"],
        "token_scan_clean": scan["clean"] is True,
        "token_leak_count_zero": scan["leak_count"] == 0,
        "rejoin_count": joined["branch_count"] == 4,
        "four_verdicts": len({c["verdict"] for c in joined["conclusions"]}) == 4,
        "helper_pass": live["pass"] is True,
    }

    # Second, explicit fork/mutate/rejoin so a helper-only pass cannot hide a
    # broken public API.
    parent = seed_council()
    branches = fork(parent, list(FOUR_LABELS))
    if len(branches) != 4:
        return fail(f"fork_count={len(branches)}")
    hashes_before = [snapshot_hash(b) for b in branches]
    if len(set(hashes_before)) != 4:
        return fail("fork-time hashes were not unique (unexpected collision)")
    iso2 = isolation_test(branches, mutator_index=0, observer_index=1)
    if not iso2.holds:
        return fail("isolation_test failed on isolated fork")
    if hashes_before[1] != snapshot_hash(branches[1]):
        return fail("observer snapshot hash changed after mutating sibling")
    if hashes_before[2] != snapshot_hash(branches[2]) or hashes_before[3] != snapshot_hash(
        branches[3]
    ):
        return fail("untouched sibling snapshot hash changed")
    seats = ["alpha", "bravo", "charlie", "delta"]
    for i, branch in enumerate(branches):
        mutate_workspace(
            branch,
            fact=f"probe1:{branch.label}",
            seat_id=seats[i],
            memory_item=f"probe1-mem:{branch.label}",
            score_seat=seats[i],
            score_delta=3,
        )
        deliver_prompt(branch, seats[i], f"probe1 delivered prompt for {branch.label}")
        conclude(branch, f"v{i}", f"rationale-{branch.label}")
    joined2 = rejoin(branches)
    scan2 = token_scan(branches)
    checks["api_rejoin_four"] = joined2.branch_count == 4
    checks["api_token_scan_clean"] = scan2.clean is True
    checks["api_isolation_holds"] = iso2.holds is True
    checks["api_mutator_changed"] = iso2.mutator_hash_changed is True

    receipt = REPO / "command-center/receipts/IMP-0294.json"
    if receipt.is_file():
        text = receipt.read_text(encoding="utf-8")
        checks["receipt_sentinel"] = "SUCCESS:IMP-0294" in text
        try:
            doc = json.loads(text)
        except json.JSONDecodeError:
            return fail("receipt unparseable")
        checks["receipt_unit_id"] = doc.get("unit_id") == UID
        st = str(doc.get("state") or "").upper()
        checks["receipt_not_blocked"] = st not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
    else:
        checks["receipt_sentinel"] = True
        checks["receipt_unit_id"] = True
        checks["receipt_not_blocked"] = True

    payload = {
        "probe": "probe1-fork-rejoin",
        "unit_id": UID,
        "pass": all(checks.values()),
        "checks": checks,
        "isolation": iso,
        "token_scan_leak_count": scan["leak_count"],
        "verdicts": [c["verdict"] for c in joined["conclusions"]],
    }
    print(json.dumps(payload, sort_keys=True))
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        return fail(str(failed))
    print(
        f"isolation_holds={iso['holds']} observer_stable=True "
        f"token_leaks={scan['leak_count']} rejoin={joined['branch_count']}"
    )
    print("SUCCESS:IMP-0294-probe1 fork-mutate-rejoin over 4 isolated branches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
