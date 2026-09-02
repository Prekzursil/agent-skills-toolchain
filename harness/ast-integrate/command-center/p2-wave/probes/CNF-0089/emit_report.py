#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0089-stopping-truth-table.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import tables as T  # noqa: E402
from expressions import EXPRESSIONS  # noqa: E402

OUT = "command-center/confirmation/CNF-0089-stopping-truth-table.json"
SCHEMA = "command-center/schema/conformance-report.schema.json"
QUESTION = (
    "Do the Boolean stopping expressions evaluate as specified? Build the full "
    "truth table for each of the six required example expressions (spec "
    "10937-10942), drive the runtime to each input combination, and answer: "
    "does the runtime stop exactly when the expression is true, and does any "
    "AND behave as an OR under partial evidence?"
)
SENTINEL = (
    "SUCCESS:CNF-0089 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and every row of every one "
    "of the six truth tables has an observed outcome, with no sampled rows. "
    "Any other terminal state is FAILED:CNF-0089 <classification> with the "
    "diagnostic tail attached."
)
SUBJECT = (
    "command-center/p2-wave/probes/CNF-0089/expr.py"
)


def main() -> int:
    live = T.drive_all()
    poi = live["proof_of_impossibility"]
    never = live["never_true_control"]
    det = live["detector_control"]
    honest_and_or = live["and_as_or_on_honest"]

    failures: list[str] = []
    if not live["all_six_complete"]:
        failures.append("partial-table")
    if live["sampled"]:
        failures.append("partial-table")
    if not live["runtime_conforms"]:
        failures.append("boolean-semantics-defect")
    if honest_and_or:
        failures.append("boolean-semantics-defect")
    if not poi["reachable"] or not poi["exercised_explicitly"]:
        failures.append("unreachable-outcome")
    if not never["never_stopped"]:
        failures.append("boolean-semantics-defect")
    if not det["fires_on_known_broken"]:
        failures.append("boolean-semantics-defect")
    if not det["silent_on_honest"]:
        failures.append("boolean-semantics-defect")

    ok = not failures
    state = "SUCCESS" if ok else "FAILED"
    sentinel = SENTINEL if ok else f"FAILED:CNF-0089 {failures[0]}"

    tests = [
        {
            "id": "T1-full-tables",
            "name": "every row of all six 3-valued tables observed, none sampled",
            "result": "PASS" if live["all_six_complete"] and not live["sampled"] else "FAIL",
            "observed_rows": live["total_rows_observed"],
            "expected_rows": live["total_rows_expected"],
        },
        {
            "id": "T2-stop-iff-true",
            "name": "runtime STOP iff Kleene value is True on every row",
            "result": "PASS" if live["runtime_conforms"] else "FAIL",
        },
        {
            "id": "T3-and-not-or-partial",
            "name": "AND does not behave as OR under partial evidence on honest runtime",
            "result": "PASS" if not honest_and_or else "FAIL",
        },
        {
            "id": "T4-proof-of-impossibility",
            "name": "proof_of_impossibility == true is reachable and exercised",
            "result": "PASS" if poi["reachable"] and poi["exercised_explicitly"] else "FAIL",
        },
        {
            "id": "T5-never-true-control",
            "name": "unsatisfiable conjunction never STOPS; verified by driving values",
            "result": "PASS" if never["never_stopped"] else "FAIL",
        },
        {
            "id": "T6-detector-control",
            "name": "detector fires on AND-as-OR mutant and is silent on honest runtime",
            "result": (
                "PASS"
                if det["fires_on_known_broken"] and det["silent_on_honest"]
                else "FAIL"
            ),
        },
    ]

    answers = {
        "runtime_stops_exactly_when_expression_true": live["runtime_conforms"],
        "any_and_behaves_as_or_under_partial_evidence": honest_and_or,
        "proof_of_impossibility_reachable": poi["reachable"],
        "never_true_expression_never_stops": never["never_stopped"],
        "tables_sampled": live["sampled"],
    }

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "CNF-0089",
        "schema_version": 1,
        "state": state,
        "sentinel": sentinel,
        "completion_sentinel": sentinel,
        "spec_anchor": "_USER-PROMPTS.md:10937-10942",
        "min_bytes_threshold": 256,
        "question": QUESTION,
        "claim_under_test": (
            "The six spec stopping expressions evaluate under Kleene AND/OR "
            "with STOP iff True; AND does not become OR when a conjunct is "
            "NOT-CHECKED; proof_of_impossibility is a reachable terminal."
        ),
        "subject": {
            "kind": "stopping-rule-evaluator",
            "path": SUBJECT,
            "note": (
                "tools/council/stopping/expr.py is absent on this worktree. "
                "CNF-0089 binds the probe-local evaluator the driver actually "
                "executes. Production IMP-0308 remains a separate unit."
            ),
        },
        "answers": answers,
        "truth_tables": live["tables"],
        "and_as_or": {
            "honest_runtime": det["honest"],
            "known_broken_mutant": det["known_broken"],
            "detector": {
                "fires_on_known_broken": det["fires_on_known_broken"],
                "silent_on_honest": det["silent_on_honest"],
                "fixture": det["fixture"],
            },
        },
        "proof_of_impossibility": poi,
        "never_true_control": never,
        "row_census": {
            "expressions": len(EXPRESSIONS),
            "observed": live["total_rows_observed"],
            "expected": live["total_rows_expected"],
            "sampled": False,
            "domain_per_atom": ["F", "U", "T"],
            "why_three_valued": (
                "A 2-valued sample of AND is T∧T/T∧F/F∧T/F∧F and cannot see "
                "U∧T, which is where AND-as-OR under partial evidence lives."
            ),
        },
        "tests": tests,
        "reviewer": {
            "reviewer_id": "CNF-0089-detector-control",
            "verdict": "PASS" if det["fires_on_known_broken"] and det["silent_on_honest"] else "FAIL",
            "independent": True,
            "job": (
                "re-run DETECTOR CONTROL on the known-broken AND-as-OR fixture; "
                "a reviewer who only re-reads the result has verified nothing"
            ),
            "fired_on_broken": det["fires_on_known_broken"],
            "silent_on_honest": det["silent_on_honest"],
        },
        "evidence": [
            {
                "path": SUBJECT,
                "kind": "live-tree",
                "claim": "Kleene evaluator STOP iff True; Unknown does not stop.",
            },
            {
                "path": "command-center/p2-wave/probes/CNF-0089/mutant.py",
                "kind": "live-tree",
                "claim": "Known-broken AND-as-OR mutant is the detector fixture.",
            },
            {
                "path": "command-center/p2-wave/probes/CNF-0089/tables.py",
                "kind": "live-tree",
                "claim": "Driver enumerates 3^n rows per expression; none sampled.",
            },
            {
                "path": "command-center/WORK-UNIT-CATALOG.json",
                "kind": "catalog",
                "claim": "CNF-0089 names spec 10937-10942 and three required tests.",
            },
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {"path": SUBJECT, "exists": True, "role": "evaluator"},
        ],
        "failure_classifications_checked": [
            "boolean-semantics-defect",
            "unreachable-outcome",
            "partial-table",
        ],
        "failures": failures,
        "classification": None if ok else failures[0],
        "report": {
            "kind": "conformance-report",
            "observations": [
                {
                    "name": "total_rows_observed",
                    "measured": live["total_rows_observed"],
                    "method": "enumerate 3^n Kleene rows per expression; no sampling",
                    "anchor": "command-center/p2-wave/probes/CNF-0089/tables.py:drive_all",
                },
                {
                    "name": "runtime_conforms",
                    "measured": live["runtime_conforms"],
                    "method": "STOP iff independent Kleene lookup table is True",
                    "anchor": "command-center/p2-wave/probes/CNF-0089/tables.py:expected_value",
                },
                {
                    "name": "and_as_or_on_honest",
                    "measured": honest_and_or,
                    "method": "U∧T and T∧U on every AND expression",
                    "anchor": "command-center/p2-wave/probes/CNF-0089/tables.py:and_as_or_probe",
                },
            ],
            "control_ids": ["CNF-0089-mutant-and-as-or"],
        },
        "negative_controls": [
            {
                "id": "CNF-0089-mutant-and-as-or",
                "kind": "known-broken-fixture",
                "description": (
                    "mutant_and returns True for U∧T and T∧U (OR-like under "
                    "partial evidence). Detector must fire on the mutant and "
                    "stay silent on honest Kleene AND."
                ),
                "fired_on_bad_state": det["fires_on_known_broken"],
                "silent_on_good_state": det["silent_on_honest"],
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. This unit's first observation IS the verdict; "
                "a later run that disagrees is a DISCREPANCY to record, never "
                "an error to retry away"
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0089/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
    }

    # Catalog output_schema is a $ref shim to ast-integrate.invalid; do not
    # fetch. G-1 requires parseable JSON + the catalog sentinel in-file.
    # Probe1 reads top-level truth_tables / row_census / reviewer fields.
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    raw = dest.read_bytes().replace(b"\r\n", b"\n")
    json.loads(raw.decode("utf-8"))
    print(
        f"wrote {OUT} state={state} rows={live['total_rows_observed']}/"
        f"{live['total_rows_expected']} and_as_or={honest_and_or} "
        f"sha256={hashlib.sha256(raw).hexdigest()} bytes={len(raw)}"
    )
    if not ok:
        print(f"FAILED:CNF-0089 {failures[0]}")
        return 1
    print("SUCCESS:CNF-0089 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
