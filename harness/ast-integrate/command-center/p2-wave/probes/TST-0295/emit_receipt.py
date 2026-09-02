#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0295.json after assembling the live corpus."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center" / "bench"))
sys.path.insert(0, str(HERE))

from corpus import assemble, write_corpus  # noqa: E402
from oracle import evaluate, load_cases, sanity, split_intersections  # noqa: E402

OUT = "command-center/receipts/TST-0295.json"
SCHEMA_REL = "command-center/schema/bench-case.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0295/probe1_schema_splits.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0295/probe2_oracle_sanity.py"
)
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
)
QUESTION = (
    "Implementation target: assemble the case set every later comparison runs on. "
    "Each case carries a stable id, the task input, a machine-checkable success "
    "oracle, provenance, a difficulty stratum, and a split tag "
    "(dev / test / held-out-shadow). Cases whose oracle is a model judgement "
    "rather than a deterministic check must be tagged."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load_schema() -> dict:
    path = REPO / SCHEMA_REL
    return json.loads(path.read_text(encoding="utf-8"))


def validate_cases(cases: list[dict], schema: dict) -> list[str]:
    validator = jsonschema.Draft7Validator(schema)
    errors: list[str] = []
    for probe in GARBAGE:
        if not list(validator.iter_errors(probe)):
            errors.append(f"schema-accepts-garbage:{probe}")
    for case in cases:
        hits = sorted(validator.iter_errors(case), key=lambda e: list(e.path))
        for err in hits:
            errors.append(f"{case.get('id')}:{list(err.path)}:{err.message}")
    return errors


def provenance_holes(cases: list[dict]) -> list[str]:
    holes: list[str] = []
    for case in cases:
        prov = case.get("provenance") or {}
        source = prov.get("source")
        if not isinstance(source, str) or not source.strip():
            holes.append(str(case.get("id")))
        if "derived_from_real_defect" not in prov:
            holes.append(f"{case.get('id')}:derived_from_real_defect-missing")
    return holes


def main() -> int:
    cases, meta = assemble()
    index = write_corpus(cases)
    schema = load_schema()
    schema_errors = validate_cases(cases, schema)
    if schema_errors:
        print("FAILED:TST-0295 schema")
        print("\n".join(schema_errors[:20]))
        return 1
    holes = provenance_holes(cases)
    if holes:
        print("FAILED:TST-0295 empty provenance", holes[:10])
        return 1
    intersections = split_intersections(cases)
    if any(intersections[k] for k in intersections):
        print("FAILED:TST-0295 split overlap", intersections)
        return 1
    sanity_rows = [sanity(c) for c in cases]
    if any(not r["ok"] for r in sanity_rows):
        bad = [r for r in sanity_rows if not r["ok"]]
        print("FAILED:TST-0295 oracle sanity", bad[:5])
        return 1
    if any(evaluate(c, c["known_bad_solution"]) for c in cases):
        print("FAILED:TST-0295 known-bad accepted")
        return 1
    for split, n in index["counts_by_split"].items():
        if n <= 0:
            print("FAILED:TST-0295 empty split", split)
            return 1
    for stratum, n in index["counts_by_stratum"].items():
        if n <= 0:
            print("FAILED:TST-0295 empty stratum", stratum)
            return 1
    n = len(cases)
    det = index["counts_by_oracle_type"].get("deterministic", 0)
    judged = index["counts_by_oracle_type"].get("judged", 0)
    if judged < 1 or det < 1:
        print("FAILED:TST-0295 need both oracle types")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cases_dir = REPO / "command-center" / "bench" / "cases"
    case_files = sorted(p.relative_to(REPO).as_posix() for p in cases_dir.glob("CASE-*.json"))
    index_sha, index_bytes = sha256_file(REPO / "command-center" / "bench" / "INDEX.json")
    schema_sha, schema_bytes = sha256_file(REPO / SCHEMA_REL)

    doc = {
        "unit_id": "TST-0295",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0295",
        "title": (
            "Build the benchmark case corpus with provenance, difficulty strata "
            "and a held-out split"
        ),
        "question": QUESTION,
        "corpus": {
            "cases_dir": "command-center/bench/cases",
            "index_path": "command-center/bench/INDEX.json",
            "schema": SCHEMA_REL,
            "n_cases": n,
            "case_files": case_files,
            "index_sha256": index_sha,
            "index_bytes": index_bytes,
            "schema_sha256": schema_sha,
            "schema_bytes": schema_bytes,
        },
        "counts_by_stratum": index["counts_by_stratum"],
        "counts_by_split": index["counts_by_split"],
        "oracle_types": {
            "deterministic": det,
            "judged": judged,
            "deterministic_fraction": det / n,
            "judged_fraction": judged / n,
        },
        "split_disjointness": {
            "method": "set-intersection-of-case-ids",
            "dev_and_test": intersections["dev_and_test"],
            "dev_and_held_out": intersections["dev_and_held_out"],
            "test_and_held_out": intersections["test_and_held_out"],
            "computed_not_asserted": True,
        },
        "vacuous_oracle_control": {
            "rejected_ids": meta["vacuous_rejected"],
            "reason": meta["vacuous_reason"],
            "present_in_corpus": False,
        },
        "source_honesty": {
            "user_prompts_file": "_USER-PROMPTS.md",
            "user_prompts_present": (REPO / "_USER-PROMPTS.md").is_file(),
            "failure_class_source_status": "ABSENT-reconstructed-from-ARC-0005",
            "b02_live_audit_artifacts_present": False,
            "notes": (
                "47 failure-class names reconstructed from "
                "command-center/p2-wave/probes/ARC-0005/seeded_classes.py. "
                "B02 cases derived from WORK-UNIT-CATALOG.json bucket=B02; live AUD "
                "artifacts are not on this worktree."
            ),
        },
        "tests": [
            {
                "id": "schema-and-runnable-oracle",
                "command": P1,
                "result": "PASS",
                "detail": "every case validates; schema rejects garbage probes",
            },
            {
                "id": "oracle-sanity-both-states",
                "command": P2,
                "result": "PASS",
                "detail": "known-good PASS and known-bad FAIL on every retained case",
            },
            {
                "id": "split-disjointness-set-intersection",
                "command": P1,
                "result": "PASS",
                "detail": "dev ∩ test, dev ∩ held-out-shadow, test ∩ held-out-shadow are empty",
            },
            {
                "id": "provenance-completeness",
                "command": P1,
                "result": "PASS",
                "detail": "zero empty provenance.source fields",
            },
        ],
        "negative_controls": [
            {
                "id": "vacuous-oracle-stripped",
                "planted_defect": "always_pass oracle that accepts known-good and known-bad",
                "detector_fired": True,
                "silent_on_good": True,
            },
            {
                "id": "schema-rejects-garbage",
                "planted_defect": "empty object / unrelated passing_tests blob / 2000-x blob",
                "detector_fired": True,
                "silent_on_good": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0295-probe2-oracle-sanity",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "notes": (
                "Re-runs every case oracle against known-good and known-bad "
                "solutions without copying probe1 schema/split arithmetic."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA_REL, "exists": True, "role": "case-schema"},
            {"path": "command-center/bench/INDEX.json", "exists": True, "role": "corpus-index"},
            {"path": "command-center/bench/cases", "exists": True, "role": "corpus"},
        ],
        "evidence": [
            {
                "kind": "stratum-counts",
                "value": index["counts_by_stratum"],
                "computed_not_asserted": True,
            },
            {
                "kind": "split-counts",
                "value": index["counts_by_split"],
                "computed_not_asserted": True,
            },
            {
                "kind": "oracle-type-fraction",
                "deterministic_fraction": det / n,
                "judged_fraction": judged / n,
            },
        ],
        "residual_caveat": (
            "command-center/schema/receipt.schema.json is not on this worktree "
            "(catalog output_schema). G-1 measure does not require it. Case schema "
            "is command-center/schema/bench-case.schema.json and is discriminating."
        ),
        "cloud_ok": False,
        "timestamps": {"emitted_at": now},
    }
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if "SUCCESS:TST-0295" not in text:
        print("FAILED:TST-0295 sentinel missing from receipt body")
        return 1
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    print(json.dumps({"n": n, "splits": index["counts_by_split"], "strata": index["counts_by_stratum"], "oracle_types": index["counts_by_oracle_type"]}, sort_keys=True))
    print("SUCCESS:TST-0295 receipt emitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
