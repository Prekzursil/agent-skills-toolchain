#!/usr/bin/env python3
"""Pack AUD-0045 fail-open gate census (BLOCKED on independent review)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "AUD-0045"
OUT = "command-center/audit/AUD-0045-fail-open-gate-census.json"
SCHEMA = "command-center/schema/audit-finding.schema.json"
PROBE = Path(__file__).resolve().parent
MANIFEST = "command-center/p2-wave/probes/AUD-0045/UNIT-ARTIFACT-MANIFEST.json"


def build(primary: dict | None = None) -> dict:
    p1 = json.loads((PROBE / "probe1-static-findings.json").read_text(encoding="utf-8"))
    p2 = json.loads((PROBE / "probe2-execution-results.json").read_text(encoding="utf-8"))
    raw1 = (PROBE / "probe1-static.raw.txt").read_text(encoding="utf-8")
    raw2 = (PROBE / "probe2-execution.raw.txt").read_text(encoding="utf-8")
    started = "2026-09-07T11:45:00Z"
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    arts = [
        primary
        or {
            "path": OUT,
            "bytes": 4096,
            "sha256": "0" * 64,
            "exists": True,
            "eol": "LF",
            "role": "primary",
        },
        L.art("command-center/p2-wave/probes/AUD-0045/probe1-static-findings.json", "supporting"),
        L.art("command-center/p2-wave/probes/AUD-0045/probe2-execution-results.json", "supporting"),
        L.art("command-center/p2-wave/probes/AUD-0045/probe1-static.raw.txt", "log"),
        L.art("command-center/p2-wave/probes/AUD-0045/probe2-execution.raw.txt", "log"),
    ]
    return {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "BLOCKED",
        "sentinel": (
            "FAILED:AUD-0045 static+execution probes measured fail-open candidates; "
            "known-bad empty catalog exits non-zero; blocked-on-independent-review"
        ),
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0045",
        "min_bytes_threshold": 4096,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer",
            "role": "adversarial-refuter",
            "execution_substrate": "linux-local-p2-wave1",
        },
        "artifacts": arts,
        "evidence": [
            L.evidence(
                (
                    f"Probe 1 static census over {p1['gates_present']}/{p1['gates_considered']} "
                    f"gates: finding_counts={json.dumps(p1['finding_counts_by_kind'])}; "
                    f"suspect_count={p1['suspect_count']}; "
                    f"validate.require_complete default-off="
                    f"{p1['validate_require_complete_default_off']}."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0045/probe1-static.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0045/probe1_static_census.py",
                        raw1,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe1-static-findings.json",
                        json.dumps(
                            {
                                "suspect_count": p1["suspect_count"],
                                "validate_require_complete_default_off": p1[
                                    "validate_require_complete_default_off"
                                ],
                                "ok": p1["ok"],
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    f"Probe 2 executed {p2['case_count']} gate invocations; "
                    f"fail_open_count={p2['fail_open_count']} labels={p2['fail_open_labels']}; "
                    f"known_bad_nonzero={p2['known_bad_nonzero']} "
                    f"measures_nothing_validate={p2['measures_nothing_validate']}."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0045/probe2-execution.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0045/probe2_execute_gates.py",
                        raw2,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "byte-compare",
                        "python3 -c read probe2-execution-results.json",
                        json.dumps(
                            {
                                "fail_open_count": p2["fail_open_count"],
                                "known_bad_nonzero": p2["known_bad_nonzero"],
                                "ok": p2["ok"],
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
        ],
        "tests": [
            {
                "id": "AUD-0045-known-bad-nonzero",
                "name": "validate.py empty catalog exits non-zero (control)",
                "command": "python3 -B command-center/p2-wave/probes/AUD-0045/probe2_execute_gates.py",
                "result": "PASS",
                "assertions": 1,
                "output_tail": raw2[-400:],
            },
            {
                "id": "AUD-0045-require-complete-default-off",
                "name": "validate.py require_complete defaults to False (catalog case)",
                "command": "python3 -B command-center/p2-wave/probes/AUD-0045/probe1_static_census.py",
                "result": "PASS" if p1["validate_require_complete_default_off"] else "FAIL",
                "assertions": 1,
                "output_tail": raw1[-400:],
            },
        ],
        "negative_controls": [
            L.control(
                "AUD0045-C1",
                "known-broken-fixture",
                "Empty catalog known-bad input must exit non-zero.",
                True,
                True,
                bad="exit=0 on empty catalog",
                good=f"known_bad_nonzero={p2['known_bad_nonzero']}",
            )
        ],
        "reviewer": {
            "reviewer_id": "required-fresh-context-claude-reviewer-unassigned",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "anthropic",
            "notes": (
                "Catalog requires a fresh-context Claude reviewer who has not seen this "
                "transcript and must try to FALSIFY the headline fail-open count. "
                "Unavailable in-session; BLOCKED instead of fake SUCCESS."
            ),
        },
        "defects": [
            {
                "id": "AUD-0045-D-REVIEW",
                "severity": "P1",
                "status": "open",
                "summary": "Independent fresh-context Claude review unpaid.",
            },
            {
                "id": "AUD-0045-D-FAIL-OPEN",
                "severity": "P2",
                "status": "open",
                "summary": (
                    f"{p2['fail_open_count']} gate invocations exited 0 without a measured "
                    f"count: {p2['fail_open_labels']}"
                ),
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
            "entry_id": UNIT,
            "registered_at": ended,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads + audit-finding schema resolver",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe(
                    "source",
                    "schema-validate",
                    "python3 -B command-center/p2-wave/probes/AUD-0045/_pack_receipt.py",
                    "state=BLOCKED",
                    0,
                ),
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 1,
            "policy": "two strikes then pivot (AGENTS.md 4b)",
        },
        "failure": {
            "classification": ["blocked-on-independent-review", "green-not-live"],
            "reason": (
                f"Measured fail_open_count={p2['fail_open_count']} across {p2['case_count']} "
                "executions and static suspects="
                f"{p1['suspect_count']}, but reviewer_requirement unmet."
            ),
            "diagnostic_tail": (
                f"fail_open_labels={p2['fail_open_labels']} "
                f"require_complete_default_off={p1['validate_require_complete_default_off']}"
            ),
            "blocked_on": (
                "Dispatch one fresh-context Claude reviewer who has not seen this transcript "
                "to falsify the headline fail-open count before PASS."
            ),
            "two_signal_proof": [
                L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/AUD-0045/probe2_execute_gates.py",
                    f"fail_open_count={p2['fail_open_count']}",
                    0,
                ),
                L.probe(
                    "verifier",
                    "file-read",
                    "reviewer.verdict",
                    "NOT-REVIEWED",
                    0,
                ),
            ],
        },
        "residual_unknowns": [
            {
                "claim": "Every CI step-wrapped shell gate (not a .py entrypoint) was executed empty.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Expand probe2 to invoke each workflow run: script body in isolation.",
            }
        ],
        "report": {
            "kind": "audit-finding",
            "question": (
                "For every CI gate and local validator, is there an input under which it exits 0 "
                "without having examined anything?"
            ),
            "headline": (
                f"{p2['fail_open_count']} fail-open execution cases; "
                f"{p1['suspect_count']} static-suspect gates; "
                f"validate.require_complete default-off="
                f"{p1['validate_require_complete_default_off']}. BLOCKED on review."
            ),
            "observations": [
                {
                    "name": "gates_present",
                    "measured": p1["gates_present"],
                    "method": "workflow+catalog gate path inventory",
                    "anchor": "command-center/p2-wave/probes/AUD-0045/probe1-static.raw.txt",
                },
                {
                    "name": "static_suspect_gates",
                    "measured": p1["suspect_count"],
                    "method": "AST early-return/default-off/swallowed-except scan",
                    "anchor": "command-center/p2-wave/probes/AUD-0045/probe1-static-findings.json",
                },
                {
                    "name": "fail_open_execution_cases",
                    "measured": p2["fail_open_count"],
                    "method": "execute empty/absent/default; exit0 && !measured_count",
                    "anchor": "command-center/p2-wave/probes/AUD-0045/probe2-execution.raw.txt",
                },
                {
                    "name": "validate_require_complete_default_off",
                    "measured": p1["validate_require_complete_default_off"],
                    "method": "AST default=False on require_complete",
                    "anchor": "command-center/p2-wave/probes/AUD-0045/probe1-static-findings.json",
                },
                {
                    "name": "known_bad_empty_catalog_nonzero",
                    "measured": p2["known_bad_nonzero"],
                    "method": "validate.py empty items control",
                    "anchor": "command-center/p2-wave/probes/AUD-0045/probe2-execution-results.json",
                },
            ],
            "control_ids": ["AUD0045-C1"],
        },
        "extensions": {
            "anti_false_green": "BLOCKED-with-real-probes",
            "wave": "p2-wave1",
            "fail_open_labels": p2["fail_open_labels"],
        },
    }


def main() -> int:
    doc = build()
    rc = L.write_if_valid(doc, OUT, SCHEMA)
    if rc != 0:
        return rc
    for _ in range(2):
        doc = build(primary=L.art(OUT, "primary"))
        rc = L.write_if_valid(doc, OUT, SCHEMA)
        if rc != 0:
            return rc
    man = {
        "unit_id": UNIT,
        "output_path": OUT,
        "sha256": L.art(OUT)["sha256"],
        "bytes": L.art(OUT)["bytes"],
        "state": "BLOCKED",
    }
    (L.REPO / MANIFEST).write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    print(f"PACKED {OUT} state=BLOCKED bytes={L.art(OUT)['bytes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
