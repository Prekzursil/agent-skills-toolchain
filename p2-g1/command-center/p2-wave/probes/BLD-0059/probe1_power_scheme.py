#!/usr/bin/env python3
"""BLD-0059 probe1 - structural + sentinel delivery predicate (live, fail-closed).

Checks the sampling scheme acceptance: detect(14, 0.20) = 1 - 0.8**14 == the recorded 0.95601953488896 >= claimed confidence 0.95, the weak n=3 scheme rejected, and the census-slot arithmetic behind the makespan lower bound.
Recreated 2026-10-25 (wave-2 shard 7) after the original probe tree was lost.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
OUT = REPO / "command-center/receipts/BLD-0059.json"
UNIT = "BLD-0059"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def main() -> int:
    fails = []
    notes = []

    def check(ok: bool, label: str, detail: str = "") -> None:
        if not ok:
            fails.append(label + (": " + detail if detail else ""))

    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print("FAILED:%s-probe1 artifact unreadable/unparseable: %s" % (UNIT, type(exc).__name__))
        return 1
    if not isinstance(doc, dict):
        print("FAILED:%s-probe1 artifact is not a JSON object" % UNIT)
        return 1

    check(doc.get("unit_id") == UNIT, "unit_id mismatch", str(doc.get("unit_id")))
    check(str(doc.get("state", "")).upper() not in NOT_DELIVERING,
          "self-declared non-delivery", str(doc.get("state")))
    check(OUT.stat().st_size > 0, "artifact empty")
    minb = int(doc.get("min_bytes_threshold") or 0)
    check(OUT.stat().st_size >= minb, "below min_bytes_threshold",
          "%s < %s" % (OUT.stat().st_size, minb))
    sentinel = str(doc.get("completion_sentinel") or doc.get("sentinel") or "")
    check(bool(sentinel) and sentinel in text, "sentinel absent from artifact text")

    smp = doc.get("sampling") or {}
    acc = (smp.get("acceptance_criterion") or {}).get("claimed_scheme") or {}
    n, p, conf = int(acc.get("n", -1)), float(acc.get("prevalence", -1)), float(acc.get("claimed_confidence", -1))
    check((n, p, conf) == (14, 0.20, 0.95), "claimed scheme drift", "n=%s p=%s conf=%s" % (n, p, conf))
    want = 1.0 - (1.0 - p) ** n
    check(abs(float(acc.get("detection_probability", -1)) - want) < 1e-9,
          "recorded detection != 1-(1-p)**n", "recorded=%s recomputed=%.14f" % (acc.get("detection_probability"), want))
    check(acc.get("accepted") is True and want >= conf, "acceptance decision drift", "accepted=%s" % acc.get("accepted"))
    weak = (smp.get("acceptance_criterion") or {}).get("weak_n3_scheme") or {}
    check(weak.get("accepted") is False and (1.0 - (1.0 - p) ** 3) < conf,
          "weak n=3 scheme must be rejected", str(weak.get("accepted")))
    check(int(doc.get("baseline_n", -1)) == 2007 and int(doc.get("scaled_n", -1)) == 20070
          and int(doc.get("scale_factor", -1)) == 10, "scale chain drift", str(doc.get("baseline_n")))
    ms = doc.get("makespan") or {}
    lb = (ms.get("lower_bound_this_recompute_10x") or {})
    check(int(lb.get("census_slots", -1)) == 22450, "census slots drift", str(lb.get("census_slots")))
    row0 = (lb.get("rows") or [{}])[0]
    impl_h = float(row0.get("implementer_h", -1))
    be = float(row0.get("break_even_t_review_s", -1))
    want_be = impl_h * 3600.0 / float(lb.get("census_slots", 1))
    check(abs(be - want_be) <= 0.1, "break-even identity drift", "recorded=%s recomputed=%.4f" % (be, want_be))
    meas = doc.get("measurements") or []
    m0 = next((m for m in meas if m.get("id") == "catalog-reviewer-coverage"), None)
    check(m0 is not None and int(m0.get("reviewer_requirement_non_empty", -1)) == 2007
          and int(m0.get("two_reviewer_units", -1)) == 238,
          "catalog reviewer-coverage measurement drift", str(m0 and (m0.get("reviewer_requirement_non_empty"), m0.get("two_reviewer_units"))))
    check((HERE / "power.py").is_file(), "instrument power.py missing")

    report = {
        "probe": "probe1-delivery-predicate",
        "unit_id": UNIT,
        "artifact_bytes": OUT.stat().st_size,
        "notes": notes,
        "fails": fails,
    }
    print(json.dumps(report, indent=1))
    if fails:
        print("FAILED:%s-probe1 %s" % (UNIT, "; ".join(fails)))
        return 1
    print("SUCCESS:%s-probe1 delivery predicate holds" % UNIT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
