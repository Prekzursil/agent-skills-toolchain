#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0147.json (predicate_report)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from harness import (  # noqa: E402
    OUT_REL,
    P1,
    P2,
    SENTINEL,
    UNIT,
    measure,
)

SCHEMA = "command-center/schema/receipt.schema.json#/$defs/predicate_report"
QUESTION = (
    "Does condition 6 treat a file:line anchor pointing at a nonexistent file, "
    "or a line beyond end-of-file, as missing evidence? PASS requires resolution "
    "of every anchor against the filesystem at the recorded revision; a "
    "syntactically valid but unresolvable anchor is a FAIL."
)


def main() -> int:
    live = measure()
    c6 = live["condition6"]
    git = live["git_and_shape"]
    if not live["catalog_pass"]:
        print("FAILED:TST-0147 emit catalog controls did not pass")
        print(
            json.dumps(
                {
                    "condition6_pass": c6["pass"],
                    "git_and_shape_pass": git["pass"],
                    "c6_good": c6["good"]["outcome"],
                    "c6_off": c6["off_by_1000"]["outcome"],
                    "git_off": git["off_by_1000"]["classification"],
                },
                indent=2,
            )
        )
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sut = "platform/lib/completion_predicate.py:_c6_evidence"
    answer_summary = (
        "Yes. Live condition 6 (`evaluate` scope=[6]) PASSes a resolvable "
        f"fixture file:line ({c6['fixture_path']}:{c6['good_line']}) and FALSEs "
        f"the same path at line {c6['bad_line']} as BEYOND-EOF and a missing "
        "path as MISSING. Independent `git cat-file -p <rev>:<path>` at "
        f"{git['fixture_rev'][:12]}… confirms OK / BEYOND-EOF / MISSING with "
        "matching blob text. A shape-only path:digits regex accepts the "
        "off-by-1000 and the missing path, so that checker fails this test. "
        f"{SENTINEL}"
    )

    doc = {
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "predicate_report",
        "title": "An unresolvable evidence anchor counts as MISSING",
        "question": QUESTION,
        "answer": answer_summary,
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "output_schema": SCHEMA,
        "output_path": OUT_REL,
        "measured_at": now,
        "min_bytes_threshold": 2048,
        "cloud_ok": False,
        "target_pass": True,
        "target_verdict": live["target_verdict"],
        "sut": {
            "module": sut,
            "method": c6["method"],
            "evidence_pointer": c6["good"].get("evidence_pointer"),
        },
        "both_states": {
            "method": c6["method"],
            "fixture_rev": c6["fixture_rev"],
            "fixture_path": c6["fixture_path"],
            "fixture_line_count": c6["fixture_line_count"],
            "good_line": c6["good_line"],
            "bad_line": c6["bad_line"],
            "good_outcome": c6["good"]["outcome"],
            "off_by_1000_outcome": c6["off_by_1000"]["outcome"],
            "missing_outcome": c6["missing"]["outcome"],
            "good_basis": c6["good"]["basis"],
            "off_by_1000_basis": c6["off_by_1000"]["basis"],
            "missing_basis": c6["missing"]["basis"],
            "silent_on_good": c6["silent_on_good"],
            "fired_on_off_by_1000": c6["fired_on_off_by_1000"],
            "fired_on_missing": c6["fired_on_missing"],
            "pass": c6["pass"],
        },
        "git_cat_file": {
            "method": git["method"],
            "fixture_rev": git["fixture_rev"],
            "fixture_path": git["fixture_path"],
            "fixture_line_count": git["fixture_line_count"],
            "good_classification": git["good"]["classification"],
            "off_by_1000_classification": git["off_by_1000"]["classification"],
            "missing_classification": git["missing"]["classification"],
            "blob_text_ok": git["blob_text_ok"],
            "good_spec": git["good"].get("spec"),
            "off_by_1000_spec": git["off_by_1000"].get("spec"),
            "shape_only_accepts_good": git["shape_only_accepts_good"],
            "shape_only_accepts_off_by_1000": git["shape_only_accepts_off_by_1000"],
            "shape_only_accepts_missing": git["shape_only_accepts_missing"],
            "shape_only_fails_this_test": git["shape_only_fails_this_test"],
            "pass": git["pass"],
        },
        "signals": [
            {
                "id": "a",
                "kind": "anchor-resolver-per-anchor-verdict",
                "source": sut,
                "good": c6["good"]["outcome"],
                "off_by_1000": c6["off_by_1000"]["outcome"],
                "missing": c6["missing"]["outcome"],
            },
            {
                "id": "b",
                "kind": "git-cat-file-existence-and-line-count",
                "command": "git cat-file -p <rev>:<path>",
                "good": git["good"]["classification"],
                "off_by_1000": git["off_by_1000"]["classification"],
                "missing": git["missing"]["classification"],
            },
        ],
        "tests": [
            {
                "id": "both-states-off-by-1000",
                "name": "resolvable file:line PASSes condition 6; off-by-1000 FALSEs",
                "command": P1,
                "result": "PASS" if c6["pass"] else "FAIL",
            },
            {
                "id": "negative-shape-only-anchor",
                "name": "shape-only path:digits regex accepts off-by-1000 and fails this test",
                "command": P2,
                "result": "PASS" if git["pass"] else "FAIL",
            },
        ],
        "tests_required": [
            {
                "id": "both-states-off-by-1000",
                "text": "both-states control: a resolvable anchor passes, an off-by-1000 line number fails",
                "result": "PASS" if c6["silent_on_good"] and c6["fired_on_off_by_1000"] else "FAIL",
            },
            {
                "id": "negative-shape-only-anchor",
                "text": "negative control: a checker that only regex-validates the anchor SHAPE must fail this test",
                "result": "PASS" if git["shape_only_fails_this_test"] else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "shape-only-anchor",
                "kind": "known-broken-implementation",
                "description": (
                    "A checker that only regex-validates path:digits accepts the "
                    "off-by-1000 and missing-path fixtures; condition 6 and git "
                    "cat-file report BEYOND-EOF / MISSING."
                ),
                "fired_on_bad_state": c6["fired_on_off_by_1000"] and git["off_by_1000"]["classification"] == "BEYOND-EOF",
                "silent_on_good_state": c6["silent_on_good"] and git["good"]["classification"] == "OK",
            }
        ],
        "evidence": [
            {
                "id": "E1",
                "claim": (
                    "Condition 6 treats a resolvable file:line as present and an "
                    "off-by-1000 or missing-path file:line as missing evidence."
                ),
                "text": (
                    "Condition 6 treats a resolvable file:line as present and an "
                    "off-by-1000 or missing-path file:line as missing evidence."
                ),
                "verdict": "CONFIRMED",
                "source_probe": "command-center/p2-wave/probes/TST-0147/probe1_both_states.py",
                "verifier_probe": "command-center/p2-wave/probes/TST-0147/probe2_cat_file_and_shape.py",
                "anchor": sut,
                "signal": "a-condition-6-evaluate",
            },
            {
                "id": "E2",
                "claim": (
                    "Independent git cat-file -p at the recorded revision confirms "
                    "existence and line count; a shape-only checker accepts the "
                    "unresolvable anchors and therefore fails this test."
                ),
                "text": (
                    "Independent git cat-file -p at the recorded revision confirms "
                    "existence and line count; a shape-only checker accepts the "
                    "unresolvable anchors and therefore fails this test."
                ),
                "verdict": "CONFIRMED",
                "source_probe": "command-center/p2-wave/probes/TST-0147/probe2_cat_file_and_shape.py",
                "verifier_probe": "command-center/p2-wave/probes/TST-0147/probe1_both_states.py",
                "anchor": f"{git['fixture_path']}:{git['good_line']}",
                "signal": "b-git-cat-file",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0147-probe2-git-cat-file-and-shape",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "notes": (
                "Probe 2 re-runs git cat-file and the shape-only regex and does "
                "not author _c6_evidence. Not a fresh-context human reviewer."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0147/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": UNIT,
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {
                "path": "platform/lib/completion_predicate.py",
                "exists": True,
                "role": "completion-predicate",
            },
        ],
        "named_probes": [
            {
                "id": "probe1-both-states",
                "command": P1,
                "result": "PASS",
                "role": "condition-6-evaluate-off-by-1000",
            },
            {
                "id": "probe2-cat-file-and-shape",
                "command": P2,
                "result": "PASS",
                "role": "git-cat-file-and-shape-only-negative",
            },
        ],
        "required_fix": None,
        "residual_unknowns": [],
    }

    dest = REPO / OUT_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    text = dest.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:TST-0147 emit sentinel absent from file")
        return 1
    parsed = json.loads(text)
    if parsed.get("state") != "SUCCESS":
        print("FAILED:TST-0147 emit state is not SUCCESS")
        return 1
    if dest.stat().st_size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:TST-0147 emit below min_bytes_threshold size={dest.stat().st_size}")
        return 1
    print(f"wrote {OUT_REL} bytes={dest.stat().st_size}")
    print("SUCCESS:TST-0147 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
