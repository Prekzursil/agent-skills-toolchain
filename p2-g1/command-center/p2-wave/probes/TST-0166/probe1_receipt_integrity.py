#!/usr/bin/env python3
"""TST-0166 probe 1: receipt integrity + catalog alignment (suite rebuilt
by shard21-wave3 after the prior builder lost the probes/ dir)."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center" / "receipts" / "TST-0166.json"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
UID = "TST-0166"
SENTINEL = "SUCCESS:TST-0166"


def fail(msg: str) -> int:
    print(f"FAILED:{UID}-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing or empty")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable: {exc}")
    if doc.get("unit_id") != UID:
        return fail(f"unit_id={doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel-absent")

    unit = None
    for u in json.loads(CATALOG.read_text(encoding="utf-8")).get("work_units") or []:
        if u.get("id") == UID:
            unit = u
            break
    if unit is None:
        return fail("catalog-missing")
    if unit.get("output_path") != f"command-center/receipts/TST-0166.json":
        return fail("catalog output_path drift")
    declared = str(doc.get("output_schema") or doc.get("declared_output_schema") or doc.get("output_schema_declaration") or "")
    if declared != str(unit.get("output_schema") or ""):
        return fail(f"output_schema mismatch: {declared!r}")

    rev = doc.get("reviewer") or {}
    if rev.get("verdict") != "PASS" or rev.get("independent") is not True:
        return fail("recorded reviewer closure missing (PASS + independent)")

    for key in ['measurements', 'question_answer', 'scientific_verdict', 'negative_controls', 'control_ids']:
        if key not in doc:
            return fail(f"claim block missing: {key}")

    print(
        json.dumps(
            {
                "probe": "probe1-receipt-integrity",
                "unit_id": UID,
                "state": doc.get("state"),
                "reviewer": str(rev.get("reviewer_id"))[:40],
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(f"SUCCESS:{UID}-probe1 receipt integrity + catalog alignment")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
