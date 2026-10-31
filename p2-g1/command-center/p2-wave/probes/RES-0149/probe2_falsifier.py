#!/usr/bin/env python3
"""Named probe 2: independent falsifier control.

Catalog evidence: a conformant record is rejected by the validator when
the falsifier field is removed.

Signal 1: jsonschema Draft-07 required=['falsifier']
Signal 2: semantic_errors() key check (does not call jsonschema)

This probe is the independent adversarial refuter for the schema: it
defaults to REFUTED unless both signals fire on the mutant.
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from validator import evaluate  # noqa: E402

ART = REPO / (
    "command-center/research/evidence-quality/"
    "RES-0149-proof-of-impossibility-record-schema.json"
)
SENTINEL = "SUCCESS:RES-0149"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def fail(msg: str) -> int:
    print(f"FAILED:RES-0149-probe2 {msg}")
    return 1


def required_keys_walker(record: dict, required: list[str]) -> list[str]:
    """Third mechanism: membership walk of schema required[], no jsonschema."""
    missing = []
    for key in required:
        if key not in record:
            missing.append(key)
    return missing


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

    complete = evaluate(example, schema)
    mutant = deepcopy(example)
    if "falsifier" not in mutant:
        return fail("worked example already has no falsifier")
    del mutant["falsifier"]
    removed = evaluate(mutant, schema)
    required = list(schema.get("required") or [])
    walker_missing = required_keys_walker(mutant, required)
    walker_complete = required_keys_walker(example, required)

    payload = {
        "probe": "probe2-falsifier",
        "unit_id": "RES-0149",
        "complete_accepted": complete["accepted"],
        "falsifier_removed_accepted": removed["accepted"],
        "schema_rejected": removed["schema_rejected"],
        "semantic_rejected": removed["semantic_rejected"],
        "walker_missing": walker_missing,
        "walker_complete_missing": walker_complete,
        "schema_errors": removed["schema_errors"][:4],
        "semantic_errors": removed["semantic_errors"][:4],
        "reviewer_verdict": "PASS"
        if (
            complete["accepted"]
            and not removed["accepted"]
            and removed["schema_rejected"]
            and removed["semantic_rejected"]
            and "falsifier" in walker_missing
            and not walker_complete
        )
        else "REFUTED",
        "pass": False,
    }
    payload["pass"] = payload["reviewer_verdict"] == "PASS"
    print(json.dumps(payload, sort_keys=True))
    if not complete["accepted"]:
        return fail("complete record rejected")
    if removed["accepted"]:
        return fail("record without falsifier was accepted")
    if not removed["schema_rejected"]:
        return fail("Draft-07 did not reject missing falsifier")
    if not removed["semantic_rejected"]:
        return fail("semantic walk did not reject missing falsifier")
    if "falsifier" not in walker_missing:
        return fail("required-keys walker did not see missing falsifier")
    if walker_complete:
        return fail(f"complete record missing required {walker_complete}")
    print(
        "NEGATIVE CONTROL (falsifier removed): REJECT the mutant; ACCEPT the "
        "complete record. jsonschema, semantic walk, and required-keys walker "
        "all fire. Reviewer verdict=PASS."
    )
    print("SUCCESS:RES-0149-probe2 falsifier-removed independent walker")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
