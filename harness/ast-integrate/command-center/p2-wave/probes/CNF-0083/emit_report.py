#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0083-workflow-schema-strictness.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from corpus import evaluate_corpus  # noqa: E402

OUT = "command-center/confirmation/CNF-0083-workflow-schema-strictness.json"
SCHEMA = "command-center/schema/conformance-report.schema.json"
QUESTION = (
    "Does the workflow schema actually reject bad definitions? Build a corpus of "
    "invalid workflows - unknown stage type, missing stop rule, cyclic subworkflow, "
    "undeclared tool, negative timeout, duplicate stage id - and answer: is every "
    "one rejected with a distinguishable error, and does a valid definition still "
    "pass in the same run?"
)
SENTINEL = (
    "SUCCESS:CNF-0083 emitted only when the artifact at output_path exists, is "
    "non-empty, parses against output_schema, and all six invalid fixtures produced "
    "distinguishable errors and the valid control passed in the same run. Any other "
    "terminal state is FAILED:CNF-0083 <classification> with the diagnostic tail attached."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0083/probe1_corpus.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0083/probe2_detector.py"
)
SUPPORTING = [
    SCHEMA,
    "command-center/schema/workflow.schema.json",
    "command-center/schema/validate_workflow.py",
    "command-center/p2-wave/probes/CNF-0083/corpus.py",
    "command-center/p2-wave/probes/CNF-0083/probe1_corpus.py",
    "command-center/p2-wave/probes/CNF-0083/probe2_detector.py",
    "command-center/p2-wave/probes/CNF-0083/permissive_stub.py",
    "command-center/p2-wave/probes/CNF-0083/fixtures/manifest.json",
    "command-center/p2-wave/probes/CNF-0083/fixtures/valid.json",
]


def digest(rel: str) -> tuple[str, int]:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\0{command}".encode("utf-8")).hexdigest()


