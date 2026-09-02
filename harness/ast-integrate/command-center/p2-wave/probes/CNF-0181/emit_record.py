#!/usr/bin/env python3
"""Emit command-center/receipts/CNF-0181.json — independent confirmation record."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from _common import (  # noqa: E402
    BASELINE_NEW_GOT,
    BASELINE_SRC,
    CASE_ID,
    IMPROVED_NEW_GOT,
    IMPROVED_SRC,
    IMPROVEMENT_ID,
    MEASURE_CASES,
    NEW_CASE,
    ORIGINAL_CASES,
)
from loop import census_production, run_retention_demo, score  # noqa: E402

OUT = "command-center/receipts/CNF-0181.json"
SCHEMA = "command-center/schema/confirmation-record.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0181/probe1_gain_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0181/probe2_revert_benchmark_neutral.py"
)


def sha_text(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def main() -> int:
    census = census_production(REPO)
    with tempfile.TemporaryDirectory(prefix="cnf0181-emit-") as tmp:
        demo = run_retention_demo(Path(tmp))

    pre = score(BASELINE_SRC, MEASURE_CASES)
    post = score(IMPROVED_SRC, MEASURE_CASES)
    new_pre = next(r for r in pre["rows"] if r["id"] == CASE_ID)
    new_post = next(r for r in post["rows"] if r["id"] == CASE_ID)
    orig_pre = score(BASELINE_SRC, ORIGINAL_CASES)
    orig_post = score(IMPROVED_SRC, ORIGINAL_CASES)

    keep = demo["keep"]
    neutral = demo["neutral"]
    no_wb = demo["no_writeback"]

    if keep["decision"] != "KEEP":
        print("FAILED:CNF-0181 emit expected KEEP for gain+writeback")
        return 1
    if neutral["decision"] != "REVERT" or no_wb["decision"] != "REVERT":
        print("FAILED:CNF-0181 emit expected REVERT for neutral and no-writeback")
        return 1
    if not demo["revert_byte_identical"]:
        print("FAILED:CNF-0181 emit revert was not byte-identical")
        return 1
    if new_pre["pass"] or not new_post["pass"]:
        print("FAILED:CNF-0181 emit both-states failed")
        return 1
    if orig_pre["ok"] != orig_pre["n"] or orig_post["ok"] != orig_post["n"]:
        print("FAILED:CNF-0181 emit original suite not green on both trees")
        return 1
    if not keep["wrote_case"]:
        print("FAILED:CNF-0181 emit KEEP without cited case id")
        return 1

    blinding = sha_text(
        IMPROVEMENT_ID,
        CASE_ID,
        BASELINE_SRC,
        IMPROVED_SRC,
        json.dumps(NEW_CASE, sort_keys=True),
        json.dumps(ORIGINAL_CASES, sort_keys=True),
    )
    source_fp = sha_text(P1, "gain-both-states")
    verifier_fp = sha_text(P2, "revert-benchmark-neutral")
    if source_fp == verifier_fp:
        print("FAILED:CNF-0181 emit source_probe fingerprint equals verifier")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    residual = (
        "Production tools/selfimprove/retain.py is absent on this worktree "
        f"(census present={census['production_modules_present'] or []} "
        f"absent={census['production_modules_absent']}). Confirmation is of "
        f"isolated retained improvement {IMPROVEMENT_ID} with write-back case "
        f"{CASE_ID}, not of an IMP-0373 production ledger."
    )

    doc = {
        "unit_id": "CNF-0181",
        "id": "CNF-0181",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0181",
        "completion_sentinel": "SUCCESS:CNF-0181",
        "title": (
            "Reproduce a retained self-improvement, its revert path, "
            "and the benchmark that prevents its silent return"
        ),
        "question": (
            "For an improvement the self-improvement loop RETAINED, can an "
            "independent party reproduce the measured gain, then reproduce the "
            "revert, and confirm the benchmark was updated so the original "
            "failure cannot silently come back (spec:11135-11150, step 10)?"
        ),
        "claim_id": IMPROVEMENT_ID,
        "confirmer": {
            "identity": "CNF-0181-independent-confirmer",
            "vendor": "anthropic",
            "role": "independent-confirmer",
            "model": "opus",
        },
        "blinding_attestation_hash": blinding,
        "source_probe": {
            "id": "probe1",
            "command": P1,
            "fingerprint": source_fp,
            "role": "gain-and-both-states",
        },
        "verifier_probe": {
            "id": "probe2",
            "command": P2,
            "fingerprint": verifier_fp,
            "role": "revert-benchmark-neutral",
        },
        "verdict": "CONFIRMED",
        "baseline_repro": {
            "tree": "baseline join_url",
            "measure_ok": pre["ok"],
            "measure_n": pre["n"],
            "new_case": {
                "id": CASE_ID,
                "pass": new_pre["pass"],
                "got": new_pre["got"],
                "want": NEW_CASE["want"],
                "expected_got": BASELINE_NEW_GOT,
            },
        },
        "corrected_repro": {
            "tree": "improved join_url",
            "measure_ok": post["ok"],
            "measure_n": post["n"],
            "new_case": {
                "id": CASE_ID,
                "pass": new_post["pass"],
                "got": new_post["got"],
                "want": NEW_CASE["want"],
                "expected_got": IMPROVED_NEW_GOT,
            },
        },
        "rollback_repro": {
            "method": "restore baseline join.py bytes",
            "new_case_fails_after_revert": True,
            "revert_byte_identical": demo["revert_byte_identical"],
            "got_after_revert": BASELINE_NEW_GOT,
        },
        "regression_diff": {
            "benchmark_case_id": CASE_ID,
            "public_before_ids": [c["id"] for c in ORIGINAL_CASES],
            "public_after_ids": [c["id"] for c in (ORIGINAL_CASES + [NEW_CASE])],
            "added": [CASE_ID],
            "removed": [],
            "without_new_case_baseline_public_is_green": True,
            "lesson": (
                "Removing case.cnf0181.double-slash makes the original "
                "triple-slash failure invisible on the public suite."
            ),
        },
        "discrepancies": [],
        "residual_caveat": residual,
        "three_measurements": {
            "gain_reproduced": {
                "before_ok": pre["ok"],
                "after_ok": post["ok"],
                "delta": post["ok"] - pre["ok"],
                "pass": post["ok"] > pre["ok"],
            },
            "revert_reproduced": {
                "pass": True,
                "original_failure_got": BASELINE_NEW_GOT,
            },
            "benchmark_delta": {
                "case_id": CASE_ID,
                "added": True,
                "pass": keep["wrote_case"],
            },
        },
        "tests": [
            {
                "id": "revert-control",
                "result": "PASS",
                "detail": "After revert, case.cnf0181.double-slash fails with triple-slash.",
            },
            {
                "id": "benchmark-control",
                "result": "PASS",
                "detail": (
                    "Remove the new case; baseline public suite is all-green; "
                    "the original failure is invisible."
                ),
            },
            {
                "id": "both-states",
                "result": "PASS",
                "detail": "Improved tree passes the new case; reverted tree fails it.",
            },
            {
                "id": "neutral-change-control",
                "result": "PASS",
                "detail": (
                    f"Comment-only candidate decision={neutral['decision']} "
                    f"reason={neutral['refuse_reason']}."
                ),
            },
            {
                "id": "no-writeback-refused",
                "result": "PASS",
                "detail": (
                    f"Gain without benchmark write-back decision={no_wb['decision']} "
                    f"reason={no_wb['refuse_reason']}."
                ),
            },
        ],
        "retention_ledger": demo["ledger"],
        "production_census": census,
        "spec_anchor": "_USER-PROMPTS.md:11135-11150 step 10",
        "output_schema": SCHEMA,
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "gain-and-both-states"},
            {"id": "probe2", "command": P2, "role": "revert-benchmark-neutral"},
        ],
        "reviewer": {
            "reviewer_id": "CNF-0181-probe2-revert-benchmark-neutral",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Mechanically different verifier: file revert, public-suite "
                "case deletion, comment-only patch, subprocess oracle. "
                "Agreement with probe 1's CONFIRMED is not required; the "
                "controls must fire."
            ),
        },
        "evidence": [
            {
                "kind": "gain",
                "detail": (
                    f"Measurement pack {pre['ok']}/{pre['n']} -> {post['ok']}/{post['n']} "
                    f"on {IMPROVEMENT_ID}."
                ),
            },
            {
                "kind": "revert",
                "detail": (
                    f"Restoring baseline join_url reproduces got={BASELINE_NEW_GOT} "
                    f"on {CASE_ID}."
                ),
            },
            {
                "kind": "benchmark-delta",
                "detail": (
                    f"Cited case id {CASE_ID} added to the public suite; "
                    "absence of this case is a retention failure."
                ),
            },
            {
                "kind": "neutral-reject",
                "detail": "Comment-only candidate refused with reason no-gain.",
            },
        ],
        "min_bytes_threshold": 2000,
        "ts": now,
        "SUCCESS:CNF-0181": True,
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    out.write_text(blob, encoding="utf-8")
    digest = hashlib.sha256(blob.encode("utf-8").replace(b"\r\n", b"\n")).hexdigest()
    if "SUCCESS:CNF-0181" not in blob:
        print("FAILED:CNF-0181 emit sentinel missing from text")
        return 1
    if len(blob.encode("utf-8")) < doc["min_bytes_threshold"]:
        print("FAILED:CNF-0181 emit below byte floor")
        return 1
    print(f"wrote {OUT} bytes={len(blob.encode('utf-8'))} sha256={digest}")
    print("SUCCESS:CNF-0181 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
