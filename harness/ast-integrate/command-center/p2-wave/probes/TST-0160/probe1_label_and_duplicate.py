#!/usr/bin/env python3
"""Probe 1: both-states labeling plus provenance independence.

Independent pair (two vendors, disjoint intermediates) is one logical unit
with two observations and an independence claim.

Accidental duplicate (same vendor, same inputs) is DUPLICATION, not independence.

Two vendors that share an intermediate must not claim independence. A mutant
that claims independence merely because vendors differ must go red.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import replication as R  # noqa: E402

UID = "TST-0160"
RUNTIME = HERE / "runtime" / "probe1"


def fail(msg: str, payload: dict) -> int:
    print(json.dumps(payload, sort_keys=True))
    print(f"FAILED:{UID}-probe1 {msg}")
    return 1


def main() -> int:
    errors: list[str] = []
    left, right = R.independent_pair()
    dup_a, dup_b = R.duplicate_pair()
    share_a, share_b = R.shared_input_pair()

    independent = R.classify_pair(left, right)
    duplicate = R.classify_pair(dup_a, dup_b)
    shared = R.classify_pair(share_a, share_b)

    R.write_ledger(
        RUNTIME / "independent.json",
        [left, right],
        extra={"label": independent["label"]},
    )
    R.write_ledger(
        RUNTIME / "duplicate.json",
        [dup_a, dup_b],
        extra={"label": duplicate["label"]},
    )
    R.write_ledger(
        RUNTIME / "shared-input.json",
        [share_a, share_b],
        extra={"label": shared["label"]},
    )

    if independent["label"] != R.LABEL_INDEPENDENT:
        errors.append(f"independent-label:{independent['label']}")
    if independent["independence_claimed"] is not True:
        errors.append("independent-did-not-claim-independence")
    if independent["logical_unit_count"] != 1:
        errors.append("independent-not-one-logical-unit")
    if independent["observation_count"] != 2:
        errors.append("independent-observation-count")
    if independent["provenance_diff"]["disjoint"] is not True:
        errors.append("independent-provenance-not-disjoint")
    if independent["same_vendor"] is True:
        errors.append("independent-same-vendor")
    if left.sha_set() == right.sha_set():
        errors.append("independent-hashes-collided")

    if duplicate["label"] != R.LABEL_DUPLICATION:
        errors.append(f"duplicate-label:{duplicate['label']}")
    if duplicate["independence_claimed"] is True:
        errors.append("duplicate-claimed-independence")
    if duplicate["same_vendor"] is not True or duplicate["same_inputs"] is not True:
        errors.append("duplicate-fixture-not-same-vendor-same-inputs")
    if duplicate["logical_unit_count"] != 1:
        errors.append("duplicate-not-one-logical-unit")

    if shared["label"] != R.LABEL_SHARED_INPUT:
        errors.append(f"shared-label:{shared['label']}")
    if shared["independence_claimed"] is True:
        errors.append("shared-input-claimed-independence")
    if shared["provenance_diff"]["disjoint"] is True:
        errors.append("shared-input-reported-disjoint")
    if shared["same_vendor"] is True:
        errors.append("shared-input-same-vendor")

    mutant_on_shared = R.mutant_independence_if_vendors_differ(share_a, share_b)
    mutant_on_dup = R.mutant_independence_if_vendors_differ(dup_a, dup_b)
    if mutant_on_shared is not True:
        errors.append("mutant-did-not-claim-on-shared-input")
    if mutant_on_dup is True:
        errors.append("mutant-claimed-on-duplicate")
    if mutant_on_shared and not shared["independence_claimed"]:
        mutant_caught = True
    else:
        mutant_caught = False
        errors.append("mutant-not-caught")

    payload = {
        "duplicate": duplicate,
        "errors": errors,
        "independent": independent,
        "mutant_caught": mutant_caught,
        "mutant_on_duplicate": mutant_on_dup,
        "mutant_on_shared": mutant_on_shared,
        "pass": not errors,
        "probe": "probe1-label-and-duplicate",
        "shared_input": shared,
        "unit_id": UID,
    }
    if errors:
        return fail(",".join(errors), payload)
    print(json.dumps(payload, sort_keys=True))
    print(
        f"independent={independent['label']} dup={duplicate['label']} "
        f"shared={shared['label']} mutant_caught={mutant_caught} "
        f"disjoint={independent['provenance_diff']['disjoint']}"
    )
    print("SUCCESS:TST-0160-probe1 both-states labelled-not-duplicated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
