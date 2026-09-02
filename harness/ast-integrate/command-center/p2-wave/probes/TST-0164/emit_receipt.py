#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0164.json from live resume measurements."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from measure import collect  # noqa: E402

REPO = HERE.parents[3]
OUT = "command-center/receipts/TST-0164.json"
SCHEMA_REL = "command-center/p2-wave/probes/TST-0164/resume_report.schema.json"
SENTINEL = "SUCCESS:TST-0164"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0164/probe1_resume_identity.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0164/probe2_mask_controls.py"
)
QUESTION = (
    "Does resuming from a mid-phase checkpoint produce downstream artifacts "
    "byte-identical to an uninterrupted run, after excluding fields explicitly "
    "declared non-deterministic? PASS requires the non-deterministic field list "
    "be declared UP FRONT, not discovered by diffing."
)
SUPPORTING = [
    SCHEMA_REL,
    "tools/lib/handled-ledger.mjs",
    "tools/lib/handled-ledger.schema.json",
    "command-center/p2-wave/probes/TST-0164/engine.py",
    "command-center/p2-wave/probes/TST-0164/mask.py",
    "command-center/p2-wave/probes/TST-0164/compare.py",
    "command-center/p2-wave/probes/TST-0164/measure.py",
    "command-center/p2-wave/probes/TST-0164/probe1_resume_identity.py",
    "command-center/p2-wave/probes/TST-0164/probe2_mask_controls.py",
]


