#!/usr/bin/env python3
"""Probe 1: full-offline campaign - naive cache served as live vs contract label.

Rebuilds the fixture, fills both client caches online, cuts the fixture, and
re-derives the classification of what each client serves offline. Verifies the
artifact's recorded offline rows: every naive path silent-success (unlabelled
cache as live = the defect), every contract path cached-and-labelled. Control:
the same paths online must succeed. Negative control: an unlabelled-cache
detector fires on the naive state and stays silent on the contract state.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402
from common import (  # noqa: E402
    PATHS,
    REPO as R,
    SENTINEL,
    UNIT_ID,
    fail,
)

ART = R / "command-center/adversarial/ADV-0128-offline-and-partition-degrade-loudly.json"


def main() -> int:
    live = E.run_offline()
    printable = {
        "probe": "probe1-full-offline",
        "unit_id": UNIT_ID,
        "pass": bool(live["online_ok"] and live["naive_silent"] and live["contract_labelled"]),
        "online_ok": live["online_ok"],
        "naive_silent": live["naive_silent"],
        "contract_labelled": live["contract_labelled"],
        "offline_naive": live["offline_naive"],
    }
    print(json.dumps(printable, sort_keys=True))
    if not live["online_ok"]:
        return fail("online control failed: contract fetch did not succeed")
    if sorted(live["naive_silent"]) != sorted(PATHS):
        return fail(f"naive not silent-success on all four paths: {live['naive_silent']}")
    if sorted(live["contract_labelled"]) != sorted(PATHS):
        return fail(f"contract not labelled on all four paths: {live['contract_labelled']}")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("catalog sentinel absent")

    art_naive = {
        r.get("path_id"): r.get("classification")
        for r in (doc.get("offline_campaign") or {}).get("offline_naive") or []
    }
    for p in PATHS:
        if art_naive.get(p) != "silent-success":
            return fail(f"artifact offline_naive[{p}] != silent-success: {art_naive.get(p)}")
    art_contract = (doc.get("offline_campaign") or {}).get("offline_contract") or []
    bad = [r for r in art_contract if not r.get("labelled")]
    if len(art_contract) != len(PATHS) or bad:
        return fail("artifact offline_contract rows incomplete or unlabelled")
    live_rows = {r["path_id"]: r["classification"] for r in live["offline_naive"]}
    for p in PATHS:
        if live_rows[p] != art_naive.get(p):
            return fail(f"live classification drifted from artifact on {p}")

    # Negative control: unlabelled-cache detector - both states.
    nc_bad = {"from_cache": True, "labelled": False, "served": {"x": 1}}
    nc_good = {"from_cache": True, "labelled": True, "served": {"x": 1}}
    fired_bad = E.classify_naive_offline(nc_bad) == "silent-success"
    silent_good = E.classify_naive_offline(nc_good) != "silent-success"
    print(f"nc_unlabelled_cache fired_bad={fired_bad} silent_good={silent_good}")
    if not (fired_bad and silent_good):
        return fail("negative control failed both-states")

    print(f"SUCCESS:{UNIT_ID}-probe1 offline: naive silent-success x4, contract labelled x4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
