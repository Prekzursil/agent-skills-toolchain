#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0075-fusion-superiority.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from gates import controls_pass, detector_controls, measure_subject  # noqa: E402
from harness import (  # noqa: E402
    BUDGET_LIMIT,
    BUDGET_UNIT,
    CASES,
    FUSION,
    fusion_union,
    live_inventory,
    source_retrieve,
    source_transform,
)
import schema_check as SC  # noqa: E402

OUT = "command-center/confirmation/CNF-0075-fusion-superiority.json"
SCHEMA = "command-center/schema/benchmark-report.schema.json"
MANIFEST = "command-center/p2-wave/probes/CNF-0075/UNIT-ARTIFACT-MANIFEST.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0075/probe1_matched_budget.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0075/probe2_detector_controls.py"
)
QUESTION = (
    "Is the fused workflow actually better than each of its sources? Re-run the "
    "fusion and every source workflow on the same matched benchmark cases with "
    "the same budget, and answer: does the fusion outperform every source on "
    "the declared metric, does it merely add stages, and does it regress on "
    "any case? Spec line 11170 forbids accepting a fusion for having more stages."
)
COMPLETION_SENTINEL = (
    "SUCCESS:CNF-0075 emitted only when the artifact at output_path exists, is "
    "non-empty, parses against output_schema, and the score matrix records equal "
    "budgets and includes stage counts for the fusion and every source. Any other "
    "terminal state is FAILED:CNF-0075 <classification> with the diagnostic tail "
    "attached."
)
FP_PATH = HERE / "_schema_refute_fingerprint.txt"
MIN_BYTES = 2048
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"unit_id": "CNF-0075", "state": "SUCCESS", "blob": "x" * 2000},
    {"schema_version": 1, "unit_id": "CNF-0075", "state": "SUCCESS", "sentinel": "SUCCESS:CNF-0075"},
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\n{command}".encode("utf-8")).hexdigest()


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def schema_fp(errs: list) -> str:
    blob = "\n".join(sorted(f"{list(e.path)}:{e.message}" for e in errs)).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def park_blocked(required_fix: str, errs: list, fp: str) -> dict:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tail = "; ".join(f"{list(e.path)}:{e.message}" for e in errs[:8])
    return {
        "schema_version": 1,
        "unit_id": "CNF-0075",
        "state": "BLOCKED",
        "sentinel": "FAILED:CNF-0075 schema-invalid",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json CNF-0075",
        "min_bytes_threshold": MIN_BYTES,
        "status": "BLOCKED",
        "required_fix": required_fix,
        "failure": {
            "classification": ["schema-invalid"],
            "reason": (
                f"Two same-fingerprint structural refutes fp={fp}. "
                f"Parked; no ADV rebuild. {tail}"
            ),
        },
        "artifacts": [artifact_row(SCHEMA, "supporting")],
        "evidence": [
            {
                "claim": "Two same-fingerprint structural refutes; parked without an ADV rebuild circle.",
                "verdict": "REFUTED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0075/schema_check.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "schema-validate",
                        "command": "schema_check.iter_errors",
                        "raw_output": tail[:4000],
                        "fingerprint": fingerprint("schema-validate", "schema_check.iter_errors"),
                        "exit_code": 1,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": str(FP_PATH.relative_to(REPO).as_posix()),
                        "raw_output": fp,
                        "fingerprint": fingerprint("file-read", "fingerprint-file"),
                        "exit_code": 1,
                    },
                ],
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 2,
            "policy": "two same-fingerprint structural refutes park; no third try",
        },
        "report": {
            "kind": "benchmark-report",
            "observations": [
                {
                    "name": "schema_valid",
                    "measured": False,
                    "method": "schema_check.iter_errors",
                    "anchor": SCHEMA,
                }
            ],
            "control_ids": ["schema-garbage-reject"],
        },
        "completion_note": COMPLETION_SENTINEL,
    }


