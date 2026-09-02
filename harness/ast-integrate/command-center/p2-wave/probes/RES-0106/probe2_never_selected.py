#!/usr/bin/env python3
"""Probe 2: never-selected detector both-states + false-alarm control.

known-good  -> silent (no routing defect)
known-broken -> fires on calendar.create (gold-expected, never selected)
false-alarm -> debug.dump_internal_state is never selected AND must not fire
naive catalog-minus-selected DOES fire on the kill-switch (proves the
exclusion is load-bearing, not a silent detector).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402

ART = REPO / "command-center/research/RES-0106.json"
FIX = HERE / "fixtures"
BROKEN_ID = "calendar.create"
FALSE_ALARM_ID = "debug.dump_internal_state"


def load_fix() -> tuple[list, list, list, list]:
    catalog = json.loads((FIX / "catalog.json").read_text(encoding="utf-8"))[
        "capabilities"
    ]
    golden = json.loads((FIX / "golden_queries.json").read_text(encoding="utf-8"))[
        "queries"
    ]
    good = json.loads((FIX / "selection_log_good.json").read_text(encoding="utf-8"))[
        "rows"
    ]
    broken = json.loads(
        (FIX / "selection_log_broken.json").read_text(encoding="utf-8")
    )["rows"]
    return catalog, golden, good, broken


def fail(msg: str) -> int:
    print(f"FAILED:RES-0106-probe2 {msg}")
    return 1


def main() -> int:
    catalog, golden, good, broken = load_fix()
    g = D.run_detector(catalog, golden, good)
    b = D.run_detector(catalog, golden, broken)
    print(
        "good.fires="
        f"{g['fires']} good.defects={g['never_selected_routing_defect']}"
    )
    print(
        "broken.fires="
        f"{b['fires']} broken.defects={b['never_selected_routing_defect']}"
    )
    print(
        "false_alarm_excluded="
        f"{FALSE_ALARM_ID in g['never_by_design_ids']} "
        f"good.leak={g['false_alarm_leak']} broken.leak={b['false_alarm_leak']}"
    )
    if g["fires"] or g["never_selected_routing_defect"]:
        return fail("known-good was not silent")
    if not b["fires"]:
        return fail("known-broken was silent")
    if BROKEN_ID not in b["never_selected_routing_defect"]:
        return fail(f"known-broken did not name {BROKEN_ID}")
    if FALSE_ALARM_ID in g["never_selected_routing_defect"]:
        return fail("false-alarm capability leaked on known-good")
    if FALSE_ALARM_ID in b["never_selected_routing_defect"]:
        return fail("false-alarm capability leaked on known-broken")
    if g["false_alarm_leak"] or b["false_alarm_leak"]:
        return fail("false_alarm_leak non-empty")
    if FALSE_ALARM_ID not in g["never_by_design_ids"]:
        return fail("kill-switch not listed as never-by-design")

    naive_good = D.naive_catalog_minus_selected(catalog, good)
    naive_broken = D.naive_catalog_minus_selected(catalog, broken)
    print(f"naive.good={naive_good}")
    print(f"naive.broken={naive_broken}")
    if FALSE_ALARM_ID not in naive_good:
        return fail("naive detector did not false-alarm on kill-switch (control broken)")
    if BROKEN_ID not in naive_broken:
        return fail("naive detector missed the real defect")

    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    det = doc.get("never_selected_detector") or {}
    fa = det.get("false_alarm_case") or {}
    if str(fa.get("capability_id")) != FALSE_ALARM_ID:
        return fail("artifact false-alarm case mismatch")
    if "when_it_runs" not in det or not det.get("when_it_runs"):
        return fail("artifact when_it_runs missing")
    ds = json.dumps(det.get("data_source") or {}).lower()
    if "catalog" not in ds or "golden" not in ds:
        return fail("artifact data_source incomplete")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"artifact self-declared {doc.get('state')}")
    print("SUCCESS:RES-0106-probe2 detector-control known-good/known-broken/false-alarm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
