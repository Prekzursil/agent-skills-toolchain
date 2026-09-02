#!/usr/bin/env python3
"""Probe 1: re-run the live harness and require the receipt to match."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from harness import assert_harness_healthy, run_harness  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0399.json"
SENTINEL = "SENTINEL:IMP-0399:ROUTER-MUTATIONS-SCORED"


def main() -> int:
    live = run_harness()
    try:
        assert_harness_healthy(live)
    except AssertionError as exc:
        print(f"FAILED:IMP-0399-probe1 harness unhealthy: {exc}")
        return 1
    if not ART.is_file():
        print("FAILED:IMP-0399-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        print("FAILED:IMP-0399-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:IMP-0399-probe1 self-declared {doc.get('state')}")
        return 1
    if doc.get("n_killed") != live["n_killed"]:
        print(
            f"FAILED:IMP-0399-probe1 n_killed receipt={doc.get('n_killed')} "
            f"live={live['n_killed']}"
        )
        return 1
    if doc.get("n_survived") != live["n_survived"]:
        print(
            f"FAILED:IMP-0399-probe1 n_survived receipt={doc.get('n_survived')} "
            f"live={live['n_survived']}"
        )
        return 1
    rec_obs = {
        r["mutation"]: r["observed"]
        for r in (doc.get("mutation_table") or [])
        if isinstance(r, dict)
    }
    live_obs = {r["mutation"]: r["observed"] for r in live["contracted"]}
    if rec_obs != live_obs:
        print(f"FAILED:IMP-0399-probe1 mutation table mismatch {rec_obs} vs {live_obs}")
        return 1
    if not live["harness_can_observe_red"]:
        print("FAILED:IMP-0399-probe1 control did not go RED")
        return 1
    if live["n_killed"] < 1:
        print("FAILED:IMP-0399-probe1 zero contracted kills")
        return 1
    print(
        json.dumps(
            {
                "probe": "probe1-harness-score",
                "n_killed": live["n_killed"],
                "n_survived": live["n_survived"],
                "control": live["control"]["observed"],
                "fifth": live["fifth"]["observed"],
                "clean_green": live["clean_suite_green"],
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:IMP-0399-probe1 live harness matches receipt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
