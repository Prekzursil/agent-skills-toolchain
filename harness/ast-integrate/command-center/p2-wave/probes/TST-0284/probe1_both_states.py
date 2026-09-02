#!/usr/bin/env python3
"""Probe 1: both-states control on the five-element gate.

Rejects a record with no refuting-observation field. Accepts a well-formed
record (no over-blocking). Recomputes live and compares to the receipt.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from validator import validate  # noqa: E402

ART = REPO / "command-center/receipts/TST-0284.json"
FIXTURES = HERE / "fixtures" / "records.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0284-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    text = json.dumps(doc)
    if "SUCCESS:TST-0284" not in text:
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    fx = json.loads(FIXTURES.read_text(encoding="utf-8"))
    good = validate(fx["well_formed"])
    missing = validate(fx["missing_refuting_observation"])
    if not good["accepted"]:
        return fail(f"over-blocking well-formed: {good['reasons']}")
    if missing["accepted"]:
        return fail("missing refuting_observation was accepted")
    if "missing-field:refuting_observation" not in missing["reasons"]:
        return fail(f"missing-field reason absent: {missing['reasons']}")
    if "refuting_observation" not in missing["missing"]:
        return fail("refuting_observation not listed missing")
    if missing["classification"] != "missing-refuting-observation":
        return fail(f"classification={missing['classification']}")

    both = doc.get("both_states") or {}
    if both.get("well_formed_accepted") is not True:
        return fail("receipt well_formed_accepted is not true")
    if both.get("missing_refuting_observation_accepted") is not False:
        return fail("receipt missing-field control did not reject")
    rec_good = (doc.get("tests") or {}).get("accepts_well_formed") or {}
    rec_miss = (doc.get("tests") or {}).get("rejects_missing_refuting_observation") or {}
    if rec_good.get("pass") is not True or rec_miss.get("pass") is not True:
        return fail("receipt tests did not record both-states PASS")

    empty = validate(fx["empty_refuting_observation"])
    if empty["accepted"]:
        return fail("empty refuting_observation was accepted")

    summary = {
        "probe": "probe1-both-states",
        "unit_id": "TST-0284",
        "pass": True,
        "well_formed_accepted": True,
        "missing_rejected": True,
        "empty_rejected": True,
        "missing_reasons": missing["reasons"],
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        "well_formed=ACCEPTED missing_field=REJECTED empty_field=REJECTED "
        "over_blocking=False"
    )
    print("SUCCESS:TST-0284-probe1 both-states missing-field vs well-formed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
