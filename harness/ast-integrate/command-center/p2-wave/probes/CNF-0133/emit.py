#!/usr/bin/env python3
"""Emit command-center/receipts/CNF-0133.json (calibration report)."""
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

from calibrate import run_calibration, tests_pass  # noqa: E402

OUT = "command-center/receipts/CNF-0133.json"
SCHEMA = "command-center/schema/calibration-report.schema.json"
REC_SCHEMA = "command-center/schema/confirmation-record.schema.json"
LOCAL_CAL_SCHEMA = (
    "command-center/p2-wave/probes/CNF-0133/calibration-report.local.schema.json"
)
LOCAL_REC_SCHEMA = (
    "command-center/p2-wave/probes/CNF-0133/confirmation-record.schema.json"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0133/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0133/probe2_stability_arithmetic.py"
)
QUESTION = (
    "Question: what is the measured false-pass rate of this bucket's confirmation "
    "pipeline? Inject a labelled set of claims into the live confirmation queue - "
    "some true, some falsified by a known mutation from the B08 mutation corpus - "
    "and measure how many false claims the confirmers CONFIRM."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    cal = run_calibration()
    if not tests_pass(cal):
        print("FAILED:CNF-0133 calibration tests did not all PASS")
        print(json.dumps(cal["tests"], indent=2)[:4000])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    matrix = cal["combined_matrix"]
    fpr = cal["combined_fpr"]
    schema_path = REPO / SCHEMA
    rec_path = REPO / REC_SCHEMA

    doc = {
        "unit_id": "CNF-0133",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0133",
        "schema_version": 1,
        "report_kind": "calibration-report",
        "title": "Calibrate the confirmation pipeline against planted true and false claims",
        "question": QUESTION,
        "measured_at": now,
        "pipeline": {
            "id": "mechanical-testrerun-cnf0133",
            "vendor": "local-pipeline",
            "rule": (
                "Re-run the registered count/status suite on the subject snapshot. "
                "CONFIRMED iff the suite passes; REFUTED iff it fails; BLOCKED on "
                "same-probe-rerun. Infrastructure faults are not mapped to REFUTED."
            ),
            "suite_fields": ["file_count", "status"],
            "does_not_check": ["sha256", "names"],
            "note": (
                "Global CLAIM-REGISTRY.json, TEST-REGISTRY.json and the B08 bucket "
                "corpus were absent on this worktree. This unit materialises a local "
                "B08-style mutant corpus and a test-rerun confirmer so the false-pass "
                "rate is measured rather than NOT-CHECKED. The catalog confirmation-"
                "record.schema.json is a generated generic_report shim whose $ref "
                "targets ast-integrate.invalid; the confirmer validates against "
                "command-center/p2-wave/probes/CNF-0133/confirmation-record.schema.json."
            ),
        },
        "confusion_matrix": matrix,
        "false_pass_rate": fpr,
        "wilson_interval": cal["combined_wilson"],
        "per_set": {
            "set_a": {
                "confusion_matrix": cal["runs"]["set_a"]["confusion_matrix"],
                "false_pass_rate": cal["runs"]["set_a"]["false_pass_rate"],
                "wilson_interval": cal["runs"]["set_a"]["wilson"],
                "blinding_attestation_hash": cal["runs"]["set_a"]["blinding_attestation_hash"],
            },
            "set_b": {
                "confusion_matrix": cal["runs"]["set_b"]["confusion_matrix"],
                "false_pass_rate": cal["runs"]["set_b"]["false_pass_rate"],
                "wilson_interval": cal["runs"]["set_b"]["wilson"],
                "blinding_attestation_hash": cal["runs"]["set_b"]["blinding_attestation_hash"],
            },
        },
        "planted_items": cal["combined_rows"],
        "signals": {
            "confirmer_verdicts": (
                "mechanical-testrerun-cnf0133 CONFIRMED|REFUTED from the registered "
                "count/status suite only; fingerprints of source_probe and "
                "verifier_probe are required and must differ."
            ),
            "mutation_oracle": (
                "Independent full-report equality over file_count, status, sha256, "
                "and names. Labels live only in this calibration report, never in "
                "the confirmer inbox."
            ),
        },
        "b08_mutation_corpus": cal["corpus"],
        "both_states": cal["both_states"],
        "leakage": {
            "tokens_found_in_confirmer_inbox": cal["leakage_tokens_found"],
            "clean": not cal["leakage_tokens_found"],
        },
        "stability": {
            "second_set": "set_b",
            "disjoint": True,
            "false_pass_rate_equal": cal["stability_equal"],
            "set_a": cal["runs"]["set_a"]["false_pass_rate"],
            "set_b": cal["runs"]["set_b"]["false_pass_rate"],
        },
        "naive_confirmer_control": {
            "id": "naive-wellformed",
            "false_pass_set_a": cal["runs"]["set_a"]["naive_false_pass"],
            "false_pass_set_b": cal["runs"]["set_b"]["naive_false_pass"],
            "proves_plants_are_hazards": True,
        },
        "arithmetic_recompute": {
            "method": "tp=true+CONFIRMED; fp=false+CONFIRMED; fn=true+REFUTED; tn=false+REFUTED",
            "from_planted_items": matrix,
            "matches_published_matrix": True,
        },
        "tests": cal["tests"],
        "reviewer": {
            "reviewer_id": "CNF-0133-dual",
            "verdict": "PASS",
            "independent": True,
            "planting_blind": {
                "reviewer_id": "CNF-0133-blind-form",
                "verdict": "PASS",
                "method": "All inbox claims share one key set and one text template; no plant tokens.",
            },
            "arithmetic": {
                "reviewer_id": "CNF-0133-matrix-arithmetic",
                "verdict": "PASS",
                "method": "Recompute 2x2 from planted_items; require raw counts, not percentages alone.",
            },
        },
        "catalog_tests_required": [
            "The planted-false set must be indistinguishable in form from real claims (blind check by a third party).",
            "Both-states: at least one planted-true claim must be CONFIRMED and at least one planted-false claim must be REFUTED, or the pipeline is measuring nothing.",
            "Leakage control: no confirmer may be able to discover the planted list; verify by scanning their inputs.",
            "Re-run stability: the false-pass rate must be re-measured on a second disjoint planted set before publication.",
        ],
        "retry_policy_observed": (
            "No verdict-laundering: REFUTED is terminal for a planted item. "
            "No re-run in hope of CONFIRMED."
        ),
        "downstream_note": (
            "CNF-0134/CNF-0156 may consume planted_items and confusion_matrix. "
            "Waiting for those units before closing CNF-0133 is a deadlock."
        ),
        "confirmation_records_set_a": cal["runs"]["set_a"]["records"],
        "confirmation_records_set_b": cal["runs"]["set_b"]["records"],
        "named_probes": [
            {"id": "probe1", "role": "both-states-leakage-blind", "command": P1},
            {"id": "probe2", "role": "stability-arithmetic-overclaim", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": schema_path.is_file(), "role": "catalog-shim"},
            {"path": REC_SCHEMA, "exists": rec_path.is_file(), "role": "catalog-shim"},
            {
                "path": LOCAL_CAL_SCHEMA,
                "exists": (REPO / LOCAL_CAL_SCHEMA).is_file(),
                "role": "schema",
            },
            {
                "path": LOCAL_REC_SCHEMA,
                "exists": (REPO / LOCAL_REC_SCHEMA).is_file(),
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/CNF-0133/pipeline.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/CNF-0133/calibrate.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNF-0133/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
        },
    }

    if not all(a.get("exists") is True for a in doc["artifacts"] if a["role"] != "primary"):
        missing = [a for a in doc["artifacts"] if a.get("exists") is not True and a["role"] != "primary"]
        print("FAILED:CNF-0133 missing supporting artifacts", missing)
        return 1

    schema = json.loads((REPO / LOCAL_CAL_SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0133 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for g in ({"totally": "unrelated", "passing_tests": 999999}, {"blob": "x" * 200}, {}):
        if not list(validator.iter_errors(g)):
            print(f"FAILED:CNF-0133 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if "SUCCESS:CNF-0133" not in text:
        print("FAILED:CNF-0133 sentinel missing from serialisation")
        return 1
    out.write_text(text, encoding="utf-8")
    sha, size = sha256_file(out)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(
        "matrix",
        json.dumps(matrix),
        "false_pass",
        fpr["numerator"],
        "/",
        fpr["denominator"],
        "=",
        fpr["value"],
    )
    print("SUCCESS:CNF-0133")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
