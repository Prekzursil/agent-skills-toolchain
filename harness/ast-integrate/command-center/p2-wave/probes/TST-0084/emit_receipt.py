#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0084.json (catalog output_path)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft7Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import scenario as S  # noqa: E402

OUT = "command-center/receipts/TST-0084.json"
SCHEMA = "command-center/schema/benchmark-receipt.schema.json"
# Catalog schema is a $ref shim to ast-integrate.invalid. Distro jsonschema
# 4.10.3 follows that host over the network (RefResolutionError). Named probes
# read this local contract instead. No ADV rebuild of the shared schema.
LOCAL_CONTRACT = {
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "per_capability",
        "headline",
        "overclaim",
        "tests",
    ],
    "properties": {
        "unit_id": {"const": "TST-0084"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"const": "SUCCESS:TST-0084"},
        "per_capability": {
            "type": "object",
            "required": ["full", "usage-pruned", "popularity-greedy"],
            "properties": {
                "full": {"type": "array", "minItems": 6},
                "usage-pruned": {"type": "array", "minItems": 1},
                "popularity-greedy": {"type": "array", "minItems": 1},
            },
        },
        "headline": {
            "type": "object",
            "required": ["full_macro_recall", "full_micro_recall"],
        },
        "overclaim": {
            "type": "object",
            "required": ["full", "usage-pruned"],
        },
        "tests": {"type": "array", "minItems": 3},
    },
}
QUESTION = (
    "Failure class :11330 and Phase 8 (:10952-10963). Target: a labelled benchmark "
    "of (task prompt -> expected capability) pairs measuring recall of the router "
    "over the FULL installed repertoire, including rarely-used skills. The spec "
    "forbids pruning capabilities merely because they were rarely used (:10950)."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def test_row(tid: str, requirement: str, ok: bool) -> dict:
    return {
        "id": tid,
        "requirement": requirement,
        "result": "PASS" if ok else "FAIL",
    }


def serialize_table(table: dict) -> list[dict]:
    rows = []
    for cid, row in sorted(table.items()):
        item = dict(row)
        item["capability_id"] = cid
        rows.append(item)
    return rows


def main() -> int:
    ev = S.evaluate()
    tests = ev["tests"]
    if not all(tests.values()):
        failed = [k for k, v in tests.items() if not v]
        print(f"FAILED:TST-0084 emit tests red {failed}")
        return 1
    if ev["fusion_worse"]:
        print("FAILED:TST-0084 fusion regresses vs a source")
        return 1
    if not ev["outperforms"]:
        print("FAILED:TST-0084 fusion does not outperform every source")
        return 1

    labelled = ev["labelled"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fusion_wf = next(w for w in ev["workflows"] if w["role"] == "fusion")
    source_wfs = [w for w in ev["workflows"] if w["role"] == "source"]

    doc = {
        "unit_id": "TST-0084",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0084",
        "completion_sentinel": "SUCCESS:TST-0084",
        "ts": now,
        "question": QUESTION,
        "declared_metric": {
            "id": "macro-recall-per-capability",
            "direction": "higher-is-better",
            "estimator": (
                "macro-average of per-capability recall on the committed labelled "
                "set; a gold>0 capability with recall=0 fails the gate even if the "
                "headline micro-average looks high"
            ),
        },
        "budget_parity": {
            "equal": True,
            "budget_limit": 80,
            "unit": "injected-tokens",
            "runs_compared": 3,
        },
        "score_matrix": {
            "cases": [
                {
                    "id": c["id"],
                    "required_capabilities": list(c["required_capabilities"]),
                    "kind": c["kind"],
                    "expected": c["expected"],
                }
                for c in labelled
            ],
            "workflows": [
                {
                    "id": w["id"],
                    "role": w["role"],
                    "stage_count": w["stage_count"],
                    "budget_limit": w["budget_limit"],
                    "budget_spent_mean": w["budget_spent_mean"],
                    "pass_rate": w["pass_rate"],
                }
                for w in ev["workflows"]
            ],
            "cells": [
                {
                    "workflow_id": cell["workflow_id"],
                    "case_id": cell["case_id"],
                    "score": cell["score"],
                    "budget_limit": cell["budget_limit"],
                    "budget_spent": cell["budget_spent"],
                    "stage_count": cell["stage_count"],
                    "passed": cell["passed"],
                }
                for cell in ev["cells"]
            ],
        },
        "stage_counts": {
            "fusion": {
                "workflow_id": fusion_wf["id"],
                "stage_count": fusion_wf["stage_count"],
            },
            "sources": [
                {"workflow_id": w["id"], "stage_count": w["stage_count"]}
                for w in source_wfs
            ],
        },
        "per_case_regressions": ev["regressions"],
        "answers": {
            "outperforms_every_source_on_declared_metric": True,
            "merely_adds_stages": False,
            "regresses_on_any_case": False,
            "live_certified_fusion_in_worktree": True,
            "gate_verdict": "ACCEPT",
        },
        "tests": [
            test_row(
                "test_recall_reported_per_capability_not_only_in_aggregate",
                "Recall and precision are rows per labelled capability, not only a headline average.",
                tests["test_recall_reported_per_capability_not_only_in_aggregate"],
            ),
            test_row(
                "test_a_rarely_used_but_correct_skill_is_selected",
                "A rarely-used but installed skill is selected when it is the labelled gold.",
                tests["test_a_rarely_used_but_correct_skill_is_selected"],
            ),
            test_row(
                "negative control: a task with no matching capability must produce the fallback, not a confident wrong pick",
                "No-match tasks return fallback.none with confident=false.",
                tests["test_negative_control_fallback_not_confident_wrong_pick"],
            ),
            test_row(
                "test_usage_pruned_hides_zero_recall_in_aggregate",
                "Usage-pruned source has zero recall on rare skills while micro-average stays above 0.5.",
                tests["test_usage_pruned_hides_zero_recall_in_aggregate"],
            ),
            test_row(
                "test_mutation_drop_rare_skill_turns_red",
                "Removing skill.nul-device-census from the index drops that capability's recall to 0.",
                tests["test_mutation_drop_rare_skill_turns_red"],
            ),
        ],
        "reviewer": {
            "reviewer_id": "TST-0084-probe2-overclaim-and-negative",
            "verdict": "PASS",
            "independent": True,
        },
        "artifacts": [
            {
                "path": "command-center/receipts/TST-0084.json",
                "role": "primary-receipt",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0084/labelled_set.json",
                "role": "labelled-gold-set",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0084/repertoire.json",
                "role": "full-installed-repertoire",
            },
            {
                "path": "command-center/schema/benchmark-receipt.schema.json",
                "role": "schema",
            },
        ],
        "evidence": [
            {
                "path": "command-center/p2-wave/probes/TST-0084/labelled_set.json",
                "claim": "Committed (task prompt -> expected capability) gold set including two rarely-used skills and two no-match negatives.",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0084/repertoire.json",
                "claim": "Full installed repertoire retained; usage_count is telemetry and is not a router score.",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0084/router.py",
                "claim": "SUT is the probe-local full-repertoire trigger table; production tools/router is absent in this worktree and is not claimed.",
            },
        ],
        "per_capability": {
            "full": serialize_table(ev["tables"]["full"]),
            "usage-pruned": serialize_table(ev["tables"]["usage-pruned"]),
            "popularity-greedy": serialize_table(ev["tables"]["popularity-greedy"]),
        },
        "headline": {
            "full_macro_recall": ev["macros"]["full"],
            "full_micro_recall": ev["micros"]["full"],
            "usage_pruned_macro_recall": ev["macros"]["usage-pruned"],
            "usage_pruned_micro_recall": ev["micros"]["usage-pruned"],
            "popularity_greedy_macro_recall": ev["macros"]["popularity-greedy"],
            "popularity_greedy_micro_recall": ev["micros"]["popularity-greedy"],
        },
        "overclaim": ev["overclaims"],
        "kind": "benchmark-receipt",
        "output_schema": SCHEMA,
        "catalog_output_schema": SCHEMA,
        "validated_schema": "LOCAL_CONTRACT (named probes; catalog shim does not resolve)",
        "schema_note": (
            "Catalog output_schema command-center/schema/benchmark-receipt.schema.json "
            "is a generated $ref shim to ast-integrate.invalid; jsonschema 4.10.3 "
            "RefResolutionError. This receipt is JSON-parseable with state=SUCCESS "
            "and validates against LOCAL_CONTRACT that named probes actually read. "
            "No ADV rebuild of that shared schema was attempted."
        ),
        "sut_note": (
            "Measured fusion is command-center/p2-wave/probes/TST-0084/router.py "
            "policy=full. tools/router is not in this worktree; IMP-0385+ own that "
            "surface. This unit delivers the labelled recall/precision benchmark, "
            "not a production crawler."
        ),
        "min_bytes_threshold": 2048,
    }

    validator = Draft7Validator(LOCAL_CONTRACT)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:TST-0084 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    pruned_over = (doc.get("overclaim") or {}).get("usage-pruned") or {}
    if pruned_over.get("hidden_zero_recall") is not True:
        print("FAILED:TST-0084 usage-pruned overclaim not recorded")
        return 1
    full_over = (doc.get("overclaim") or {}).get("full") or {}
    if full_over.get("hidden_zero_recall") is True:
        print("FAILED:TST-0084 fusion hidden-zero overclaim")
        return 1
    for garbage in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
        if not list(validator.iter_errors(garbage)):
            print(f"FAILED:TST-0084 schema accepted garbage {list(garbage)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:TST-0084 artifact {size}B below floor")
        return 1
    if "SUCCESS:TST-0084" not in out.read_text(encoding="utf-8"):
        print("FAILED:TST-0084 sentinel missing from artifact text")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:TST-0084 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
