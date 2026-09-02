#!/usr/bin/env python3
"""Named probe 1: both-states empty exhausted_sources vs complete record.

Catalog test: the validator must reject a record whose exhausted_sources
list is empty (a not-found masquerading as impossible) and accept the
complete one.

Two signals:
  1. jsonschema Draft-07 minItems on exhausted_sources
  2. hand-rolled semantic_errors() (does not call jsonschema)
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from validator import evaluate, schema_is_vacuous  # noqa: E402

ART = REPO / (
    "command-center/research/evidence-quality/"
    "RES-0149-proof-of-impossibility-record-schema.json"
)
SENTINEL = "SUCCESS:RES-0149"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def fail(msg: str) -> int:
    print(f"FAILED:RES-0149-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable {exc}")
    if doc.get("unit_id") != "RES-0149":
        return fail(f"unit_id {doc.get('unit_id')}")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return fail(f"self-declared:{st}")
    schema = doc.get("record_schema")
    example = doc.get("worked_example")
    if not isinstance(schema, dict) or not isinstance(example, dict):
        return fail("record_schema or worked_example missing")
    if schema_is_vacuous(schema):
        return fail("schema accepts garbage")

    complete = evaluate(example, schema)
    empty_rec = deepcopy(example)
    empty_rec["exhausted_sources"] = []
    empty = evaluate(empty_rec, schema)

    payload = {
        "probe": "probe1-both-states",
        "unit_id": "RES-0149",
        "complete_accepted": complete["accepted"],
        "empty_accepted": empty["accepted"],
        "empty_schema_rejected": empty["schema_rejected"],
        "empty_semantic_rejected": empty["semantic_rejected"],
        "empty_schema_errors": empty["schema_errors"][:4],
        "empty_semantic_errors": empty["semantic_errors"][:4],
        "pass": bool(
            complete["accepted"]
            and not empty["accepted"]
            and empty["schema_rejected"]
            and empty["semantic_rejected"]
        ),
    }
    print(json.dumps(payload, sort_keys=True))
    if not complete["accepted"]:
        return fail("complete record rejected")
    if empty["accepted"]:
        return fail("empty exhausted_sources was accepted (not-found masquerade)")
    if not empty["schema_rejected"]:
        return fail("Draft-07 did not reject empty exhausted_sources")
    if not empty["semantic_rejected"]:
        return fail("semantic walk did not reject empty exhausted_sources")
    if complete["accepted"] == empty["accepted"]:
        return fail("detector silent in both states")
    print(
        "NEGATIVE CONTROL (empty exhausted_sources): REJECT empty list, "
        "ACCEPT complete record; both jsonschema and semantic walk fire."
    )
    print("SUCCESS:RES-0149-probe1 both-states empty-sources vs complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