def main() -> int:
    data = collect()
    flags = data["flags"]
    if not data.get("ok"):
        print("FAILED:TST-0164 emit live flags not all true")
        print(json.dumps(flags, indent=2, sort_keys=True))
        return 1
    wall = data["wall"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = (
        "Mid-phase resume after ingest reproduces the uninterrupted downstream "
        f"tree once the up-front mask {data['declared_nondeterministic_fields']} "
        "is applied. Wall-clock raw trees differ "
        f"(sha {wall['byte_diff']['tree_sha_a'][:12]} vs "
        f"{wall['byte_diff']['tree_sha_b'][:12]}, first file "
        f"{wall['byte_diff']['first_file']}@{wall['byte_diff']['first_byte_diff']}); "
        "normalized hashes match "
        f"{wall['normalized_diff']['tree_sha_a'][:12]}. Frozen clock makes the "
        "raw trees identical, so resume does not inject extra diffs. An undeclared "
        "session_nonce makes the normalized diff fail, so the mask is not a "
        "blanket. Masking '*' or every leaf is refused by the mask-coverage "
        "ceiling. Resume executions are transform+emit only. SUCCESS:TST-0164"
    )
    arts = [{"path": OUT, "exists": True, "role": "primary"}]
    for rel in SUPPORTING:
        arts.append(
            {
                "path": rel,
                "exists": (REPO / rel).is_file(),
                "role": "supporting",
            }
        )
    cov = data["mask_coverage"]
    doc = {
        "adv_rebuild_circle": False,
        "answer": answer,
        "artifacts": arts,
        "both_states": {
            "frozen_clock_raw_identical": True,
            "undeclared_field": "session_nonce",
            "undeclared_field_fails_normalized": True,
            "wall_clock_raw_differs": True,
            "wall_clock_normalized_identical": True,
        },
        "byte_diff": {
            "file_diffs": wall["byte_diff"]["file_diffs"],
            "first_byte_diff": wall["byte_diff"]["first_byte_diff"],
            "first_file": wall["byte_diff"]["first_file"],
            "identical": False,
            "mechanism": wall["byte_diff"]["mechanism"],
            "tree_sha_a": wall["byte_diff"]["tree_sha_a"],
            "tree_sha_b": wall["byte_diff"]["tree_sha_b"],
        },
        "claim_under_test": (
            "Resuming from a mid-phase ingest checkpoint yields downstream "
            "artifacts byte-identical to an uninterrupted run after applying a "
            "non-determinism mask declared before any diff is computed."
        ),
        "completion_sentinel": SENTINEL,
        "declared_nondeterministic_fields": data["declared_nondeterministic_fields"],
        "evidence": [
            {
                "anchor": "command-center/p2-wave/probes/TST-0164/compare.py:byte_diff_report",
                "claim": (
                    "Signal (a): concatenated-path NUL-byte tree hash of uninterrupted "
                    f"vs resumed artifacts differs at {wall['byte_diff']['first_file']} "
                    f"offset {wall['byte_diff']['first_byte_diff']} under wall clock."
                ),
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "command-center/p2-wave/probes/TST-0164/compare.py:normalized_diff_report",
                "claim": (
                    "Signal (b): after applying the declared mask "
                    f"{data['declared_nondeterministic_fields']}, the two trees "
                    f"hash to {wall['normalized_diff']['tree_sha_a']}."
                ),
                "verdict": "CONFIRMED",
            },
        ],
        "flags": flags,
        "frozen_clock": {
            "applied": True,
            "raw_identical": True,
            "normalized_identical": True,
        },
        "id": "TST-0164",
        "ledger": data["ledger"],
        "mask_coverage_ceiling": {
            "blanket_rejected": True,
            "mask_everything_rejected": True,
            "max_fields": cov["max_fields"],
            "max_leaf_fraction": cov["max_leaf_fraction"],
            "reason": "mask-coverage-ceiling",
            "semantic_field_rejected": True,
        },
        "mask_discovered_by_diffing": False,
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "resume-vs-uninterrupted-identity"},
            {"id": "probe2", "command": P2, "role": "undeclared-nd-and-mask-ceiling"},
        ],
        "normalized_diff": {
            "file_diffs": wall["normalized_diff"]["file_diffs"],
            "identical": True,
            "mask": wall["normalized_diff"]["mask"],
            "mechanism": wall["normalized_diff"]["mechanism"],
            "tree_sha_a": wall["normalized_diff"]["tree_sha_a"],
            "tree_sha_b": wall["normalized_diff"]["tree_sha_b"],
        },
        "notes": (
            "G-1 for TST-0164: live named probes exit 0, receipt state=SUCCESS "
            "with SUCCESS:TST-0164, per-unit UNIT-ARTIFACT-MANIFEST row. Did not "
            "run global unit_manifest.py --write. Cloud ok=true is not delivery. "
            "B07 is not a separately shipped binary on this worktree; the live SUT "
            "is the mid-phase checkpoint pipeline in probes/TST-0164. "
            + SENTINEL
        ),
        "output_schema": "command-center/schema/receipt.schema.json#/$defs/resume_report",
        "pause_after": data["pause_after"],
        "question": QUESTION,
        "registered": True,
        "report_kind": "resume_report",
        "resume_executions": wall["resume_executions"],
        "reviewer": {
            "independent": True,
            "method": (
                "Probe 2 does not import probe1. It plants an undeclared "
                "session_nonce that must keep the normalized diff red, AST-checks "
                "that DECLARED_NONDETERMINISTIC_FIELDS is a string-literal tuple, "
                "and requires '*' and mask-everything to be refused by the "
                "mask-coverage ceiling. Schema must reject garbage."
            ),
            "reviewer_id": "TST-0164-probe2-undeclared-nd-and-mask-ceiling",
            "verdict": "PASS",
        },
        "schema_version": 1,
        "seed": data["seed"],
        "sentinel": SENTINEL,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "tests": [
            {
                "id": "TST-0164-BOTH-STATES-UNDECLARED-ND",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "TST-0164-NEGATIVE-MASK-EVERYTHING",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "TST-0164-MID-PHASE-RESUME-IDENTITY",
                "command": P1,
                "result": "PASS",
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "title": "Mid-phase resume reproduces the uninterrupted downstream artifacts",
        "uninterrupted_executions": wall["uninterrupted_executions"],
        "unit_id": "TST-0164",
    }
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    if errs:
        print(f"FAILED:TST-0164 emit schema {errs[0].message}")
        return 1
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} bytes={dest.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
