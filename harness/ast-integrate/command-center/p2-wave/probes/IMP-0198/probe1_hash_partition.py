#!/usr/bin/env python3
"""Probe 1: held-out membership is a pure function of the case hash.

Independent recomputation (this file, not the stored label) must agree with
``partition_of`` on every case, twice. Relabelling ``partition_cached`` cannot
move a case. Every difficulty stratum contains both slices.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.evals.rows import (  # noqa: E402
    DIFFICULTIES,
    HELD_OUT,
    HOLD_OUT_MOD,
    HOLD_OUT_RESIDUE,
    PARTITION_SALT,
    VISIBLE,
    build_corpus,
    case_hash,
    canonical_identity,
    load_corpus,
    partition_of,
    stratum_counts,
)

FROZEN = REPO / "command-center" / "bench" / "cases" / "IMP-0198" / "corpus.json"


def independent_partition(case: dict) -> str:
    """Second derivation of the documented hash-partition. Not a call to partition_of."""
    payload = {
        "id": case["id"],
        "family": case["family"],
        "difficulty": case["difficulty"],
        "task": case["task"],
        "oracle": case["oracle"],
    }
    blob = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    digest = hashlib.sha256(PARTITION_SALT + b"\x1f" + blob).hexdigest()
    n = int(digest[:16], 16)
    return HELD_OUT if (n % HOLD_OUT_MOD) == HOLD_OUT_RESIDUE else VISIBLE


def main() -> int:
    live_a = build_corpus()
    live_b = build_corpus()
    if [c["id"] for c in live_a] != [c["id"] for c in live_b]:
        print("FAILED:IMP-0198-probe1 corpus rebuild is not deterministic")
        return 1
    if [case_hash(c) for c in live_a] != [case_hash(c) for c in live_b]:
        print("FAILED:IMP-0198-probe1 hashes drifted across rebuilds")
        return 1

    if FROZEN.is_file():
        frozen = load_corpus(str(FROZEN))
        if [c["id"] for c in frozen] != [c["id"] for c in live_a]:
            print("FAILED:IMP-0198-probe1 frozen corpus id list != live rebuild")
            return 1
        for frozen_case, live_case in zip(frozen, live_a):
            if case_hash(frozen_case) != case_hash(live_case):
                print(f"FAILED:IMP-0198-probe1 hash drift {frozen_case['id']}")
                return 1

    disagreements = []
    convention_moved = []
    identity_mismatch = []
    for case in live_a:
        lib = partition_of(case)
        indep = independent_partition(case)
        if lib != indep:
            disagreements.append(case["id"])
        if canonical_identity(case) != canonical_identity(
            {**case, "partition_cached": "tampered", "case_hash": "0" * 64}
        ):
            identity_mismatch.append(case["id"])
        mutant = dict(case)
        mutant["partition_cached"] = VISIBLE if lib == HELD_OUT else HELD_OUT
        if partition_of(mutant) != lib:
            convention_moved.append(case["id"])
        if independent_partition(mutant) != lib:
            convention_moved.append(case["id"])

    if disagreements:
        print(f"FAILED:IMP-0198-probe1 independent hash disagrees n={len(disagreements)}")
        return 1
    if identity_mismatch:
        print("FAILED:IMP-0198-probe1 cached fields leaked into identity")
        return 1
    if convention_moved:
        print("FAILED:IMP-0198-probe1 stored label moved the partition")
        return 1

    counts = stratum_counts(live_a)
    for difficulty in DIFFICULTIES:
        if counts[difficulty][HELD_OUT] < 1 or counts[difficulty][VISIBLE] < 1:
            print(f"FAILED:IMP-0198-probe1 stratum {difficulty} not split {counts[difficulty]}")
            return 1

    held = [c["id"] for c in live_a if partition_of(c) == HELD_OUT]
    vis = [c["id"] for c in live_a if partition_of(c) == VISIBLE]
    if not held or not vis:
        print("FAILED:IMP-0198-probe1 empty slice")
        return 1

    # Changing identity bytes must change the hash (oracle/task is in identity).
    sample = dict(live_a[0])
    sample["task"] = {"prompt": "tamper", "input": "probe1"}
    if case_hash(sample) == case_hash(live_a[0]):
        print("FAILED:IMP-0198-probe1 task tamper did not change hash")
        return 1

    print(
        json.dumps(
            {
                "n_cases": len(live_a),
                "n_held_out": len(held),
                "n_visible": len(vis),
                "stratum_counts": counts,
                "independent_agreements": len(live_a),
                "convention_moves": 0,
                "rebuild_identical": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"hash_partition_ok=True held_out={len(held)} visible={len(vis)} "
        f"strata={counts}"
    )
    print("SUCCESS:IMP-0198-probe1 held-out partition is hash-determined and reproducible")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
