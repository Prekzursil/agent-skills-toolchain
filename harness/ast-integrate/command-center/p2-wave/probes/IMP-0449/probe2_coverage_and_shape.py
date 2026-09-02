#!/usr/bin/env python3
"""Named probe 2: coverage table + closed result shape (different field than probe 1).

Probe 1 reads classifier exhaustiveness. This probe re-harvests live strings,
re-classifies them, and proves the schema rejects open-ended prose documents.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import corpus  # noqa: E402
import failure_taxonomy as ft  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0449.json"
SCHEMA = REPO / "command-center/schema/failure-taxonomy.schema.json"
SENTINEL = "SENTINEL:IMP-0449:TAXONOMY-CLOSED"


def main() -> int:
    failures: list[str] = []
    if not ART.is_file() or ART.stat().st_size < 512:
        print("FAILED:IMP-0449-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:IMP-0449-probe2 sentinel-absent")
        return 1
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:IMP-0449-probe2 self-declared:{doc.get('state')}")
        return 1

    # Catalog output_schema is a generated $ref shim. jsonschema 4.10.3 on
    # this worktree would fetch https://ast-integrate.invalid/. Closed shape
    # is the local receipt contract plus TERMINAL_RESULT_SCHEMA.
    if not SCHEMA.is_file() or SCHEMA.stat().st_size <= 0:
        print("FAILED:IMP-0449-probe2 catalog schema path missing")
        return 1
    receipt_schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": [
            "unit_id",
            "state",
            "sentinel",
            "coverage_table",
            "taxonomy",
            "taxonomy_closed",
        ],
        "properties": {
            "unit_id": {"const": "IMP-0449"},
            "state": {"const": "SUCCESS"},
            "sentinel": {
                "type": "string",
                "pattern": "SENTINEL:IMP-0449:TAXONOMY-CLOSED",
            },
            "coverage_table": {"type": "array", "minItems": 8},
            "taxonomy_closed": {"const": True},
            "taxonomy": {
                "type": "object",
                "required": ["classes", "unclassified_sink", "count"],
                "properties": {
                    "count": {"const": 8},
                    "unclassified_sink": {"const": ft.UNCLASSIFIED},
                },
            },
        },
    }
    validator = jsonschema.Draft7Validator(receipt_schema)
    schema_errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if schema_errs:
        print("FAILED:IMP-0449-probe2 schema")
        for err in schema_errs[:12]:
            print(" ", list(err.path), err.message)
        return 1

    live = corpus.harvest_coverage(REPO)
    declared = {row["class"]: row for row in doc.get("coverage_table") or []}
    for row in live:
        cls = row["class"]
        got = ft.classify(row["observed_error_string"])
        if got != cls:
            failures.append(
                f"live {cls} classified as {got} snippet={row['observed_error_string'][:120]!r}"
            )
        if row["corpus_kind"] != "REAL":
            failures.append(f"{cls} not REAL: {row.get('speculative_reason')}")
        rec = declared.get(cls)
        if rec is None:
            failures.append(f"artifact missing coverage row {cls}")
            continue
        if rec.get("classified_as") != cls:
            failures.append(f"artifact row {cls} classified_as={rec.get('classified_as')}")
        if rec.get("source") != row["source"] or rec.get("line") != row["line"]:
            failures.append(f"artifact row {cls} source/line drifted from live harvest")

    want = set(ft.TAXONOMY_CLASSES)
    have = {row["class"] for row in live}
    if want != have:
        failures.append(f"coverage set {sorted(have)} != {list(want)}")

    prose_docs = (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {
            "unit_id": "IMP-0449",
            "state": "SUCCESS",
            "message": "the run went well, please see the narrative",
        },
        "just a prose string",
    )
    for i, garbage in enumerate(prose_docs):
        errs = list(validator.iter_errors(garbage))
        if not errs:
            failures.append(f"schema accepted garbage[{i}]")

    result_validator = jsonschema.Draft7Validator(ft.TERMINAL_RESULT_SCHEMA)
    bad_results = (
        {"status": "SUCCESS", "id": "x", "marker": "SUCCESS:x"},  # missing class:null
        {"status": "FAILED", "id": "x", "marker": "FAILED:x no"},  # missing reason+class
        {"message": "open ended prose", "ok": True},
        {"status": "SUCCESS", "id": "x", "marker": "SUCCESS:x", "class": None, "body": "prose"},
    )
    for i, bad in enumerate(bad_results):
        if not list(result_validator.iter_errors(bad)):
            failures.append(f"result schema accepted open shape[{i}] {bad}")

    good_fail = ft.format_failure("IMP-0449", "died with os error 206").to_json()
    if list(result_validator.iter_errors(good_fail)):
        failures.append("valid FAILED result rejected")
    good_ok = ft.format_success("IMP-0449").to_json()
    if list(result_validator.iter_errors(good_ok)):
        failures.append("valid SUCCESS result rejected")

    if failures:
        print("FAILED:IMP-0449-probe2 coverage-and-shape")
        for item in failures:
            print(" ", item)
        return 1

    print(
        json.dumps(
            {
                "probe": "probe2-coverage-and-shape",
                "unit_id": "IMP-0449",
                "rows": len(live),
                "real_rows": sum(1 for r in live if r["corpus_kind"] == "REAL"),
                "schema_accepted_garbage": 0,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:IMP-0449-probe2 coverage table and closed result shape")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
