#!/usr/bin/env python3
"""Named probe 2: mutation control — disable pinning and the property must fail.

Mechanically different from probe 1: this probe's oracle is that LRU-only
eviction removes in-use keys (eviction log names holder keys AND holders miss).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from harness import run_mutation_suite  # noqa: E402

ART = REPO / "command-center/receipts/TST-0178.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:TST-0178-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:TST-0178" not in ART.read_text(encoding="utf-8"):
        print("FAILED:TST-0178-probe2 sentinel absent")
        return 1

    live = run_mutation_suite()
    if not live.get("ok") or not live.get("detector_fired"):
        print("FAILED:TST-0178-probe2 mutation did not break the property")
        print(json.dumps(live.get("harsh"), indent=2, default=str)[:3000])
        return 1
    harsh = live["harsh"]
    if harsh.get("pinning_enabled") is not False:
        print("FAILED:TST-0178-probe2 harsh trial still had pinning")
        return 1
    if harsh.get("property_holds"):
        print("FAILED:TST-0178-probe2 property still holds with pinning disabled")
        return 1
    if not harsh.get("in_use_evicted"):
        print("FAILED:TST-0178-probe2 no in-use eviction under mutation")
        return 1
    if int(harsh.get("held_eviction_count") or 0) < 1:
        print("FAILED:TST-0178-probe2 eviction log did not name a held key")
        return 1
    if int(harsh.get("reader_miss_count") or 0) < 1:
        print("FAILED:TST-0178-probe2 holders did not miss after eviction")
        return 1

    recorded = doc.get("mutation_suite") or {}
    if not recorded.get("detector_fired"):
        print("FAILED:TST-0178-probe2 artifact mutation detector not fired")
        return 1
    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") != "PASS":
        print("FAILED:TST-0178-probe2 reviewer verdict")
        return 1

    payload = {
        "pass": True,
        "probe": "probe2-mutation-control",
        "unit_id": "TST-0178",
        "detector_fired": True,
        "harsh_held_eviction_count": harsh["held_eviction_count"],
        "harsh_reader_miss_count": harsh["reader_miss_count"],
        "property_failed_count": live["property_failed_count"],
        "computed_not_asserted": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "pinning=off property_holds=False "
        f"held_evictions={harsh['held_eviction_count']} "
        f"reader_misses={harsh['reader_miss_count']}"
    )
    print("SUCCESS:TST-0178-probe2 mutation control pinning-off fails property")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
