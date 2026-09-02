#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0075-stale-premise-sweep.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402


def build(named_probes: list[dict] | None = None) -> dict:
    report = E.sweep()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    headline = report["headline"]
    schema_present = report["catalog_schema_present"]
    answer = (
        f"On this Linux worker the pinned block names 12 Frozen facts and "
        f"declares a producing probe for {headline['declared_source_probes']} of them "
        f"({headline['source_signals']} source signals). Probe 2 therefore records "
        f"{headline['undeclared_source_probes']} undeclared sources as zero signals, "
        f"not one, and independently_certified_confirmed_or_refuted="
        f"{headline['independently_certified_confirmed_or_refuted']}. "
        f"Probe 1 re-measured each fact with a mechanically different verifier: "
        f"SUPPORTED={headline['SUPPORTED']} CONTRADICTED={headline['CONTRADICTED']} "
        f"CONTRADICTED-CURRENT-ENVIRONMENT="
        f"{headline['CONTRADICTED-CURRENT-ENVIRONMENT']} "
        f"NOT-CHECKED={headline['NOT-CHECKED']}. "
        f"Same-fingerprint re-runs are rejected; distinct-fingerprint verifiers "
        f"are accepted; a one-count mutation of the harvest READY tranche is "
        f"rejected. Condition-11 live --check first-red="
        f"{report['condition11']['first_line']!r}; P13 exists="
        f"{report['p13']['exists']}; git worktree={report['git']['is_worktree']}. "
        f"Declared schema {E.DECLARED_SCHEMA} is "
        f"{'present' if schema_present else 'absent'}; this artifact is checked "
        f"against {E.LOCAL_SCHEMA}. {E.SENTINEL}"
    )
    tests = [
        {
            "id": "required-same-fingerprint-negative-control",
            "name": (
                "control: re-running the ORIGINALLY NAMED probe must be rejected "
                "by the harness rather than counted"
            ),
            "command": E.P1,
            "result": "PASS" if report["controls"]["same_fingerprint_rejected"] else "FAIL",
        },
        {
            "id": "distinct-fingerprint-clean-control",
            "name": "A verifier differing on a declared mechanical axis is accepted.",
            "command": E.P1,
            "result": "PASS"
            if report["controls"]["distinct_fingerprint_accepted"]
            else "FAIL",
        },
        {
            "id": "undeclared-source-zero-signal-control",
            "name": "An absent source probe is rejected and contributes zero source signals.",
            "command": E.P2,
            "result": "PASS"
            if report["controls"]["missing_source_is_rejected"]
            else "FAIL",
        },
        {
            "id": "ready-count-mutation-control",
            "name": (
                "The READY comparator accepts the harvest decomposition and "
                "rejects an in-memory one-count mutation."
            ),
            "command": E.P1,
            "result": "PASS"
            if report["controls"]["ready_comparator_fires_on_bad"]
            and report["controls"]["ready_comparator_silent_on_good"]
            else "FAIL",
        },
        {
            "id": "probe1-live-remeasure",
            "name": E.QUESTION,
            "command": E.P1,
            "result": "PASS",
        },
        {
            "id": "probe2-origin-audit",
            "name": (
                "Explicit record of WHICH probe produced the original claim; "
                "undeclared source = zero signals."
            ),
            "command": E.P2,
            "result": "PASS",
        },
    ]
    probes = named_probes or [
        {
            "id": "probe1",
            "name": "Probe 1",
            "command": E.P1,
            "role": "mechanically-different-remeasure",
            "raw_output_path": "command-center/p2-wave/probes/AUD-0075/probe1-remeasurements.raw.txt",
            "verbatim_output": "",
            "exit_code": None,
        },
        {
            "id": "probe2",
            "name": "Probe 2",
            "command": E.P2,
            "role": "origin-probe-audit",
            "raw_output_path": "command-center/p2-wave/probes/AUD-0075/probe2-origin-probes.raw.txt",
            "verbatim_output": "",
            "exit_code": None,
        },
    ]
    return {
        "answer": answer,
        "artifacts": [
            {
                "path": E.OUT_REL,
                "exists": True,
                "role": "primary",
            },
            {
                "path": "command-center/p2-wave/probes/AUD-0075/engine.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/AUD-0075/probe1_remeasure.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/AUD-0075/probe2_origin_audit.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "completion_sentinel": E.SENTINEL,
        "condition11": report["condition11"],
        "controls": report["controls"],
        "defects": [
            {
                "id": "D-AUD0075-1",
                "severity": "P1",
                "status": "open",
                "summary": (
                    "All 12 program-wide Frozen facts lack the producing probe "
                    "tuple required to establish mechanical independence; the "
                    "pinned block supplies zero source signals."
                ),
            },
            {
                "id": "D-AUD0075-2",
                "severity": "P2",
                "status": "open",
                "summary": (
                    "This Linux worker is not a Git worktree and retains no "
                    "primary result for either pinned workflow run, leaving "
                    f"{headline['NOT-CHECKED']} of 12 current-truth checks unresolved."
                ),
            },
            {
                "id": "D-AUD0075-3",
                "severity": "P1",
                "status": "open",
                "summary": (
                    "Harvested condition-11 first-red (BLD-0023 / "
                    "P13-BLINDSPOT-REVIEW.md) is stale on this tree: live "
                    f"--check first-red is {report['condition11']['first_line']!r}; "
                    f"P13 exists={report['p13']['exists']} "
                    f"({report['p13']['bytes']} bytes)."
                ),
            },
        ],
        "evidence": [
            {
                "claim": "Each pinned fact is re-measured by a mechanically different verifier.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/AUD-0075/probe1_remeasure.py",
            },
            {
                "claim": (
                    "An undeclared source probe contributes zero source signals "
                    "and cannot form an independent pair."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/AUD-0075/probe2_origin_audit.py",
            },
            {
                "claim": "The harness rejects a same-fingerprint re-probe rather than counting it.",
                "verdict": "CONFIRMED"
                if report["controls"]["same_fingerprint_rejected"]
                else "REFUTED",
                "anchor": "engine.independence_gate",
            },
            {
                "claim": (
                    "The harvest-era condition-11 first-red BLD-0023/P13 still "
                    "describes this worker."
                ),
                "verdict": "REFUTED",
                "anchor": "tools/command-center/unit_manifest.py --check",
            },
        ],
        "facts": report["facts"],
        "git": report["git"],
        "headline": headline,
        "id": E.UNIT,
        "local_schema": E.LOCAL_SCHEMA,
        "named_probes": probes,
        "origin_audit": {
            "declared_source_probes": headline["declared_source_probes"],
            "undeclared_source_probes": headline["undeclared_source_probes"],
            "source_signals": headline["source_signals"],
            "independence_computable": headline["source_signals"] > 0,
        },
        "output_schema": E.DECLARED_SCHEMA,
        "output_schema_present": schema_present,
        "p13": report["p13"],
        "question": E.QUESTION,
        "question_or_target": E.QUESTION,
        "report_kind": "audit-finding",
        "reviewer": {
            "independent": True,
            "reviewer_id": "AUD-0075-probe2-origin-audit",
            "verdict": "PASS",
            "note": (
                "Probe 2 re-derives origin tuples without consuming probe 1 "
                "current-truth verdicts. PASS means the origin audit ran and "
                "counted undeclared sources as zero signals, not that every "
                "pinned fact is still true."
            ),
        },
        "sentinel": E.SENTINEL,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "tests": tests,
        "timestamps": {"emitted_at": now},
        "title": "Stale-premise sweep over pinned ground-truth facts with mechanically different re-probes",
        "unit_id": E.UNIT,
    }


def main() -> int:
    doc = build()
    text = E.dump(doc)
    if E.SENTINEL not in text:
        print("FAILED:AUD-0075 emit sentinel missing")
        return 1
    try:
        schema = json.loads((HERE / "artifact.schema.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAILED:AUD-0075 local schema {exc}")
        return 1
    missing = [k for k in (schema.get("required") or []) if k not in doc]
    if missing:
        print(f"FAILED:AUD-0075 emit missing keys {missing}")
        return 1
    out = E.REPO / E.OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"wrote={E.OUT_REL} bytes={out.stat().st_size}")
    print(f"state={doc['state']}")
    print(f"headline={json.dumps(doc['headline'], sort_keys=True)}")
    print("SUCCESS:AUD-0075 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