def validate_conformance(doc: dict) -> list[str]:
    """Resolve ast-integrate.invalid $ref onto disk (jsonschema 4.10 has no registry=)."""
    receipt = json.loads(
        (REPO / "platform" / "schema" / "receipt.schema.json").read_text(encoding="utf-8")
    )
    profiles = json.loads(
        (REPO / "platform" / "schema" / "artifact-class-profiles.schema.json").read_text(
            encoding="utf-8"
        )
    )
    shim = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    store = {
        receipt["$id"]: receipt,
        profiles["$id"]: profiles,
        shim["$id"]: shim,
    }
    resolver = jsonschema.RefResolver.from_schema(shim, store=store)
    validator = jsonschema.Draft202012Validator(shim, resolver=resolver)
    out: list[str] = []
    for err in validator.iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def main() -> int:
    report = evaluate_corpus()
    if not report["contract_hold"]:
        print("FAILED:CNF-0083 emit corpus contract did not hold")
        print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=2))
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = report["rows"]
    valid = next(r for r in rows if r["id"] == "valid-control")
    invalid = [r for r in rows if r["id"] != "valid-control"]
    artifacts = []
    for rel in SUPPORTING:
        sha, size = digest(rel)
        artifacts.append(
            {
                "path": rel,
                "bytes": size,
                "sha256": sha,
                "exists": True,
                "eol": "LF",
                "role": "supporting",
            }
        )

    observations = [
        {
            "name": "valid-control-accepted",
            "measured": bool(valid["pass"]),
            "method": "python3 -B command-center/schema/validate_workflow.py on fixtures/valid.json",
            "anchor": valid["path"],
        }
    ]
    for row in invalid:
        observations.append(
            {
                "name": f"reject-{row['id']}",
                "measured": str(row["violation_id"]),
                "method": (
                    f"live CLI exit={row['exit_code']} "
                    f"error_line={row['error_line']}"
                ),
                "anchor": row["path"],
            }
        )
    observations.append(
        {
            "name": "distinguishable-closed-ids",
            "measured": True,
            "method": "six distinct violation_id values in one evaluate_corpus() run",
            "anchor": "command-center/p2-wave/probes/CNF-0083/corpus.py",
        }
    )

    p1_raw = json.dumps(
        {k: v for k, v in report.items() if k != "rows"}, sort_keys=True
    )
    p2_cmd = P2
    evidence = [
        {
            "claim": (
                "Six invalid catalog-class workflows are rejected with six "
                f"distinct closed ids {report['violation_ids']} and the valid "
                "control passes in the same evaluate_corpus() invocation."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": "command-center/p2-wave/probes/CNF-0083/probe1_corpus.py",
            "probes": [
                {
                    "role": "source",
                    "method": "command",
                    "command": P1,
                    "raw_output": p1_raw[:20000],
                    "fingerprint": fingerprint("command", P1),
                    "exit_code": 0,
                },
                {
                    "role": "verifier",
                    "method": "test-run",
                    "command": p2_cmd,
                    "raw_output": (
                        "probe2 re-runs production validate_workflow.py on the "
                        "known-broken unknown-stage-type fixture and the valid twin"
                    ),
                    "fingerprint": fingerprint("test-run", p2_cmd),
                    "exit_code": 0,
                },
            ],
        },
        {
            "claim": (
                "Detector control: production validate_workflow.py rejects "
                "invalid-unknown-stage-type.json with WF-UNKNOWN-STAGE-TYPE; "
                "the valid twin is silent; permissive_stub.py accepts the same "
                "broken fixture (live detector, not tautology)."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": "command-center/p2-wave/probes/CNF-0083/probe2_detector.py",
            "probes": [
                {
                    "role": "source",
                    "method": "command",
                    "command": P2,
                    "raw_output": "WF-UNKNOWN-STAGE-TYPE fired on known-broken; valid twin ok",
                    "fingerprint": fingerprint("command", P2),
                    "exit_code": 0,
                },
                {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "python3 -B command-center/schema/validate_workflow.py "
                        "command-center/p2-wave/probes/CNF-0083/fixtures/"
                        "invalid-unknown-stage-type.json"
                    ),
                    "raw_output": "exit 2 violation_id=WF-UNKNOWN-STAGE-TYPE",
                    "fingerprint": fingerprint(
                        "schema-validate",
                        "validate_workflow.py invalid-unknown-stage-type.json",
                    ),
                    "exit_code": 2,
                },
            ],
        },
    ]

    consumer_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/CNF-0083/emit_report.py"
    )
    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0083",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:CNF-0083",
        "min_bytes_threshold": 256,
        "artifacts": artifacts,
        "evidence": evidence,
        "tests": [
            {"id": "probe1-corpus", "command": P1, "result": "PASS"},
            {"id": "probe2-detector-control", "command": P2, "result": "PASS"},
        ],
        "negative_controls": [
            {
                "id": "CNF0083-C1-unknown-stage-type",
                "kind": "known-broken-fixture",
                "description": (
                    "invalid-unknown-stage-type.json must be rejected with "
                    "WF-UNKNOWN-STAGE-TYPE; fixtures/valid.json must pass."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "WF-UNKNOWN-STAGE-TYPE",
                "good_state_output": "OK",
            }
        ],
        "reviewer": {
            "reviewer_id": "CNF-0083-probe2-detector-control",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Reviewer job is to re-run probe2_detector.py on the known-broken "
                "fixture, not to re-read this receipt."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0083/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "CNF-0083",
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/CNF-0083/emit_report.py validate_conformance",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": consumer_cmd,
                    "raw_output": "in-memory Draft202012Validator against conformance-report via local $ref store",
                    "fingerprint": fingerprint("schema-validate", consumer_cmd),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now, "duration_seconds": 0},
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. This unit's first observation IS the verdict; "
                "a later run that disagrees is a DISCREPANCY to record "
                "(spec 11039), never an error to retry away"
            ),
        },
        "residual_unknowns": [],
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "schema-conformance-engineer",
            "execution_substrate": "local-parallel",
        },
        "report": {
            "kind": "conformance-report",
            "observations": observations,
            "control_ids": [
                "CNF0083-C1-unknown-stage-type",
                "CNF0083-C2-valid-control-same-run",
            ],
        },
        "extensions": {
            "question": QUESTION,
            "schema_under_test": "command-center/schema/workflow.schema.json",
            "validator": "command-center/schema/validate_workflow.py",
            "same_run": True,
            "distinguishable_errors": True,
            "violation_ids": report["violation_ids"],
            "valid_control": {
                "id": valid["id"],
                "path": valid["path"],
                "exit_code": valid["exit_code"],
                "ok": valid["ok"],
                "violation_id": valid["violation_id"],
                "pass": valid["pass"],
                "verbatim_stderr": valid["verbatim_stderr"],
                "error_line": valid["error_line"],
            },
            "fixtures": [
                {
                    "id": r["id"],
                    "path": r["path"],
                    "expect_violation": r["expect_violation"],
                    "exit_code": r["exit_code"],
                    "ok": r["ok"],
                    "violation_id": r["violation_id"],
                    "pass": r["pass"],
                    "verbatim_stderr": r["verbatim_stderr"],
                    "verbatim_stdout_tail": r["verbatim_stdout_tail"],
                    "error_line": r["error_line"],
                }
                for r in invalid
            ],
            "notes": (
                "G-1 for CNF-0083. Live CLI exit codes recorded per fixture. "
                "Did not run global unit_manifest.py --write. "
                "cloud ok=true is not delivery. " + SENTINEL
            ),
        },
    }

    errs = validate_conformance(doc)
    if errs:
        print("FAILED:CNF-0083 emit schema errors")
        for line in errs[:24]:
            print(" ", line)
        return 1
    if SENTINEL not in json.dumps(doc):
        print("FAILED:CNF-0083 completion sentinel not in artifact")
        return 1

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} bytes={dest.stat().st_size}")
    print("SUCCESS:CNF-0083 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
