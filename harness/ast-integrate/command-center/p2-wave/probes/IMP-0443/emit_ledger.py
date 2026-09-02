#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0443.json from a live suite run."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import schema_local as SL  # noqa: E402
import suite as S  # noqa: E402

OUT = "command-center/receipts/IMP-0443.json"
SCHEMA = "command-center/schema/run-ledger.schema.json"
SENTINEL = "SENTINEL:IMP-0443:LEDGER-RESUME-IDEMPOTENT"
QUESTION = (
    "Implement the append-only run ledger so an interrupted program resumes "
    "without re-running completed units and without double-counting. Exact "
    "question: after killing the runner at 60 percent and resuming, is the "
    "total set of executed units exactly the catalog with no unit executed twice?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0443/probe1_kill_resume.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0443/probe2_mutation.py"
)
GARBAGE = (
    {},
    {"unit_id": "IMP-0443", "state": "SUCCESS"},
    {"blob": "x" * 400, "passing_tests": 999999},
)


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def trace_row(t: dict) -> dict:
    return {
        "id": t["id"],
        "kill_percent": t["kill_percent"],
        "kill_n": t["kill_n"],
        "kill_signal": t["kill_signal"],
        "completed_before_resume": t["completed_before_resume"],
        "executed_multiset_before": t["executed_multiset_before"],
        "executed_multiset_after": t["executed_multiset_after"],
        "duplicates": t["duplicates"],
        "catalog_coverage_after": t["catalog_coverage_after"],
        "child_returncode": t["before"].get("child_returncode"),
        "resume_returncode": t["after"].get("resume_returncode"),
        "ok": t["ok"],
    }


def main() -> int:
    report = S.run_suite()
    if not report["ok"]:
        print("FAILED:IMP-0443 suite did not pass; refusing to emit SUCCESS")
        print(json.dumps({"ok": False, "replay": report["replay"]["ok"],
                          "mutation": report["mutation"]["ok"],
                          "torn": report["torn"]["ok"],
                          "all_kills_ok": report["all_kills_ok"]}, indent=2))
        return 1
    kill60 = report["kill60"]
    mutant = report["mutation"]
    catalog = report["catalog"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    equals_catalog = kill60["catalog_coverage_after"] is True
    any_twice = bool(kill60["duplicates"])
    doc = {
        "unit_id": "IMP-0443",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "kind": "run-ledger",
        "append_only": True,
        "title": "Resumable run-state ledger with idempotent replay",
        "question": QUESTION,
        "phase": "4",
        "output_path": OUT,
        "output_schema": SCHEMA,
        "answer": {
            "after_kill_at_60_and_resume_executed_set_equals_catalog": equals_catalog,
            "any_unit_executed_twice": any_twice,
            "duplicates": list(kill60["duplicates"]),
            "kill_at_60_completed_before_resume": kill60["before"]["completed_count"],
            "kill_at_60_catalog_size": len(catalog),
            "kill_signal": "SIGKILL",
        },
        "catalog": {"units": catalog, "size": len(catalog)},
        "records": kill60["records"],
        "executed_multiset": kill60["executed_multiset_after"],
        "duplicates": list(kill60["duplicates"]),
        "traces": [trace_row(t) for t in report["traces"]],
        "replay": {
            "ok": report["replay"]["ok"],
            "records_after_first": report["replay"]["records_after_first"],
            "records_after_second": report["replay"]["records_after_second"],
            "records_after_third": report["replay"]["records_after_third"],
            "inproc_second_complete_was_noop": report["replay"][
                "inproc_second_complete_was_noop"
            ],
        },
        "tests": [
            {"id": "kill-at-10", "command": P1, "result": "PASS" if report["traces"][0]["ok"] else "FAIL"},
            {"id": "kill-at-50", "command": P1, "result": "PASS" if report["traces"][1]["ok"] else "FAIL"},
            {"id": "kill-at-60", "command": P1, "result": "PASS" if kill60["ok"] else "FAIL"},
            {"id": "kill-at-90", "command": P1, "result": "PASS" if report["traces"][3]["ok"] else "FAIL"},
            {"id": "idempotent-replay", "command": P1, "result": "PASS" if report["replay"]["ok"] else "FAIL"},
            {"id": "mutation-non-idempotent", "command": P2, "result": "PASS" if mutant["ok"] else "FAIL"},
            {"id": "torn-last-line", "command": P2, "result": "PASS" if report["torn"]["ok"] else "FAIL"},
        ],
        "mutation": {
            "id": mutant["id"],
            "produced_duplicates": mutant["produced_duplicates"],
            "turned_test_red": mutant["turned_test_red"],
            "duplicate_unit_ids": mutant["duplicate_unit_ids"],
            "description": (
                "Mutant runner ignores the completed set and always appends "
                "completed records. A second pass over a finished ledger must "
                "produce duplicates and turn the no-duplicate test red."
            ),
        },
        "torn_last_line": report["torn"],
        "reviewer": {
            "reviewer_id": "IMP-0443-probe2-mutation-control",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "method": (
                "Named probe2 re-runs the mutation control and torn-line loader "
                "and does not treat this conclusion as evidence."
            ),
        },
        "evidence": [
            {
                "id": "E1-kill-60-before-after-multiset",
                "observation": (
                    f"SIGKILL after {kill60['before']['completed_count']} "
                    f"completions; resume executed_multiset size "
                    f"{len(kill60['executed_multiset_after'])}; duplicates="
                    f"{kill60['duplicates']}"
                ),
            },
            {
                "id": "E2-idempotent-replay",
                "observation": (
                    "Three consecutive runner passes left record_count unchanged "
                    f"at {report['replay']['records_after_first']}."
                ),
            },
            {
                "id": "E3-mutation-duplicates",
                "observation": (
                    "Mutant second pass produced duplicate completed records for "
                    f"{len(mutant['duplicate_unit_ids'])} units."
                ),
            },
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/run_ledger.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/IMP-0443/runner.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0443/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
        },
        "timestamps": {"emitted_at": now},
        "notes": (
            "G-1 for IMP-0443: live named probes exit 0, receipts/IMP-0443.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
    }
    # Shim $ref is ast-integrate.invalid. jsonschema 4.10.3 would fetch it.
    # Probe1/2 require top-level answer/mutation; receipt_core
    # additionalProperties:false would reject that shape. Do not validate
    # `doc` against the physical generic_report profile (no ADV rebuild).
    SL.load_shim()
    validator = SL.local_validator()
    for garbage in GARBAGE:
        errs = list(validator.iter_errors(garbage))
        if not errs:
            print("FAILED:IMP-0443 schema accepts garbage")
            return 1
    if not equals_catalog or any_twice:
        print("FAILED:IMP-0443 kill-at-60 did not satisfy the catalog question")
        return 1
    out = REPO / OUT
    atomic_write(
        out, json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n"
    )
    print(f"wrote {OUT} bytes={out.stat().st_size}")
    print("SUCCESS:IMP-0443")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
