#!/usr/bin/env python3
"""Probe 1: mid-phase resume vs uninterrupted, raw byte-diff + declared-mask norm.

Does not import probe2. Re-runs the pipeline live.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from engine import PAUSE_AFTER, SEED  # noqa: E402
from measure import collect, independent_continue_matches_helper  # noqa: E402

RECEIPT = REPO / "command-center" / "receipts" / "TST-0164.json"
SENTINEL = "SUCCESS:TST-0164"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0164-probe1 {msg}")
    return 1


def main() -> int:
    data = collect()
    flags = data["flags"]
    wall = data["wall"]
    frozen = data["frozen"]
    print(
        json.dumps(
            {
                "pause_after": PAUSE_AFTER,
                "seed": SEED,
                "declared_mask": data["declared_nondeterministic_fields"],
                "wall_raw_identical": wall["byte_diff"]["identical"],
                "wall_normalized_identical": wall["normalized_diff"]["identical"],
                "wall_first_file": wall["byte_diff"]["first_file"],
                "wall_first_byte": wall["byte_diff"]["first_byte_diff"],
                "wall_raw_sha_a": wall["byte_diff"]["tree_sha_a"],
                "wall_raw_sha_b": wall["byte_diff"]["tree_sha_b"],
                "wall_norm_sha_a": wall["normalized_diff"]["tree_sha_a"],
                "wall_norm_sha_b": wall["normalized_diff"]["tree_sha_b"],
                "frozen_raw_identical": frozen["byte_diff"]["identical"],
                "resume_executions": wall["resume_executions"],
                "uninterrupted_executions": wall["uninterrupted_executions"],
                "semantic_equal": wall["semantic_payloads_equal"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if not flags["wall_raw_differs"]:
        return fail("wall-clock uninterrupted vs resume were raw-identical (ND fields never fired)")
    if not flags["wall_normalized_identical"]:
        diffs = wall["normalized_diff"]["file_diffs"]
        return fail(f"declared-mask normalized trees still differ: {diffs}")
    if wall["byte_diff"]["tree_sha_a"] == wall["byte_diff"]["tree_sha_b"]:
        return fail("raw tree hashes collided while identical flag was false")
    if wall["normalized_diff"]["tree_sha_a"] != wall["normalized_diff"]["tree_sha_b"]:
        return fail("normalized tree hashes disagree with identical=true")
    if not flags["wall_semantic_equal"]:
        return fail("semantic payload/records/downstream diverged (resume bug, not ND)")
    if not flags["frozen_raw_identical"]:
        return fail("frozen-clock pair was not raw-identical (resume injected extra diffs)")
    if not flags["frozen_normalized_identical"]:
        return fail("frozen-clock pair failed normalized identity")
    if not flags["resume_skips_ingest"]:
        return fail(f"resume re-ran ingest executions={wall['resume_executions']}")
    if not flags["uninterrupted_runs_all_phases"]:
        return fail(f"uninterrupted executions={wall['uninterrupted_executions']}")
    if wall["ingest_reexecuted"]:
        return fail("resume notes claimed ingest re-execution")
    if not independent_continue_matches_helper():
        return fail("continue_from_checkpoint helper diverged from uninterrupted frozen run")
    if data["pause_after"] != "ingest":
        return fail("checkpoint is not mid-phase (ingest)")
    if wall["byte_diff"]["mechanism"] == wall["normalized_diff"]["mechanism"]:
        return fail("byte-diff and normalized-diff used the same mechanism string")
    if not data["ledger"]["uninterrupted"]["valid"]:
        return fail(f"ledger schema {data['ledger']['uninterrupted']['errors']}")

    if RECEIPT.is_file():
        text = RECEIPT.read_text(encoding="utf-8")
        doc = json.loads(text)
        if SENTINEL not in text:
            return fail("receipt sentinel absent")
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            return fail(f"receipt self-declared {doc.get('state')}")
        if doc.get("normalized_diff", {}).get("identical") is not True:
            return fail("receipt normalized_diff.identical is not true")
        if doc.get("mask_discovered_by_diffing") is not False:
            return fail("receipt claims mask was discovered by diffing")
        if doc.get("byte_diff", {}).get("identical") is True:
            return fail("receipt claimed raw trees were identical (mask would be untested)")
        print("receipt_matches_live_resume_identity=True")
    else:
        print("receipt_absent_on_this_run (pipeline checks only)")

    print("SUCCESS:TST-0164-probe1 mid-phase resume byte-diff + declared-mask identity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
