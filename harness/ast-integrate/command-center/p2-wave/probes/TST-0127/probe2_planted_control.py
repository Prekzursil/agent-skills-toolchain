#!/usr/bin/env python3
"""Probe 2: planted order-dependence is detected and named with its shared state.

Also: independents stay invariant, always-fail is not called order-dependent,
and same-order repeats (TST-0032 shape) stay deterministic.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from runner import flake_repeats, run_census  # noqa: E402
from suite import (  # noqa: E402
    ALWAYS_FAIL,
    INDEPENDENTS_PASS,
    PLANT_CHANNELS,
    PLANTED_READERS,
    PLANTED_WRITERS,
)

ART = REPO / "command-center/receipts/TST-0127.json"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def fail(msg: str) -> int:
    print(f"FAILED:TST-0127-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "TST-0127":
        return fail(f"unit_id={doc.get('unit_id')}")
    if "SUCCESS:TST-0127" not in text:
        return fail("sentinel-absent")
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        return fail(f"self-declared:{doc.get('state')}")

    census = run_census()
    by_id = {t["id"]: t for t in census["tests"]}
    od_ids = {t["id"] for t in census["order_dependent"]}

    for nid in PLANTED_READERS:
        row = by_id.get(nid)
        if row is None:
            return fail(f"missing test {nid}")
        if row["classification"] != "ORDER_DEPENDENT":
            return fail(f"{nid} classification={row['classification']}")
        shared = row["suspected_shared_state"] or {}
        writer = PLANT_CHANNELS[nid]["writer"]
        if writer not in (shared.get("pairwise_suspects") or []):
            return fail(f"{nid} pairwise_suspects={shared.get('pairwise_suspects')} want {writer}")
        if shared.get("known_writer") != writer:
            return fail(f"{nid} known_writer={shared.get('known_writer')}")
        if not shared.get("channel") or not shared.get("kind"):
            return fail(f"{nid} unnamed shared state: {shared}")
        if nid not in od_ids:
            return fail(f"{nid} absent from order_dependent list")

    for nid in INDEPENDENTS_PASS + PLANTED_WRITERS:
        row = by_id[nid]
        if not row["invariant"] or row["classification"] != "INVARIANT":
            return fail(f"{nid} should be invariant, got {row['classification']}")
        if row["unique_outcomes"] != ["PASS"]:
            return fail(f"{nid} unique={row['unique_outcomes']} want ['PASS']")

    broken = by_id[ALWAYS_FAIL]
    if not broken["invariant"] or broken["unique_outcomes"] != ["FAIL"]:
        return fail(f"always-fail misclassified: {broken}")
    if broken["classification"] == "ORDER_DEPENDENT":
        return fail("always-fail was labelled ORDER_DEPENDENT")

    flake = flake_repeats(census["runs"][0]["order"], n=5)
    if flake["classification"] != "DETERMINISTIC-AT-FIXED-ORDER":
        return fail(f"same-order repeats={flake['classification']}")

    named = doc.get("order_dependent_named") or []
    named_ids = {n.get("test_id") for n in named}
    if set(PLANTED_READERS) - named_ids:
        return fail(f"receipt did not name planted readers: {named}")
    for item in named:
        if item.get("test_id") in PLANTED_READERS and not item.get("suspected_shared_state"):
            return fail(f"receipt unnamed shared state for {item}")

    payload = {
        "probe": "probe2-planted-control",
        "order_dependent": sorted(od_ids),
        "planted_readers_detected": list(PLANTED_READERS),
        "always_fail_invariant": True,
        "same_order_deterministic": True,
        "independents_invariant": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:TST-0127-probe2 planted readers named with shared state; "
        "always-fail not order-dependent; same-order deterministic"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
