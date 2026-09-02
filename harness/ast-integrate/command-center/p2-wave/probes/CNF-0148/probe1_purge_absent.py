#!/usr/bin/env python3
"""Probe 1: detector control — known cached artifact absent after measured purge.

Signal 1: cache directory byte size before vs after (must drop).
Signal 2: explicit existence probe of a named cache entry (must vanish).
Also requires a result delta attributed to a named cache entry.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from experiment import predicates, run  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0148.json"
RAW = HERE / "probe1-purge-absent.raw.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0148-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "CNF-0148":
        print("FAILED:CNF-0148-probe1 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0148-probe1 self-declared", doc.get("state"))
        return 1
    if "SUCCESS:CNF-0148" not in text:
        print("FAILED:CNF-0148-probe1 sentinel absent")
        return 1

    live = run()
    bad = predicates(live)
    RAW.write_text(json.dumps(live, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if bad:
        print("FAILED:CNF-0148-probe1 " + ",".join(bad))
        return 1
    det = live["detector_control"]
    purge = live["purge"]
    if not det["present_before"] or det["present_after"]:
        print("FAILED:CNF-0148-probe1 known artifact still present or never seeded")
        return 1
    if int(purge["before_bytes"]) <= 0 or int(purge["after_bytes"]) != 0:
        print(
            f"FAILED:CNF-0148-probe1 sizes before={purge['before_bytes']} "
            f"after={purge['after_bytes']}"
        )
        return 1
    if not live["flips"]:
        print("FAILED:CNF-0148-probe1 no confirmation flipped after purge")
        return 1
    print(
        f"known={det['known_artifact_rel']} present_before={det['present_before']} "
        f"present_after={det['present_after']} before_bytes={purge['before_bytes']} "
        f"after_bytes={purge['after_bytes']} flips={len(live['flips'])} "
        f"survivors={live['survivors']}"
    )
    print("SUCCESS:CNF-0148-probe1 purge measured and known artifact absent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
