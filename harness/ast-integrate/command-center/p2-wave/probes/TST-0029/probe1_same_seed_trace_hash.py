#!/usr/bin/env python3
"""Probe 1: two runs, same seed, same structural trace hash.

Also the different-seed control: the seed must actually move DynamicFanOut
cardinality, otherwise a constant hash is a dead detector.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from load_lib import receipt_domain, repo  # noqa: E402
from measure import collect, independent_hash  # noqa: E402

REPO = repo()
RECEIPT = REPO / "command-center" / "receipts" / "TST-0029.json"
SENTINEL = "SUCCESS:TST-0029"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0029-probe1 {msg}")
    return 1


def main() -> int:
    data = collect()
    flags = data["flags"]
    run_a = data["run_a"]
    print(
        json.dumps(
            {
                "same_seed_identical": flags["same_seed_identical"],
                "different_seed_diverges": flags["different_seed_diverges"],
                "run_a_sha256": run_a["trace_hash"],
                "run_b_sha256": data["run_b"]["trace_hash"],
                "other_seed_sha256": data["other_seed_hash"],
                "node_order": run_a["node_order"],
                "fan_out_cardinalities": data["fan_out_cardinalities"],
                "barrier_ids": [b["id"] for b in run_a["barrier_resolution"]],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if not flags["same_seed_identical"]:
        return fail("same seed produced different trace hashes")
    if run_a["trace_hash"] != data["run_b"]["trace_hash"]:
        return fail("run_a/run_b hash mismatch")
    if not flags["different_seed_diverges"]:
        return fail("different seed did not change the trace (seed not consumed)")
    indep = independent_hash(
        {
            "node_order": run_a["node_order"],
            "fan_out": run_a["fan_out"],
            "barrier_resolution": run_a["barrier_resolution"],
        }
    )
    if indep != run_a["trace_hash"]:
        return fail("independent canonical hash != library trace_hash")
    if len(run_a["node_order"]) < 5:
        return fail("node_order too short for a fan-out/barrier DAG")
    kinds = {row["kind"] for row in run_a["fan_out"]}
    if "FanOut" not in kinds or "DynamicFanOut" not in kinds:
        return fail(f"missing fan-out kinds {kinds}")
    if len(run_a["barrier_resolution"]) < 2:
        return fail("expected two barriers (fan-out join and dynamic join)")
    cards = {row["id"]: row["cardinality"] for row in data["fan_out_cardinalities"]}
    if cards.get("fan-ab") != 2:
        return fail(f"static FanOut cardinality {cards.get('fan-ab')} != 2")
    if cards.get("dyn") != 2 + (7 % 3):
        return fail(f"seed-7 DynamicFanOut cardinality {cards.get('dyn')} != 3")

    if RECEIPT.is_file():
        text = RECEIPT.read_text(encoding="utf-8")
        doc = json.loads(text)
        if SENTINEL not in text:
            return fail("receipt sentinel absent")
        cmp_ = receipt_domain(doc).get("trace_hash_comparison") or {}
        if cmp_.get("run_a_sha256") != run_a["trace_hash"]:
            return fail("receipt run_a_sha256 is not the live hash")
        if cmp_.get("identical") is not True:
            return fail("receipt did not record identical same-seed traces")
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            return fail(f"receipt self-declared {doc.get('state')}")
        print("receipt_matches_live_same_seed_hash=True")
    else:
        print("receipt_absent_on_this_run (library checks only)")

    print("SUCCESS:TST-0029-probe1 two runs same seed same trace hash")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
