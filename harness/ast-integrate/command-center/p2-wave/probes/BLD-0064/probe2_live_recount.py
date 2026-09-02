#!/usr/bin/env python3
"""Probe 2: live disk recount vs emitted ledger, plus both-states extractor.

Re-derives finding counts from command-center/receipts/BLD-0001..0063 and
checks they match the ledger. BLD-0064 is not a source. A scratch tree with
planted receipts must raise the count; claiming that scratch count against
the live tree must fail the validator.
"""
from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import validate as V  # noqa: E402

LEDGER = V.REPO / V.LIVE_LEDGER_REL
RECEIPTS = V.REPO / V.LIVE_RECEIPTS_REL


def main() -> int:
    if not LEDGER.is_file():
        print("FAILED:BLD-0064-probe2 ledger missing")
        return 1
    doc = V.load_json(LEDGER)
    if not isinstance(doc, dict):
        print("FAILED:BLD-0064-probe2 ledger unparseable")
        return 1

    extracted, census = V.census_and_extract(RECEIPTS)
    live_count = len(extracted)
    ledger_count = len(doc.get("findings") or [])
    print(
        "live_present={p} live_absent={a} live_findings={f} ledger_findings={l}".format(
            p=census["present_count"],
            a=census["absent_count"],
            f=live_count,
            l=ledger_count,
        )
    )
    if live_count != ledger_count:
        print("FAILED:BLD-0064-probe2 recount mismatch live vs ledger")
        return 1
    if census["expected_count"] != 63:
        print("FAILED:BLD-0064-probe2 expected_count is not 63")
        return 1
    if "BLD-0064" in census["source_unit_ids"]:
        print("FAILED:BLD-0064-probe2 self-included in source_unit_ids")
        return 1
    if any(row.get("source_unit_id") == "BLD-0064" for row in extracted):
        print("FAILED:BLD-0064-probe2 extracted a BLD-0064 finding")
        return 1
    if "SUCCESS:BLD-0064" not in json.dumps(doc):
        print("FAILED:BLD-0064-probe2 sentinel missing")
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:BLD-0064-probe2 self-declared non-delivery")
        return 1
    if doc.get("counts", {}).get("unassigned") != 0:
        print("FAILED:BLD-0064-probe2 unassigned findings")
        return 1

    errs = V.validate_path(LEDGER, RECEIPTS)
    if errs:
        print("FAILED:BLD-0064-probe2 live ledger invalid")
        for e in errs[:8]:
            print(" ", e)
        return 1

    with tempfile.TemporaryDirectory(prefix="bld0064-probe2-") as tmp:
        scratch = Path(tmp)
        V.write_fixture_receipts(scratch)
        planted, planted_census = V.census_and_extract(scratch)
        print(
            "scratch_present={p} scratch_findings={f}".format(
                p=planted_census["present_count"],
                f=len(planted),
            )
        )
        if len(planted) < 2:
            print("FAILED:BLD-0064-probe2 scratch receipts did not raise finding count")
            return 1
        if len(planted) == live_count:
            print("FAILED:BLD-0064-probe2 scratch count equals live count; both-states silent")
            return 1
        mutant = copy.deepcopy(doc)
        mutant["counts"] = dict(mutant.get("counts") or {})
        mutant["counts"]["findings"] = len(planted)
        mutant["findings"] = [
            {
                **row,
                "disposition": "RESOLVED",
                "evidence": "probe2 planted-receipt control; not a live finding.",
            }
            for row in planted
        ]
        mutant["unassigned_finding_ids"] = []
        mutant["counts"]["RESOLVED"] = len(planted)
        mutant["counts"]["NEW-WORK-UNIT"] = 0
        mutant["counts"]["ACCEPTED-RESIDUAL-RISK"] = 0
        mutant["counts"]["unassigned"] = 0
        rc = dict(mutant.get("receipt_census") or {})
        rc["finding_count_from_receipts"] = len(planted)
        mutant["receipt_census"] = rc
        live_reject = V.validate_ledger(mutant, RECEIPTS)
        print(f"mutant_against_live_rejected={bool(live_reject)}")
        if not live_reject:
            print("FAILED:BLD-0064-probe2 mutant claiming scratch count on live tree passed")
            return 1
        if not any("recount mismatch" in e for e in live_reject):
            print("FAILED:BLD-0064-probe2 live mutant did not fail on recount")
            print(live_reject[:8])
            return 1

    print("recount_match=True self_excluded=True both_states=True")
    print("SUCCESS:BLD-0064-probe2 live recount both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
