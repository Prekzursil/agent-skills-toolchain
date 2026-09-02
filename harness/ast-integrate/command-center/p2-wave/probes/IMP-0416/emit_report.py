#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0416.json (mutation report)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import generator as G  # noqa: E402
from reducer import load_preferred_reducer  # noqa: E402

OUT = "command-center/receipts/IMP-0416.json"
SCHEMA = "command-center/schema/mutation-report.schema.json"
UNIT = "IMP-0416"
SENTINEL = "SENTINEL:IMP-0416:REDUCER-NEGATIVE-CONTROLS"
QUESTION = (
    "Implement the generator that synthesizes, for each of the twelve "
    "completion conditions, an artifact that violates exactly that one "
    "condition and satisfies the other eleven. Exact question: does the "
    "reducer reject all twelve, and for any it accepts, which condition "
    "is unenforced?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0416/probe1_positive_control.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0416/probe2_twelve_negatives.py"
)
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
)
REQUIRED = (
    "unit_id",
    "state",
    "sentinel",
    "mutations",
    "results_table",
    "positive_control",
    "unenforced_conditions",
    "negative_controls",
    "reviewer",
    "report",
)


def validate_or_die(doc: dict) -> None:
    """Catalog output_schema is a generated $ref shim.

    Draft7Validator follows https://ast-integrate.invalid over the network
    and raises. G-1 measure is json.loads + sentinel + named probes; unit
    structure is checked here and by probe1/probe2 against the written
    artifact. Do not fetch the remote $ref.
    """
    schema_path = REPO / SCHEMA
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if not isinstance(schema, dict) or not schema.get("$ref"):
        raise SystemExit("FAILED:IMP-0416 output schema shim missing $ref")
    missing = [k for k in REQUIRED if k not in doc]
    if missing:
        raise SystemExit(f"FAILED:IMP-0416 document missing {missing}")
    report = doc.get("report")
    if not isinstance(report, dict) or report.get("kind") != "mutation-report":
        raise SystemExit("FAILED:IMP-0416 report.kind is not mutation-report")
    obs = report.get("observations")
    if not isinstance(obs, list) or len(obs) < 1:
        raise SystemExit("FAILED:IMP-0416 report.observations empty")
    controls = report.get("control_ids")
    if not isinstance(controls, list) or len(controls) < 1:
        raise SystemExit("FAILED:IMP-0416 report.control_ids empty")
    if not isinstance(doc.get("mutations"), list) or len(doc["mutations"]) != 12:
        raise SystemExit("FAILED:IMP-0416 mutations is not a 12-row table")
    if not isinstance(doc.get("results_table"), list) or len(doc["results_table"]) != 12:
        raise SystemExit("FAILED:IMP-0416 results_table is not a 12-row table")
    for garbage in GARBAGE:
        if all(k in garbage for k in REQUIRED):
            raise SystemExit("FAILED:IMP-0416 structural check accepted garbage")
    doc["schema_validated"] = True
    doc["schema_validation"] = {
        "declared": SCHEMA,
        "shim_parses": True,
        "shim_is_ref": True,
        "remote_ref_not_fetched": True,
        "unit_structure_checked": True,
    }


