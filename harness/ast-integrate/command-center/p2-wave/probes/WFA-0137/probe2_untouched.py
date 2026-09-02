#!/usr/bin/env python3
"""Probe 2: decertify nothing; zero packs are touched (both-states control).

Independent of probe 1: a passing rerun on the same leaf, and a world on
which apply_regression is never called. Every pack stays SERVING and serve()
succeeds.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center" / "foundry"))

from revocation.engine import (  # noqa: E402
    CERTIFIED,
    SERVING,
    apply_regression,
    fresh_world,
    serve,
)
from revocation.graph import CONSUMERS, LEAF_ID  # noqa: E402

ART = REPO / (
    "command-center/foundry/"
    "WFA-0137-decertification-path-when-a-certified-workflow-later.json"
)


def main() -> int:
    world = fresh_world()
    before = world.snapshot_consumer_status()
    ev = apply_regression(world, LEAF_ID, passed=True, run_id="probe2-pass")
    after = world.snapshot_consumer_status()
    if ev.applied or ev.re_gated:
        print("FAILED:WFA-0137-probe2 passing rerun revoked or re-gated")
        return 1
    if before != after:
        print("FAILED:WFA-0137-probe2 consumer status changed on pass")
        return 1
    if world.records[LEAF_ID].status != CERTIFIED:
        print("FAILED:WFA-0137-probe2 leaf flipped on pass")
        return 1

    packs = [cid for cid, spec in CONSUMERS.items() if spec["kind"] == "pack"]
    touched = [p for p in packs if world.consumers[p].status != SERVING]
    if touched:
        print(f"FAILED:WFA-0137-probe2 packs touched {touched}")
        return 1
    for cid in CONSUMERS:
        sr = serve(world, cid)
        if not sr.ok:
            print(f"FAILED:WFA-0137-probe2 serve {cid} {sr.reason}")
            return 1

    idle = fresh_world()
    if idle.snapshot_consumer_status() != before:
        print("FAILED:WFA-0137-probe2 idle world drifted")
        return 1
    idle_touched = [
        cid
        for cid, spec in CONSUMERS.items()
        if spec["kind"] == "pack" and idle.consumers[cid].status != SERVING
    ]
    if idle_touched:
        print(f"FAILED:WFA-0137-probe2 idle packs not serving {idle_touched}")
        return 1

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        if "SUCCESS:WFA-0137" not in text:
            print("FAILED:WFA-0137-probe2 sentinel absent")
            return 1
        doc = json.loads(text)
        bs = doc.get("both_states") or {}
        if bs.get("decertify_nothing_zero_packs_touched") is not True:
            print("FAILED:WFA-0137-probe2 artifact both_states missing nothing-touched")
            return 1
        if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print(f"FAILED:WFA-0137-probe2 artifact state {doc.get('state')}")
            return 1

    out = {
        "probe": "probe2-untouched",
        "unit_id": "WFA-0137",
        "packs_touched": 0,
        "pass_rerun_applied": False,
        "idle_packs_serving": len(packs),
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(f"packs={len(packs)} touched=0 idle_ok=True")
    print("SUCCESS:WFA-0137-probe2 decertify nothing; zero packs touched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
