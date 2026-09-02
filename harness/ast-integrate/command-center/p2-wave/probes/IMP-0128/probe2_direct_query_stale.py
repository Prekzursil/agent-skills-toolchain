#!/usr/bin/env python3
"""Probe 2: pane values match direct registry APIs; stale renders as STALE.

Independent signal (2): the same values queried from the registry APIs match
what the pane displays. Negative control: a stale metric renders as STALE
with its age, never as a bare number.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "marketplace"))
sys.path.insert(0, str(REPO / "tools" / "monitorcore"))

from cockpit_pane import pane_payload  # noqa: E402
from registry_health import METRIC_IDS  # noqa: E402
from scenario import make_health  # noqa: E402

OUT = HERE / "probe2-direct-query-stale.raw.json"


def main() -> int:
    live, _c1, _p1 = make_health(stale=False)
    pane_live = pane_payload(live)
    direct = live.direct_query()
    rendered = live.render_direct()
    mismatches = []
    for mid in METRIC_IDS:
        if pane_live["values"][mid] != direct[mid].value:
            mismatches.append(mid)
        if pane_live["displays"][mid] != rendered[mid].display:
            mismatches.append(f"{mid}:display")
        if pane_live["statuses"][mid] != "FRESH":
            mismatches.append(f"{mid}:not-fresh")
    if mismatches:
        print(f"FAILED:IMP-0128-probe2 pane/API mismatch {mismatches}")
        return 1

    stale_health, _c2, _p2 = make_health(stale=True)
    raw = stale_health.direct_query()["mirror_conflict_count"].value
    pane_stale = pane_payload(stale_health)
    stale_displays = pane_stale["displays"]
    for mid in METRIC_IDS:
        disp = stale_displays[mid]
        if not str(disp).startswith("STALE"):
            print(f"FAILED:IMP-0128-probe2 {mid} display={disp!r} not STALE")
            return 1
        if pane_stale["values"][mid] is not None:
            print(f"FAILED:IMP-0128-probe2 {mid} still has value={pane_stale['values'][mid]!r}")
            return 1
        if disp == str(raw) or __import__("re").fullmatch(r"-?\d+", str(disp)):
            print(f"FAILED:IMP-0128-probe2 stale display leaked bare number {disp!r}")
            return 1
    if pane_stale["displays"]["mirror_conflict_count"] != "STALE (25h 0m)":
        print(
            "FAILED:IMP-0128-probe2 expected STALE (25h 0m) "
            f"got {pane_stale['displays']['mirror_conflict_count']!r}"
        )
        return 1

    payload = {
        "probe": "probe2-direct-query-stale",
        "unit_id": "IMP-0128",
        "live_match": True,
        "live_values": pane_live["values"],
        "stale_displays": pane_stale["displays"],
        "bare_number_suppressed": True,
        "pass": True,
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:IMP-0128-probe2 direct query match and stale negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
