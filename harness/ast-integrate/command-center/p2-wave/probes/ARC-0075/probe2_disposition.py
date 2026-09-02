#!/usr/bin/env python3
"""Probe 2: PORT-NOW + PORT-LATER + DROP == rows, computed; schema discriminates.

Both-states: stripping a scorecard dimension, lying about totals, or dropping
the minority needle must fail. Empty garbage must fail the decision-record schema.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import salvage as S  # noqa: E402
import schema_local as SL  # noqa: E402

ART = S.REPO / S.OUT_REL


def main() -> int:
    if not ART.is_file():
        print("FAILED:ARC-0075-probe2 SALVAGE-REGISTER.json missing")
        return 1
    raw = ART.read_text(encoding="utf-8")
    doc = json.loads(raw)
    empty_rejected, live_ok, live_errs = SL.reject_empty_accept_live(doc)
    if not empty_rejected:
        print("FAILED:ARC-0075-probe2 schema accepted empty garbage")
        return 1
    print("schema_rejects_empty_garbage=True")
    if not live_ok:
        print("FAILED:ARC-0075-probe2 live artifact schema-invalid")
        for err in live_errs[:12]:
            print(" ", err)
        return 1
    print("schema_accepts_live_artifact=True")

    ok, why = S.check_disposition(doc)
    print(f"disposition_ok={ok} {why}")
    if not ok:
        print("FAILED:ARC-0075-probe2 live disposition failed")
        return 1
    payload = S.domain(doc)
    totals = payload.get("disposition_totals") or {}
    print(
        "totals "
        f"PORT-NOW={totals.get('PORT-NOW')} "
        f"PORT-LATER={totals.get('PORT-LATER')} "
        f"DROP={totals.get('DROP')} "
        f"rows={totals.get('rows')}"
    )

    mutant_dim = copy.deepcopy(doc)
    if not S.domain(mutant_dim).get("salvage_rows"):
        print("FAILED:ARC-0075-probe2 no salvage_rows")
        return 1
    S.domain(mutant_dim)["salvage_rows"][0]["scorecard_dimension"] = "taste"
    dok, dwhy = S.check_disposition(mutant_dim)
    print(f"mutant_bad_dimension ok={dok} {dwhy}")
    if dok:
        print("FAILED:ARC-0075-probe2 accepted a row without a rubric dimension")
        return 1

    mutant_tot = copy.deepcopy(doc)
    S.domain(mutant_tot)["disposition_totals"]["rows"] = int(totals.get("rows") or 0) + 9
    tok, twhy = S.check_disposition(mutant_tot)
    print(f"mutant_lying_totals ok={tok} {twhy}")
    if tok:
        print("FAILED:ARC-0075-probe2 accepted lying disposition totals")
        return 1

    mutant_min = copy.deepcopy(doc)
    for row in S.domain(mutant_min).get("salvage_rows") or []:
        if row.get("minority_preserve"):
            row["mechanism"] = "redacted"
            row["why_not_in_winner"] = "redacted"
    S.domain(mutant_min)["minority_needles"] = [S.MINORITY_NEEDLE]
    nok, nwhy = S.check_disposition(mutant_min)
    print(f"mutant_drop_minority ok={nok} {nwhy}")
    if nok:
        print("FAILED:ARC-0075-probe2 accepted silent drop of minority mechanism")
        return 1

    later = [
        r
        for r in S.domain(doc)["salvage_rows"]
        if r.get("disposition") == "PORT-LATER"
    ]
    if later and not all(r.get("trigger") for r in later):
        print("FAILED:ARC-0075-probe2 PORT-LATER without trigger")
        return 1
    drop = [r for r in S.domain(doc)["salvage_rows"] if r.get("disposition") == "DROP"]
    if drop and not all(r.get("reason") for r in drop):
        print("FAILED:ARC-0075-probe2 DROP without reason")
        return 1
    if "SUCCESS:ARC-0075" not in raw:
        print("FAILED:ARC-0075-probe2 sentinel absent")
        return 1
    print("SUCCESS:ARC-0075-probe2 disposition totality schema minority")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
