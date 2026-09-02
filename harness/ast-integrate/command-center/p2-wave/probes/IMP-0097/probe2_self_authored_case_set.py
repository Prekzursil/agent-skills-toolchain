#!/usr/bin/env python3
"""Named probe 2: self-authored case set is flagged against known provenance.

Different field than probe 1: case-set authorship from the provenance fixture,
not reproduction-status arithmetic. A flag that leaves the score unchanged
would be an overclaim; this probe requires contribution == 0.0 as well.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.marketplace.benchmark_gaming import (  # noqa: E402
    FLAG_SELF_AUTHORED,
    contribution,
    is_self_authored,
    score_with_benchmarks,
    score_without_record,
)
from tools.marketplace.scenario import load_scenario  # noqa: E402
from tools.marketplace.tests.test_benchmark_gaming import (  # noqa: E402
    test_self_authored_case_set_is_flagged,
)

ART = REPO / "command-center/receipts/IMP-0097.json"
PLANTED_ID = "rec.self-authored.reproduced"
GOOD_ID = "rec.independent.reproduced"
PLANTED_CASE = "bench.acme.easy-v1"


def _fail(msg: str, extra=None) -> int:
    print(f"FAILED:IMP-0097-probe2 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return _fail("receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:IMP-0097" not in ART.read_text(encoding="utf-8"):
        return _fail("sentinel-absent")
    residual = (doc.get("reviewer") or {}).get("disclosed_residual")
    if not residual:
        return _fail("reviewer disclosed_residual missing")

    measurements, records, provenance, _raw = load_scenario()
    planted = next(r for r in records if r.record_id == PLANTED_ID)
    good = next(r for r in records if r.record_id == GOOD_ID)

    authors = provenance[PLANTED_CASE].authors
    if authors != ("publisher.acme",):
        return _fail("provenance fixture authors drifted", {"authors": list(authors)})
    if planted.publisher_id != "publisher.acme":
        return _fail("publisher_id drifted", {"publisher_id": planted.publisher_id})
    if not is_self_authored(planted, provenance):
        return _fail("planted self-authored record not detected")
    if is_self_authored(good, provenance):
        return _fail("independently-cased record falsely flagged as self-authored")

    full = score_with_benchmarks(measurements, records, provenance)
    flags = [
        f
        for f in full.flags
        if f["flag"] == FLAG_SELF_AUTHORED and f["record_id"] == PLANTED_ID
    ]
    if not flags:
        return _fail("SELF_AUTHORED_CASE_SET flag absent", full.as_dict())
    if contribution(planted, provenance) != 0.0:
        return _fail("self-authored still contributes (docs-not-arithmetic overclaim)")
    without = score_without_record(measurements, records, provenance, PLANTED_ID)
    if full.total != without.total:
        return _fail("self-authored changed the score", {"full": full.total, "without": without.total})

    without_good = score_without_record(measurements, records, provenance, GOOD_ID)
    if not (full.total > without_good.total):
        return _fail("independently-cased reproduced record did not raise score")

    claimed = ((doc.get("evidence") or {}).get("signal_2_self_authored") or {})
    if claimed:
        if claimed.get("flag") != FLAG_SELF_AUTHORED:
            return _fail("receipt signal_2 flag mismatch", claimed)
        if claimed.get("case_set_id") != PLANTED_CASE:
            return _fail("receipt signal_2 case_set mismatch", claimed)
        if float(claimed.get("contribution")) != 0.0:
            return _fail("receipt signal_2 contribution not zero", claimed)

    test_self_authored_case_set_is_flagged()

    payload = {
        "probe": "probe2-self-authored-case-set",
        "unit_id": "IMP-0097",
        "pass": True,
        "flagged": True,
        "flag": FLAG_SELF_AUTHORED,
        "planted_record_id": PLANTED_ID,
        "case_set_id": PLANTED_CASE,
        "authors": list(authors),
        "self_authored_contribution": 0.0,
        "independent_raises": full.total - without_good.total,
        "computed_not_asserted": True,
        "disclosed_residual_present": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"self_authored_flagged=True contribution=0.0 "
        f"independent_raises={full.total - without_good.total}"
    )
    print("SUCCESS:IMP-0097-probe2 self-authored case set flagged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
