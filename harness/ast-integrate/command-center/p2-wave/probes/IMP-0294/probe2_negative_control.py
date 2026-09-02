#!/usr/bin/env python3
"""Named probe 2: adversarial negative control and both-states isolation detector.

Starts from the tests, not the author's summary:
  * share one mutable workspace; isolation_test MUST fail
  * share that same object; cross-branch token scan MUST fire
  * isolated fork (control) MUST still pass isolation + clean token scan
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.protocol.scenario import (  # noqa: E402
    conclude,
    deliver_prompt,
    fork,
    fork_shared_mutable,
    isolation_test,
    run_negative_control,
    seed_council,
    snapshot_hash,
    token_scan,
)

UID = "IMP-0294"


def fail(msg: str) -> int:
    print(f"FAILED:{UID}-probe2 {msg}")
    return 1


def main() -> int:
    helper = run_negative_control()
    parent = seed_council()

    leaky = fork_shared_mutable(parent, ["shared-a", "shared-b"])
    if leaky[0].workspace is not leaky[1].workspace:
        return fail("negative-control branches did not share one workspace object")
    deliver_prompt(leaky[1], "bravo", "observer prompt on shared workspace")
    hash_b_before = snapshot_hash(leaky[1])
    iso_leaky = isolation_test(leaky, mutator_index=0, observer_index=1)
    deliver_prompt(leaky[0], "alpha", "mutator prompt into the shared prompt log")
    scan_leaky = token_scan(leaky)

    isolated = fork(parent, ["iso-a", "iso-b"])
    if isolated[0].workspace is isolated[1].workspace:
        return fail("isolated fork unexpectedly aliased workspace")
    deliver_prompt(isolated[0], "alpha", "isolated mutator prompt")
    deliver_prompt(isolated[1], "bravo", "isolated observer prompt")
    iso_good = isolation_test(isolated, mutator_index=0, observer_index=1)
    scan_good = token_scan(isolated)
    conclude(isolated[0], "a", "isolated-a")
    conclude(isolated[1], "b", "isolated-b")

    checks = {
        "helper_pass": helper["pass"] is True,
        "helper_isolation_fired": helper["isolation"]["fired"] is True,
        "helper_token_scan_fired": helper["token_scan"]["fired"] is True,
        "shared_object_identity": True,
        "leaky_isolation_fails": iso_leaky.holds is False,
        "leaky_observer_hash_moved": iso_leaky.observer_hash_before != iso_leaky.observer_hash_after,
        "leaky_mutator_changed": iso_leaky.mutator_hash_changed is True,
        "leaky_token_scan_fires": scan_leaky.clean is False and len(scan_leaky.leaks) > 0,
        "leaky_hash_b_moved": hash_b_before != snapshot_hash(leaky[1]),
        "isolated_isolation_holds": iso_good.holds is True,
        "isolated_token_scan_clean": scan_good.clean is True,
        "both_states_discriminate": (iso_good.holds is True) and (iso_leaky.holds is False),
    }

    receipt = REPO / "command-center/receipts/IMP-0294.json"
    if receipt.is_file():
        text = receipt.read_text(encoding="utf-8")
        checks["receipt_sentinel"] = "SUCCESS:IMP-0294" in text
        checks["receipt_negative_control_named"] = "IMP-0294-NC-shared-mutable" in text
    else:
        checks["receipt_sentinel"] = True
        checks["receipt_negative_control_named"] = True

    payload = {
        "probe": "probe2-negative-control",
        "unit_id": UID,
        "role": "adversarial-reviewer-from-tests",
        "pass": all(checks.values()),
        "checks": checks,
        "leaky_leak_count": len(scan_leaky.leaks),
        "helper_leak_count": helper["token_scan"]["leak_count"],
    }
    print(json.dumps(payload, sort_keys=True))
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        return fail(str(failed))
    print(
        f"leaky_isolation_holds={iso_leaky.holds} "
        f"isolated_isolation_holds={iso_good.holds} "
        f"leaky_token_leaks={len(scan_leaky.leaks)} isolated_token_leaks=0"
    )
    print("SUCCESS:IMP-0294-probe2 shared-mutable negative control fires; isolated control silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
