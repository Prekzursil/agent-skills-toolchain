#!/usr/bin/env python3
"""Named probe 1: blind recomputation from raw records, fusion-lane unread.

Must not import fusion_lane. Live independent scores must match the artifact.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import pipeline as P  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0117-fusion-independent-review.json"
UNIT = "WFA-0117"


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != UNIT:
        return fail("unit_id", doc.get("unit_id"))
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    blob = json.dumps(doc)
    if "SUCCESS:WFA-0117" not in blob:
        return fail("sentinel absent")

    proto = doc.get("independence_protocol") or {}
    if proto.get("fusion_unread_before_recompute") is not True:
        return fail("fusion was not unread before recompute")
    if proto.get("recompute_module_omits_fusion_lane") is not True:
        return fail("recompute module not marked blind")

    live = P.live_independent()
    if not live["blind"]["ok"]:
        return fail("recompute.py is not blind", live["blind"])
    if "fusion_lane" in sys.modules:
        return fail("probe1 imported fusion_lane")

    live_v = P.verdict_map(live["independent"]["verdicts"])
    art_v = P.verdict_map(doc["recomputed_scores"]["verdicts"])
    if live_v != art_v:
        return fail("live independent verdicts != artifact", {"live": live_v, "art": art_v})
    want = {
        "fused_complement": "PASS",
        "fused_worse": "FAIL",
        "fused_gaming": "VOID",
    }
    for wf, verd in want.items():
        if live_v.get(wf) != verd:
            return fail(f"{wf} live verdict {live_v.get(wf)} != {verd}")

    if not live["gaming"]["hits"]["fused_gaming"]:
        return fail("gaming detector silent")
    if not live["gaming"]["genuine_static_silent"]:
        return fail("false positive on genuine source")

    print(json.dumps({"probe": "probe1-recompute-blind", "verdicts": live_v, "pass": True}))
    print("SUCCESS:WFA-0117-probe1 blind recompute")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
