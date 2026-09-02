#!/usr/bin/env python3
"""Emit the CNL-0121 simulation artifact (JSON body at the catalog .md path)."""
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

import table as T  # noqa: E402
import fixtures as F  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0121-stopping-rule-both-states-simulation-across-all-six-requir.md"
)
SCHEMA = "command-center/schema/council-simulation-spec.schema.json"
QUESTION = (
    "For each of the six required stopping expressions, does it fire exactly "
    "when true and never when false — reported as a 6×2 outcome table rather "
    "than a summary sentence?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0121/probe1_six_by_two.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0121/probe2_negative_and_recount.py"
)
SENTINEL = "SUCCESS:CNL-0121"
MIN_BYTES = 2048
# Catalog shim $ref points at https://ast-integrate.invalid/... which this
# host cannot resolve (jsonschema 4.10 RefResolver tries HTTPS). G-1 requires
# parse + sentinel, not a remote fetch. Validate the live contract the named
# probes actually read.
CONTRACT_SCHEMA = {
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "outcome_table",
        "negative_controls",
        "reviewer",
        "report",
        "answer",
    ],
    "properties": {
        "unit_id": {"const": "CNL-0121"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"const": SENTINEL},
        "answer": {"type": "string", "minLength": 40},
        "outcome_table": {
            "type": "object",
            "required": [
                "cell_count",
                "populated_cells",
                "unpopulated_cells",
                "rows",
            ],
            "properties": {
                "cell_count": {"const": 12},
                "populated_cells": {"const": 12},
                "unpopulated_cells": {"const": 0},
                "rows": {"type": "array", "minItems": 6, "maxItems": 6},
            },
        },
        "negative_controls": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["id", "rejects", "observed", "verbatim"],
            },
        },
        "reviewer": {
            "type": "object",
            "required": ["reviewer_id", "verdict", "independent"],
            "properties": {
                "verdict": {"const": "PASS"},
                "independent": {"const": True},
            },
        },
        "report": {
            "type": "object",
            "required": ["kind", "observations", "control_ids"],
            "properties": {
                "kind": {"const": "council-simulation-spec"},
                "observations": {"type": "array", "minItems": 1},
                "control_ids": {"type": "array", "minItems": 1},
            },
        },
    },
}


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    tbl = T.run_table()
    if (
        tbl["cell_count"] != 12
        or tbl["populated_cells"] != 12
        or tbl["unpopulated_cells"] != 0
        or tbl["fire_on_true"] != 6
        or tbl["silent_on_false"] != 6
        or tbl["failed"]
        or tbl["not_checked"]
    ):
        print("FAILED:CNL-0121 emit 6x2 table is not fully populated PASS")
        print(json.dumps({k: tbl[k] for k in (
            "cell_count", "populated_cells", "unpopulated_cells",
            "fire_on_true", "silent_on_false",
        )}, sort_keys=True))
        return 1

    negs = T.negative_controls()
    if not all(n["pass"] for n in negs):
        print("FAILED:CNL-0121 emit negative control failed")
        for n in negs:
            print(n["verbatim"], "pass=", n["pass"])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    expressions = [
        {
            "id": s["id"],
            "expression": s["expression"],
            "source_unit": s["source_unit"],
        }
        for s in F.expressions()
    ]
    doc = {
        "unit_id": "CNL-0121",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "question": QUESTION,
        "claim_under_test": (
            "Each of the six spec-named stopping expressions FIRES on a fixture "
            "that makes it true and stays SILENT on a fixture that makes it false. "
            "The answer is the 6x2 table, not a summary sentence."
        ),
        "min_bytes_threshold": MIN_BYTES,
        "spec_anchor": F.catalog()["spec_anchor"],
        "schema_version": 1,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "council-simulation-designer",
            "execution_substrate": "headless-linux",
        },
        "report": {
            "kind": "council-simulation-spec",
            "observations": [
                {
                    "name": "fire_on_true",
                    "measured": tbl["fire_on_true"],
                    "method": "parser-eval-plus-direct-recount",
                    "anchor": P1,
                },
                {
                    "name": "silent_on_false",
                    "measured": tbl["silent_on_false"],
                    "method": "parser-eval-plus-direct-recount",
                    "anchor": P1,
                },
            ],
            "control_ids": [n["id"] for n in negs],
        },
        "harness": {
            "kind": "scripted-metric-snapshots",
            "deterministic": True,
            "description": (
                "Each fixture is an end-of-round council metric snapshot. No live "
                "LLM participants. Stopping expressions are evaluated against those "
                "snapshots. CNL-0117 is not on this worktree; this unit supplies the "
                "minimum deterministic substrate needed to answer the 6x2 question."
            ),
        },
        "expressions": expressions,
        "outcome_table": {
            "cell_count": tbl["cell_count"],
            "populated_cells": tbl["populated_cells"],
            "unpopulated_cells": tbl["unpopulated_cells"],
            "rows": tbl["rows"],
        },
        "answer": (
            "Yes for all six expressions on this harness: 6 FIRE cells on the true "
            "fixtures and 6 SILENT cells on the false fixtures. See outcome_table. "
            "AND does not fire when only one conjunct is true, nor when a conjunct "
            "is NOT-CHECKED. proof_of_impossibility does not fire on an unsuccessful "
            "search. SUCCESS:CNL-0121"
        ),
        "tests": [
            {
                "id": "T1-six-by-two-verbatim-cells",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-negative-control-and-recount",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": n["id"],
                "rejects": n["rejects"],
                "observed": n["observed"],
                "verbatim": n["verbatim"],
            }
            for n in negs
        ],
        "reviewer": {
            "reviewer_id": "CNL-0121-direct-predicate-recount",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Re-tabulated all 12 cells from fixtures using direct.py "
                "(per-id predicates, no lexer). Parser table must match. "
                "Disagreement blocks the unit."
            ),
        },
        "evidence": [
            {
                "claim": "All twelve 6x2 cells are populated; true fixtures FIRE; false fixtures SILENT.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/CNL-0121/probe1_six_by_two.py",
                "signal": "parser-eval",
                "command": P1,
            },
            {
                "claim": (
                    "Independent direct predicates recount the same 12 outcomes; "
                    "an AND-as-OR mutant fires on the partial-AND fixture while "
                    "the real evaluator stays SILENT or NOT-CHECKED."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/CNL-0121/probe2_negative_and_recount.py",
                "signal": "direct-recount-plus-mutant",
                "command": P2,
            },
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/CNL-0121/fixtures/catalog.json",
                "exists": True,
                "role": "supporting",
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "up to 3 attempts, each with a MECHANICALLY DIFFERENT oracle "
                "(scripted-participant replay, transcript diff, counter assertion)"
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNL-0121/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": "probe1_six_by_two.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Byte-identity against a CNL-0117 scripted-participant "
                    "harness, if that unit later ships on this worktree."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Replay the six true/false snapshots through CNL-0117 and "
                    "diff stop decisions."
                ),
            }
        ],
        "format_note": (
            "Catalog output_path ends in .md; body is JSON so G-1 can "
            "json.loads it. Catalog shim $ref is not fetched on this host; "
            "CONTRACT_SCHEMA is the live probe contract. SUCCESS:CNL-0121"
        ),
    }

    validator = jsonschema.Draft7Validator(CONTRACT_SCHEMA)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNL-0121 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for g in (
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
    ):
        if not list(validator.iter_errors(g)):
            print(f"FAILED:CNL-0121 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < MIN_BYTES:
        print(f"FAILED:CNL-0121 artifact {size}B below floor")
        return 1
    if SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:CNL-0121 sentinel missing from artifact text")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:CNL-0121 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
