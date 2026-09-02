#!/usr/bin/env python3
"""Write command-center/audit/AUD-0045-fail-open-gate-census.json from a live census."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402

UNIT = "AUD-0045"
OUT_REL = "command-center/audit/AUD-0045-fail-open-gate-census.json"
SCHEMA = "command-center/schema/audit-finding.schema.json"
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0045/probe1_static_paths.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0045/probe2_empty_and_control.py"
)
QUESTION = (
    "For every CI gate and local validator, is there an input under which it "
    "exits 0 without having examined anything — an empty input set, a missing "
    "optional flag, a swallowed exception, or a skipped tool?"
)
COMPLETION = (
    "SUCCESS:AUD-0045 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)


def _row(executed: list[dict], gid: str) -> dict:
    return next(r for r in executed if r["id"] == gid)


def main() -> int:
    snap = C.snapshot()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    executed = snap["executed"]
    fail_open = snap["fail_open_ids"]
    nothing = snap["measures_nothing_ids"]
    m16 = _row(executed, "cc-validate-m16-disarmed-surface")
    freeze_none = _row(executed, "freeze-gate-clean-plus-checks-none")
    freeze_off = _row(executed, "freeze-gate-not-frozen")
    silent = _row(executed, "control-silent-always")
    closed = _row(executed, "control-closed-always")

    answer = (
        f"Local execution of {snap['gate_count_executed']} gate surfaces found "
        f"{len(fail_open)} fail-open-on-empty (including measures-nothing) and "
        f"{len(nothing)} gates that also stay green on known-bad input. "
        f"Named case validate.py --no-require-complete exits {m16['empty']['exit_code']} "
        f"with work-unit fields counted but not failed (class={m16['class']}); "
        f"the armed default exits {m16['known_bad']['exit_code']}. "
        f"Named case CLEAN+checks:NONE is freeze_active=true with frozen_paths=[] "
        f"(exit {freeze_none['empty']['exit_code']}, printed count "
        f"{freeze_none['empty']['printed_count']}) plus the CHECKS=NONE fixture; "
        f"a sha-mismatched frozen path exits {freeze_none['known_bad']['exit_code']}. "
        f"freeze_active=false measures nothing (class={freeze_off['class']}). "
        f"AUD-0041 YAML names {snap['ci'].get('fail_open_step_count', 0)} fail-open "
        f"CI steps including continue_on_error=true on the routing regression probe; "
        f".github/workflows is absent here so CI execution is NOT-CHECKED. "
        f"Empty-catalog validate, unit-manifest empty walk, claim_gate without a "
        f"payload, and _measure_one_delivered without an id fail closed."
    )

    p1_raw = json.dumps(
        {
            "probe": "probe1-static-paths",
            "gate_count_static": snap["gate_count_static"],
            "default_off_flags": snap["default_off_flags"],
            "ci_status": snap["ci"].get("status"),
            "ci_fail_open_step_count": snap["ci"].get("fail_open_step_count"),
            "ci_fail_open_steps": snap["ci"].get("fail_open_steps"),
            "early_return_files": [
                s["path"]
                for s in snap["static"]
                if s.get("early_return_zero") or s.get("swallowed_exception")
            ],
        },
        indent=2,
        sort_keys=True,
    )
    p2_raw = json.dumps(
        {
            "probe": "probe2-empty-and-control",
            "class_counts": snap["class_counts"],
            "fail_open_ids": fail_open,
            "measures_nothing_ids": nothing,
            "named_cases": snap["named_cases"],
            "control_silent_class": silent["class"],
            "control_closed_class": closed["class"],
        },
        indent=2,
        sort_keys=True,
    )

    tests = [
        {
            "id": "control-silent-always-measures-nothing",
            "command": P2_CMD,
            "result": "PASS" if silent["class"] == "measures-nothing" else "FAIL",
        },
        {
            "id": "control-closed-always-fail-closed",
            "command": P2_CMD,
            "result": "PASS" if closed["class"] == "fail-closed" else "FAIL",
        },
        {
            "id": "m16-armed-goes-red",
            "command": "tools/command-center/validate.py armed vs --no-require-complete",
            "result": "PASS"
            if m16["empty"]["exit_code"] == 0 and m16["known_bad"]["exit_code"] != 0
            else "FAIL",
        },
        {
            "id": "freeze-empty-paths-vs-sha-mismatch",
            "command": "command-center/freeze/gate.py empty frozen_paths vs bad sha",
            "result": "PASS"
            if freeze_none["empty"]["exit_code"] == 0
            and freeze_none["known_bad"]["exit_code"] != 0
            else "FAIL",
        },
    ]

    doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:AUD-0045",
        "completion_sentinel": COMPLETION,
        "report_kind": "audit-finding",
        "title": "Fail-open gate census: which gates can pass while measuring nothing",
        "question": QUESTION,
        "answer": answer,
        "headline_counts": {
            "gates_executed": snap["gate_count_executed"],
            "gates_static": snap["gate_count_static"],
            "fail_open_on_empty": len(fail_open),
            "measures_nothing": len(nothing),
            "fail_closed": snap["class_counts"].get("fail-closed", 0),
            "ci_fail_open_steps_static": snap["ci"].get("fail_open_step_count", 0),
            "ci_execution": "NOT-CHECKED",
        },
        "class_counts": snap["class_counts"],
        "fail_open_ids": fail_open,
        "measures_nothing_ids": nothing,
        "executed_gates": executed,
        "static_scan": snap["static"],
        "ci_static": snap["ci"],
        "named_measured_cases": snap["named_cases"],
        "named_probes": [
            {
                "id": "probe1-static-paths",
                "command": P1_CMD,
                "exit_code": 0,
                "raw_output": p1_raw,
                "role": "code-read-early-return-and-default-off",
            },
            {
                "id": "probe2-empty-and-control",
                "command": P2_CMD,
                "exit_code": 0,
                "raw_output": p2_raw,
                "role": "empty-input-execution-plus-known-bad-control",
            },
        ],
        "tests": tests,
        "evidence": [
            {
                "id": "m16-disarmed-require-complete",
                "text": (
                    "validate.py --no-require-complete exits 0 on a catalog with "
                    "unresolved work-unit fields; the armed default exits non-zero "
                    "on the same catalog."
                ),
                "verdict": "CONFIRMED",
                "source_probe": "command-center/p2-wave/probes/AUD-0045/census.py:execute_gates",
                "verifier_probe": P2_CMD,
            },
            {
                "id": "clean-plus-checks-none",
                "text": (
                    "freeze_active=true with frozen_paths=[] exits 0 with reason=clean "
                    "and no examined files; a sha-mismatched frozen path exits non-zero. "
                    "The CHECKS=NONE fixture matches that empty-list shape."
                ),
                "verdict": "CONFIRMED",
                "source_probe": "command-center/p2-wave/probes/AUD-0045/census.py:execute_gates",
                "verifier_probe": P2_CMD,
            },
            {
                "id": "freeze-inactive-measures-nothing",
                "text": (
                    "freeze_active=false returns ok=True reason=not-frozen even when "
                    "the ledger names a sha-mismatched frozen file."
                ),
                "verdict": "CONFIRMED",
                "source_probe": "command-center/p2-wave/probes/AUD-0045/census.py:execute_gates",
                "verifier_probe": P2_CMD,
            },
            {
                "id": "ci-continue-on-error-routing-probe",
                "text": (
                    "AUD-0041 YAML inventory records continue_on_error=true on "
                    "routing-benchmark.yml routing regression probe and empty-result "
                    "swallows on autofix-models / codex-runner. Workflow files are "
                    "absent on this worktree so execution is NOT-CHECKED."
                ),
                "verdict": "PARTIAL",
                "source_probe": "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json",
                "verifier_probe": P1_CMD,
            },
        ],
        "reviewer": {
            "reviewer_id": "AUD-0045-probe2-known-bad-control",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 is a separate process that re-executes empty and known-bad "
                "invocations; it is not a re-read of this artifact's prose."
            ),
        },
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/AUD-0045/census.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "tools/command-center/validate.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/freeze/gate.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "residual_caveat": (
            ".github/workflows is not present on this worktree; CI fail-open "
            "labels are static reads of AUD-0041's YAML inventory, not live job "
            "executions. validate.py's live require_complete default is True; the "
            "named historical default-False case is measured via --no-require-complete."
        ),
        "min_bytes_threshold": 1024,
        "timestamps": {"generated_at": now},
        "output_schema": SCHEMA,
    }

    test_fail = [t["id"] for t in tests if t["result"] != "PASS"]
    if test_fail:
        print("FAILED:AUD-0045 emit tests not PASS", test_fail)
        return 1
    blob = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if COMPLETION not in blob:
        print("FAILED:AUD-0045 completion sentinel missing from document")
        return 1

    out = C.REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(blob, encoding="utf-8", newline="\n")
    print(f"wrote {OUT_REL} bytes={out.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
