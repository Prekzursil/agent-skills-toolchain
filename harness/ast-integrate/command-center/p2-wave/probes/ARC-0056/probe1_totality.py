#!/usr/bin/env python3
"""Named probe 1: disposition totality from a live tree walk (set equality).

Field: enumerated name set vs preserved∪aliased∪deprecated∪removed.
Mechanically different from probe 2 (resolved target strings).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from dispositions import partition  # noqa: E402
from enumerate import enumerate_live  # noqa: E402
from usage import counts_in_window, load_events  # noqa: E402

ART = REPO / "command-center/phase3/A8/MIGRATION.json"
LIVE = HERE / "fixtures" / "live"
LEDGER = HERE / "fixtures" / "usage-ledger.jsonl"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:ARC-0056-probe1 migration artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "ARC-0056":
        print("FAILED:ARC-0056-probe1 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:ARC-0056" not in json.dumps(doc):
        print("FAILED:ARC-0056-probe1 sentinel absent")
        return 1

    rows = enumerate_live(LIVE)
    names = [r["name"] for r in rows]
    usage = counts_in_window(load_events(LEDGER))
    part = partition(names, usage)
    if part["gaps"] or part["overlaps"] or part["removal_blocked"] or not part["totality_holds"]:
        print("FAILED:ARC-0056-probe1 totality")
        print(json.dumps(part, indent=2, default=str)[:3000])
        return 1

    disp = doc.get("dispositions") or {}
    recorded_names = list((doc.get("enumeration") or {}).get("names") or [])
    if sorted(recorded_names) != sorted(names):
        print("FAILED:ARC-0056-probe1 enumeration drift vs artifact")
        print("live", sorted(names))
        print("art ", sorted(recorded_names))
        return 1
    for key in ("preserved", "aliased", "deprecated", "removed"):
        if sorted(disp.get(key) or []) != sorted(part[key]):
            print(f"FAILED:ARC-0056-probe1 {key} drift")
            return 1
    tests = (doc.get("tests") or {}).get("disposition_totality") or {}
    if int(tests.get("enumerated") or -1) != len(names):
        print("FAILED:ARC-0056-probe1 artifact enumerated count drift")
        return 1
    summed = (
        len(part["preserved"])
        + len(part["aliased"])
        + len(part["deprecated"])
        + len(part["removed"])
    )
    if summed != len(names):
        print("FAILED:ARC-0056-probe1 sum_of_buckets", summed, len(names))
        return 1

    out = {
        "probe": "probe1-disposition-totality",
        "unit_id": "ARC-0056",
        "enumerated": len(names),
        "sum_of_buckets": summed,
        "counts": part["counts"],
        "gaps": [],
        "overlaps": [],
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"enumerated={len(names)} preserved={len(part['preserved'])} "
        f"aliased={len(part['aliased'])} deprecated={len(part['deprecated'])} "
        f"removed={len(part['removed'])}"
    )
    print("SUCCESS:ARC-0056-probe1 disposition totality")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