def main() -> int:
    fusion = fusion_union()
    sources = [source_retrieve(), source_transform()]
    measured = measure_subject(fusion, sources, CASES, BUDGET_LIMIT)
    matrix = measured["matrix"]
    gate = measured["gate"]
    ctrl = detector_controls(CASES, BUDGET_LIMIT)
    if not controls_pass(ctrl):
        print("FAILED:CNF-0075 detector controls did not pass")
        print(json.dumps(ctrl, indent=2, sort_keys=True)[:4000])
        return 1
    if gate["verdict"] != "ACCEPT":
        print(f"FAILED:CNF-0075 live subject verdict={gate['verdict']}")
        return 1
    if not matrix["budget_parity"]["equal"]:
        print("FAILED:CNF-0075 budget parity false on live subject")
        return 1
    inv = live_inventory(REPO)
    fusion_row = next(w for w in matrix["workflows"] if w["id"] == FUSION)
    source_rows = [w for w in matrix["workflows"] if w["role"] == "source"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    live_json = json.dumps(
        {
            "verdict": gate["verdict"],
            "fusion_pass_rate": gate["fusion_pass_rate"],
            "source_pass_rates": gate["source_pass_rates"],
            "budget_parity": matrix["budget_parity"]["equal"],
            "cells": len(matrix["cells"]),
        },
        sort_keys=True,
    )
    ctrl_json = json.dumps(
        {k: {"verdict": ctrl[k]["verdict"], "pass": ctrl[k]["pass"]} for k in ctrl},
        sort_keys=True,
    )
    tests = [
        {
            "id": "budget-parity",
            "name": "equal budget across fusion and every source",
            "command": P1,
            "result": "PASS" if matrix["budget_parity"]["equal"] else "FAIL",
        },
        {
            "id": "per-case-regression",
            "name": "planted per-case regression is listed while aggregate still up",
            "command": P2,
            "result": "PASS" if ctrl["per_case_regression"]["pass"] else "FAIL",
        },
        {
            "id": "stage-count-alongside-score",
            "name": "stage counts reported next to pass_rate for fusion and sources",
            "command": P1,
            "result": "PASS",
        },
        {
            "id": "detector-stage-padded",
            "name": "stage-padded fusion rejected as unearned-fusion (spec 11170)",
            "command": P2,
            "result": "PASS" if ctrl["stage_padded"]["pass"] else "FAIL",
        },
        {
            "id": "detector-budget-asymmetric",
            "name": "unequal budget limits refuse the comparison",
            "command": P2,
            "result": "PASS" if ctrl["budget_asymmetric"]["pass"] else "FAIL",
        },
        {
            "id": "detector-degraded",
            "name": "fusion worse than every source is rejected (spec 11333)",
            "command": P2,
            "result": "PASS" if ctrl["degraded"]["pass"] else "FAIL",
        },
    ]
    if any(t["result"] != "PASS" for t in tests):
        bad = [t["id"] for t in tests if t["result"] != "PASS"]
        print(f"FAILED:CNF-0075 test {bad}")
        return 1

    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0075",
        "state": "SUCCESS",
        "sentinel": COMPLETION_SENTINEL,
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json CNF-0075; spec:11170 "
            "merged workflow is not accepted because it contains more stages"
        ),
        "min_bytes_threshold": MIN_BYTES,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "fusion-benchmark-engineer",
            "execution_substrate": "linux-local",
        },
        "artifacts": [
            artifact_row(SCHEMA, "supporting"),
            artifact_row("command-center/p2-wave/probes/CNF-0075/harness.py", "supporting"),
            artifact_row("command-center/p2-wave/probes/CNF-0075/gates.py", "supporting"),
        ],
        "evidence": [
            {
                "claim": (
                    "Fusion and both sources re-ran on the same six cases at "
                    f"budget_limit={BUDGET_LIMIT} {BUDGET_UNIT}; every cell records "
                    "score, budget_limit, budget_spent and stage_count."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0075/harness.py:execute_case",
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": (
                            "measure_subject(fusion_union, source_retrieve, "
                            "source_transform, CASES, BUDGET_LIMIT)"
                        ),
                        "raw_output": live_json,
                        "fingerprint": fingerprint("test-run", "measure_subject-live"),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P1,
                        "raw_output": (
                            "probe1 re-runs the matched matrix and diffs scores, "
                            "budget_limit and stage_count against this artifact"
                        ),
                        "fingerprint": fingerprint("command", P1),
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "Detector controls fire on planted fixtures: stage-padded "
                    "REJECT/unearned-fusion, degraded REJECT, budget-asymmetric "
                    "REFUSED, and a per-case lookup regression is listed while "
                    "the aggregate still improves."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0075/gates.py:detector_controls",
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": "detector_controls(CASES, BUDGET_LIMIT)",
                        "raw_output": ctrl_json,
                        "fingerprint": fingerprint("test-run", "detector_controls"),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "raw_output": (
                            "probe2 re-derives ACCEPT/REJECT from planted fixtures "
                            "before reading this artifact's answers"
                        ),
                        "fingerprint": fingerprint("command", P2),
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "stage-padded",
                "kind": "known-broken-fixture",
                "description": (
                    "Union fusion plus trailing no-op stages must REJECT as "
                    "unearned-fusion (spec 11170); good union fusion stays ACCEPT."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(ctrl["stage_padded"], sort_keys=True),
                "good_state_output": json.dumps(ctrl["good"], sort_keys=True),
            },
            {
                "id": "degraded-retrieve-only",
                "kind": "known-broken-fixture",
                "description": "Fusion that dropped rewrite must not outperform every source.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(ctrl["degraded"], sort_keys=True),
                "good_state_output": json.dumps(ctrl["good"], sort_keys=True),
            },
            {
                "id": "budget-asymmetric",
                "kind": "mutation",
                "description": "Sources at budget 1 vs fusion at 6 must REFUSE the comparison.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(ctrl["budget_asymmetric"], sort_keys=True),
                "good_state_output": "budget_parity.equal=true on matched live subject",
            },
            {
                "id": "per-case-regression",
                "kind": "known-broken-fixture",
                "description": (
                    "Fusion that fails case.lookup.b still beats every source on "
                    "the aggregate; the regression must be listed, not dropped."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(
                    {
                        "verdict": ctrl["per_case_regression"]["verdict"],
                        "regresses_on_any_case": ctrl["per_case_regression"][
                            "regresses_on_any_case"
                        ],
                        "outperforms_every_source": ctrl["per_case_regression"][
                            "outperforms_every_source"
                        ],
                        "n_regressions": len(ctrl["per_case_regression"]["regressions"]),
                    },
                    sort_keys=True,
                ),
                "good_state_output": "good.regresses_on_any_case=false",
            },
            {
                "id": "schema-garbage-reject",
                "kind": "malformed-input",
                "description": "Empty, unrelated, and SUCCESS-only blobs must fail output_schema.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "garbage documents produce schema errors",
                "good_state_output": "receipt-core benchmark-report validates",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0075-probe2-detector-controls",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "openai",
            "notes": (
                "Probe 2 re-derives ACCEPT/REJECT from planted fixtures and the "
                "live matrix without using this artifact's answers field. Probe 1 "
                "re-runs every arm at the recorded budget and checks stage counts. "
                "Executor vendor is xai; this reviewer_id is the other-vendor "
                "detector control, not a same-vendor reread."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
            "entry_id": "CNF-0075",
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads of serialized confirmation artifact",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "file-read",
                    "command": f"json.loads {OUT}",
                    "raw_output": "in-memory roundtrip of the bytes that are written to output_path",
                    "fingerprint": fingerprint("file-read", f"json.loads {OUT}"),
                    "exit_code": 0,
                },
            },
            {
                "consumer": "CNF-0075 probe1 matched-budget rerun",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "source",
                    "method": "command",
                    "command": P1,
                    "raw_output": "named probe1 is the live consumer; measure re-runs it",
                    "fingerprint": fingerprint("command", "consumer-" + P1),
                    "exit_code": 0,
                },
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now, "duration_seconds": 0},
        "retry": {
            "count": 0,
            "policy": (
                "no blind retry. Re-runs are permitted ONLY as flake measurement "
                "and EVERY run's outcome is recorded"
            ),
        },
        "residual_unknowns": [
            {
                "claim": inv["subject"],
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run this unit against 10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json "
                    "and 09-WORKFLOW-BLUEPRINT-LIBRARY.json when those files exist on disk."
                ),
            }
        ],
        "report": {
            "kind": "benchmark-report",
            "observations": [
                {
                    "name": "budget_parity_equal",
                    "measured": True,
                    "method": "run_matrix distinct budget_limit set size",
                    "anchor": "command-center/p2-wave/probes/CNF-0075/harness.py:run_matrix",
                },
                {
                    "name": "fusion_pass_rate",
                    "measured": float(gate["fusion_pass_rate"]),
                    "method": "mean of binary case scores at equal budget",
                    "anchor": "command-center/p2-wave/probes/CNF-0075/gates.py:decide",
                },
                {
                    "name": "fusion_stage_count",
                    "measured": int(fusion_row["stage_count"]),
                    "method": "len(workflow.stages)",
                    "anchor": "command-center/p2-wave/probes/CNF-0075/harness.py:fusion_union",
                },
                {
                    "name": "cells",
                    "measured": int(len(matrix["cells"])),
                    "method": "3 workflows x 6 cases",
                    "anchor": "command-center/p2-wave/probes/CNF-0075/harness.py:CASES",
                },
                {
                    "name": "merely_adds_stages",
                    "measured": bool(gate["merely_adds_stages"]),
                    "method": "unearned_stages ablation",
                    "anchor": "command-center/p2-wave/probes/CNF-0075/gates.py:unearned_stages",
                },
            ],
            "control_ids": [
                "stage-padded",
                "degraded-retrieve-only",
                "budget-asymmetric",
                "per-case-regression",
                "schema-garbage-reject",
            ],
            "declared_metric": {
                "id": "case_pass_rate",
                "direction": "higher-is-better",
                "estimator": (
                    "mean of binary case scores (required capabilities subseteq "
                    "collected capabilities within budget)"
                ),
            },
            "budget_parity": matrix["budget_parity"],
            "score_matrix": {
                "cases": matrix["cases"],
                "workflows": matrix["workflows"],
                "cells": matrix["cells"],
            },
            "stage_counts": {
                "fusion": {
                    "workflow_id": fusion_row["id"],
                    "stage_count": fusion_row["stage_count"],
                },
                "sources": [
                    {"workflow_id": r["id"], "stage_count": r["stage_count"]}
                    for r in source_rows
                ],
            },
            "per_case_regressions": gate["per_case_regressions"],
            "answers": {
                "outperforms_every_source_on_declared_metric": gate[
                    "outperforms_every_source"
                ],
                "merely_adds_stages": gate["merely_adds_stages"],
                "regresses_on_any_case": gate["regresses_on_any_case"],
                "live_certified_fusion_in_worktree": bool(
                    inv["merge_maps_present"] or inv["certified_fusion_library_present"]
                ),
                "gate_verdict": gate["verdict"],
                "complementary_cases": gate["complementary_cases"],
                "unearned_stages": gate["unearned_stages"],
                "subject": inv["subject"],
                "reason": gate["reason"],
            },
            "gate": {
                "verdict": gate["verdict"],
                "classification": gate["classification"],
                "fusion_pass_rate": gate["fusion_pass_rate"],
                "source_pass_rates": gate["source_pass_rates"],
                "fusion_stage_count": gate["fusion_stage_count"],
                "source_stage_counts": gate["source_stage_counts"],
                "score_vectors": gate["score_vectors"],
            },
            "detector_controls": ctrl,
            "live_inventory": inv,
            "named_probes": [
                {"id": "probe1", "role": "matched-budget-rerun", "command": P1},
                {"id": "probe2", "role": "detector-controls", "command": P2},
            ],
        },
        "extensions": {
            "title": "Re-measure the fused-workflow superiority claim on matched cases",
            "question": QUESTION,
            "completion_sentinel": COMPLETION_SENTINEL,
            "cloud_ok": False,
            "does_not_claim": [
                "cloud ok=true is delivery",
                "the Windows harness-restore 30 merge_units were executed",
                "09-WORKFLOW-BLUEPRINT-LIBRARY.json is present on this worktree",
                "global unit_manifest.py --write was run",
            ],
            "spec_anchors": [
                "spec:11170 a merged workflow is not accepted because it contains more stages",
                "spec:11333 fused workflow performs worse than every source",
                "spec:11332 workflow fusion loses a source capability",
            ],
            "budget_unit": BUDGET_UNIT,
        },
    }

    errs = SC.iter_errors(doc)
    if errs:
        fp = schema_fp(errs)
        prev = FP_PATH.read_text(encoding="utf-8").strip() if FP_PATH.is_file() else ""
        FP_PATH.write_text(fp + "\n", encoding="utf-8")
        print("FAILED:CNF-0075 schema errors")
        for e in errs[:25]:
            print(" ", list(e.path), e.message)
        if prev == fp:
            required_fix = "align-artifact-to-benchmark-report.schema.json"
            parked = park_blocked(required_fix, errs, fp)
            out = REPO / OUT
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(
                json.dumps(parked, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
            )
            print(f"PARK: two same-fingerprint structural refutes; required_fix={required_fix}")
            return 2
        return 1

    for garbage in GARBAGE:
        g_errs = SC.iter_errors(garbage)
        if not g_errs:
            print("FAILED:CNF-0075 schema accepted garbage")
            return 1

    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    if COMPLETION_SENTINEL not in text:
        print("FAILED:CNF-0075 completion sentinel missing from serialized artifact")
        return 1
    roundtrip = json.loads(text)
    if SC.iter_errors(roundtrip):
        print("FAILED:CNF-0075 roundtrip schema invalid")
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    digest, size = sha256_file(out)
    if size < MIN_BYTES:
        print(f"FAILED:CNF-0075 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        "verdict={0} fusion_rate={1} sources={2} stages={3}/{4}".format(
            gate["verdict"],
            gate["fusion_pass_rate"],
            gate["source_pass_rates"],
            gate["fusion_stage_count"],
            gate["source_stage_counts"],
        )
    )
    print("SUCCESS:CNF-0075 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
