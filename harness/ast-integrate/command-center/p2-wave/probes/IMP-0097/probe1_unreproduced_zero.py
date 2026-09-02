#!/usr/bin/env python3
"""Named probe 1: UNREPRODUCED records contribute exactly zero.

Signal is score equality with vs without the record (live arithmetic), not a
comment in a doc. Same run includes the negative control that an independently
cased, independently reproduced record does raise the score.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.marketplace.benchmark_gaming import (  # noqa: E402
    contribution,
    score_with_benchmarks,
    score_without_record,
)
from tools.marketplace.scenario import load_scenario  # noqa: E402
from tools.marketplace.tests.test_benchmark_gaming import (  # noqa: E402
    test_unreproduced_contributes_zero,
    test_reproduced_independently_cased_raises_score,
)

ART = REPO / "command-center/receipts/IMP-0097.json"
DEAD_IDS = (
    "rec.unreproduced.claim",
    "rec.publisher-only.rerun",
    "rec.failed.independent",
)
GOOD_ID = "rec.independent.reproduced"


def _fail(msg: str, extra=None) -> int:
    print(f"FAILED:IMP-0097-probe1 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return _fail("receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    text = ART.read_text(encoding="utf-8")
    if doc.get("unit_id") != "IMP-0097":
        return _fail("unit_id", doc.get("unit_id"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return _fail(f"self-declared:{doc.get('state')}")
    if "SUCCESS:IMP-0097" not in text:
        return _fail("sentinel-absent")

    measurements, records, provenance, _raw = load_scenario()
    full = score_with_benchmarks(measurements, records, provenance)
    by_id = {r.record_id: r for r in records}

    equalities = []
    for dead_id in DEAD_IDS:
        dead = by_id[dead_id]
        contrib = contribution(dead, provenance)
        without = score_without_record(measurements, records, provenance, dead_id)
        equalities.append(
            {
                "record_id": dead_id,
                "claimed_delta": dead.claimed_delta,
                "contribution": contrib,
                "full_total": full.total,
                "without_total": without.total,
                "equal": full.total == without.total,
            }
        )
        if contrib != 0.0:
            return _fail("unreproduced contribution is not zero", equalities[-1])
        if full.total != without.total:
            return _fail("score moved when unreproduced record removed", equalities[-1])

    good = by_id[GOOD_ID]
    without_good = score_without_record(measurements, records, provenance, GOOD_ID)
    raised = full.total - without_good.total
    if raised != good.claimed_delta or raised <= 0:
        return _fail(
            "negative control: independently-cased reproduced record did not raise score",
            {
                "full_total": full.total,
                "without_good": without_good.total,
                "raised": raised,
                "claimed_delta": good.claimed_delta,
            },
        )

    claimed = ((doc.get("evidence") or {}).get("signal_1_unreproduced_zero") or {})
    if claimed:
        if float(claimed.get("full_total")) != full.total:
            return _fail("receipt signal_1 full_total != live", {"live": full.total, "receipt": claimed})
        if float(claimed.get("unreproduced_contribution")) != 0.0:
            return _fail("receipt claimed non-zero unreproduced contribution", claimed)

    test_unreproduced_contributes_zero()
    test_reproduced_independently_cased_raises_score()

    payload = {
        "probe": "probe1-unreproduced-zero",
        "unit_id": "IMP-0097",
        "pass": True,
        "base": full.base,
        "full_total": full.total,
        "without_good_total": without_good.total,
        "raised_by_independent": raised,
        "equalities": equalities,
        "computed_not_asserted": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"unreproduced_zero=True independent_raises={raised} "
        f"base={full.base} total={full.total}"
    )
    print("SUCCESS:IMP-0097-probe1 unreproduced contributes zero")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
