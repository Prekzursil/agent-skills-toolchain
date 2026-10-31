#!/usr/bin/env python3
"""TST-0164 probe 1: receipt integrity + catalog alignment (rebuild on tree).

The original probe tree (probes/TST-0164/*) was lost with the dead prior
builder; this shard rebuilds the probe suite. Probe 1 verifies the receipt
artifact against its catalog contract and its recorded reviewer closure.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center" / "receipts" / "TST-0164.json"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
UID = "TST-0164"
SENTINEL = "SUCCESS:TST-0164"


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
    if unit.get("output_path") != "command-center/receipts/TST-0164.json":
        return fail("catalog output_path drift")
    declared = str(doc.get("output_schema") or doc.get("declared_output_schema") or "")
    if declared != str(unit.get("output_schema") or ""):
        return fail(f"output_schema mismatch: {declared!r}")
    q = str(unit.get("question_or_target") or "")
    rq = str(doc.get("question") or "")
    if q[:80] != rq[:80]:
        return fail("receipt question does not anchor the catalog question")

    rev = doc.get("reviewer") or {}
    if rev.get("verdict") != "PASS" or rev.get("independent") is not True:
        return fail("recorded reviewer closure missing (PASS + independent)")

    for key in (
        "declared_nondeterministic_fields",
        "normalized_diff",
        "byte_diff",
        "both_states",
        "mask_coverage_ceiling",
        "flags",
    ):
        if key not in doc:
            return fail(f"claim block missing: {key}")

    mask = doc.get("declared_nondeterministic_fields") or []
    if not mask or any(not isinstance(f, str) for f in mask):
        return fail("declared mask is not a non-empty string list")
    if "*" in mask or len(mask) > (doc.get("mask_coverage_ceiling") or {}).get("max_fields", 8):
        return fail("mask violates its own coverage ceiling")

    print(
        json.dumps(
            {
                "probe": "probe1-receipt-integrity",
                "unit_id": UID,
                "state": doc.get("state"),
                "mask": mask,
                "reviewer": rev.get("reviewer_id"),
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(f"SUCCESS:{UID}-probe1 receipt integrity + catalog alignment")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