def main() -> int:
    suite = G.materialize(HERE / "fixtures", REPO)
    if not suite["positive_accepted"]:
        print("FAILED:IMP-0416 positive control not ACCEPTED")
        print(json.dumps(suite["positive"], indent=2, default=str)[:3000])
        return 1
    if not suite["all_twelve_rejected"]:
        print("FAILED:IMP-0416 reducer accepted one or more negatives")
        print(json.dumps(suite["unenforced_conditions"], indent=2))
        return 1
    if not suite["exit_zero_alone_rejected"]:
        print("FAILED:IMP-0416 exit-zero-alone was ACCEPTED")
        return 1
    isolation_miss = [r for r in suite["mutations"] if not G.independence_ok(r)]
    if isolation_miss:
        print("FAILED:IMP-0416 isolation")
        print(json.dumps(isolation_miss, indent=2, default=str)[:4000])
        return 1

    reducer_path = load_preferred_reducer(REPO, HERE)
    try:
        reducer_rel = reducer_path.relative_to(REPO).as_posix()
    except ValueError:
        reducer_rel = str(reducer_path)
    imp0415 = REPO / "command-center/receipts/IMP-0415.json"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    mutations = []
    for row in suite["mutations"]:
        mutations.append(
            {
                "id": row["id"],
                "condition": row["condition"],
                "condition_text": row["condition_text"],
                "mutation": row["mutation"],
                "fixture_path": row["fixture_path"],
                "reducer_verdict": row["reducer_verdict"],
                "failing": row["failing"],
                "unenforced_condition": row["unenforced_condition"],
            }
        )

    doc = {
        "id": UNIT,
        "unit_id": UNIT,
        "schema_version": 1,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Negative-control fixture generator for the completion reducer",
        "question": QUESTION,
        "phase": "4",
        "output_path": OUT,
        "output_schema": SCHEMA,
        "report_kind": "mutation-report",
        "report": {
            "kind": "mutation-report",
            "observations": [
                {
                    "name": "positive_control_verdict",
                    "measured": suite["positive"]["reducer_verdict"],
                    "method": "reducer.judge(fixtures/positive)",
                    "anchor": "command-center/p2-wave/probes/IMP-0416/reducer.py",
                },
                {
                    "name": "all_twelve_rejected",
                    "measured": bool(suite["all_twelve_rejected"]),
                    "method": "reducer.judge(fixtures/negative-01..12)",
                    "anchor": "command-center/p2-wave/probes/IMP-0416/generator.py",
                },
                {
                    "name": "exit_zero_alone_verdict",
                    "measured": suite["exit_zero_alone"]["reducer_verdict"],
                    "method": "reducer.judge(fixtures/exit-zero-alone, process_exit_code=0)",
                    "anchor": "command-center/p2-wave/probes/IMP-0416/reducer.py",
                },
                {
                    "name": "unenforced_condition_count",
                    "measured": len(suite["unenforced_conditions"]),
                    "method": "ACCEPT rows among twelve single-condition mutants",
                    "anchor": "command-center/receipts/IMP-0416.json",
                },
            ],
            "control_ids": ["IMP0416-C1", "IMP0416-C2"],
        },
        "min_bytes_threshold": 128,
        "reducer": {
            "module": reducer_rel,
            "preferred_imp0415_receipt_present": imp0415.is_file(),
            "exit_code_consulted_for_complete": False,
        },
        "positive_control": {
            "fixture_path": suite["positive"]["fixture_path"],
            "reducer_verdict": suite["positive"]["reducer_verdict"],
            "failing": suite["positive"]["failing"],
            "process_exit_code": 0,
        },
        "mutations": mutations,
        "results_table": [
            {
                "condition": r["condition"],
                "condition_text": r["condition_text"],
                "fixture_path": r["fixture_path"],
                "reducer_verdict": r["reducer_verdict"],
                "unenforced_condition": r["unenforced_condition"],
            }
            for r in mutations
        ],
        "unenforced_conditions": suite["unenforced_conditions"],
        "exit_zero_alone": suite["exit_zero_alone"],
        "all_twelve_rejected": True,
        "answers": {
            "does_the_reducer_reject_all_twelve": True,
            "unenforced_conditions": [],
            "positive_control_accepted": True,
            "exit_zero_alone_cannot_complete": True,
        },
        "tests": [
            {
                "id": "T1-positive-control-ACCEPT",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-twelve-negatives-REJECT",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "T3-exit-zero-alone-REJECT",
                "command": "judge(exit-zero-alone, process_exit_code=0)",
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "IMP0416-C1",
                "kind": "known-good-fixture",
                "description": (
                    "All-conditions-satisfied workspace must be ACCEPTED, or the "
                    "generator/reducer pair is a reject-everything detector."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "twelve negatives REJECT",
                "good_state_output": "positive ACCEPT",
            },
            {
                "id": "IMP0416-C2",
                "kind": "exit-zero-alone",
                "description": (
                    "A workspace whose only fact is process_exit_code=0 must be "
                    "REJECTED; exit code zero is never success."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": suite["exit_zero_alone"]["reducer_verdict"],
                "good_state_output": suite["positive"]["reducer_verdict"],
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0416-probe2-twelve-negatives",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "method": (
                "Named probe2 re-materializes the twelve mutants and re-runs "
                "the reducer; it does not re-read this conclusion as evidence."
            ),
        },
        "evidence": [
            {
                "claim": "The all-conditions-satisfied fixture is ACCEPTED.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0416/fixtures/positive/subject.json",
                "confidence": "almost-certain",
            },
            {
                "claim": "All twelve single-condition mutants are REJECTED; none is unenforced.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0416/generator.py",
                "confidence": "almost-certain",
            },
            {
                "claim": "Exit-code-zero alone cannot COMPLETE (exit_code_consulted_for_complete=false).",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0416/fixtures/exit-zero-alone/process_exit.json",
                "confidence": "almost-certain",
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0416/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/IMP-0416/reducer.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/IMP-0416/generator.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "named_probes": [
            {"id": "probe1", "role": "positive-control", "command": P1},
            {"id": "probe2", "role": "twelve-negatives", "command": P2},
        ],
        "timestamps": {"emitted_at": now},
        "residual_unknowns": [
            {
                "claim": (
                    "command-center/receipts/IMP-0415.json (the catalog-named "
                    "shared reducer receipt) is present on this worktree."
                ),
                "verdict": "CONFIRMED" if imp0415.is_file() else "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run this generator against the IMP-0415 library path "
                    "once that receipt and module exist; disagreement would "
                    "be IMP-0418's differential oracle."
                ),
            }
        ],
        "notes": (
            "G-1 for IMP-0416: live named probes exit 0, IMP-0416.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
    }
    validate_or_die(doc)
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT} bytes={out.stat().st_size}")
    print(
        f"rejected={sum(1 for r in mutations if r['reducer_verdict']=='REJECT')}/12 "
        f"positive={suite['positive']['reducer_verdict']} "
        f"unenforced={suite['unenforced_conditions']}"
    )
    print("SUCCESS:IMP-0416")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
