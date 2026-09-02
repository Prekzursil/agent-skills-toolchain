#!/usr/bin/env python3
"""Probe 2: unjustified equivalent-mutant exclusions are rejected.

Catalog test: test_an_unjustified_exclusion_is_rejected.
Planted cases must fire; the clean reviewed list must stay accepted.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from policy import REVIEWER_ID, TEST_UNJUSTIFIED  # noqa: E402
from triage import detector_controls, publish_score  # noqa: E402

ART = REPO / "command-center/receipts/TST-0120.json"
SCHEMA = REPO / "command-center/schema/detector-control.schema.json"
UID = "TST-0120"
GARBAGE = (
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {},
)


def fail(msg: str) -> int:
    print(f"FAILED:TST-0120-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != UID:
        return fail(f"unit_id {doc.get('unit_id')}")
    if "SUCCESS:TST-0120" not in text:
        return fail("sentinel-absent")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = list(validator.iter_errors(doc))
    if errs:
        return fail(f"schema {errs[0].message}")
    for garbage in GARBAGE:
        if not list(validator.iter_errors(garbage)):
            return fail(f"schema accepted garbage {list(garbage)[:2]}")

    ctrl = detector_controls()
    if not ctrl["planted_fired"]:
        return fail("planted detector did not fire")
    if not ctrl["clean_silent"]:
        return fail("clean score not accepted")

    planted = ctrl["planted"]
    if planted["boilerplate_justification"]["accepted"]:
        return fail("boilerplate justification accepted")
    if planted["false_equivalent_sentinel"]["accepted"]:
        return fail("false equivalent (killable sentinel) accepted")
    if planted["missing_reviewer"]["accepted"]:
        return fail("missing reviewer accepted")
    if planted["reviewer_is_author"]["accepted"]:
        return fail("author-as-reviewer accepted")

    live_ids = {r["mutant_id"] for r in ctrl["clean"]["exclusions"]}
    art_ids = {r["mutant_id"] for r in (doc.get("exclusions") or [])}
    if live_ids != art_ids:
        return fail(f"exclusion ids live={sorted(live_ids)} art={sorted(art_ids)}")
    for row in doc.get("exclusions") or []:
        if row.get("reviewer_id") != REVIEWER_ID:
            return fail(f"exclusion {row.get('mutant_id')} reviewer")
        if len(str(row.get("justification") or "")) < 80:
            return fail(f"exclusion {row.get('mutant_id')} short justification")

    empty = publish_score(
        ctrl["measured"],
        [
            {
                "mutant_id": "M-EQ-LF-CRLF",
                "operator": "lf-crlf-flip",
                "location": "subject.write_lines",
                "justification": "",
                "reviewer_id": REVIEWER_ID,
            }
        ],
    )
    if empty["accepted"]:
        return fail("empty justification accepted")

    dc = doc.get("detector_control") or {}
    if dc.get("fired") is not True or dc.get("silent") is not True:
        return fail("artifact detector_control flags")
    if not (doc.get("controls") or {}).get("unjustified_exclusion_rejected"):
        return fail("artifact controls.unjustified_exclusion_rejected")

    counts = doc.get("counts") or {}
    if counts.get("VALID", 0) < 1 or counts.get("SILENT-IN-BOTH", 1) != 0:
        return fail(f"gate counts {counts}")

    summary = {
        "probe": "probe2-unjustified-exclusion-rejected",
        "unit_id": UID,
        "test": TEST_UNJUSTIFIED,
        "pass": True,
        "boilerplate_rejected": True,
        "false_equivalent_rejected": True,
        "missing_reviewer_rejected": True,
        "author_reviewer_rejected": True,
        "empty_justification_rejected": True,
        "clean_accepted": True,
        "exclusion_count": ctrl["clean"]["exclusion_count"],
        "schema_ok": True,
        "garbage_rejected": True,
        "gates_valid": counts.get("VALID"),
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        "boilerplate_rejected=True false_eq_rejected=True "
        "clean_accepted=True schema_ok=True"
    )
    print("SUCCESS:TST-0120-probe2 unjustified exclusion rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
