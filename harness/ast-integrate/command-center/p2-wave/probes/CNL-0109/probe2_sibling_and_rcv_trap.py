#!/usr/bin/env python3
"""Probe 2: nearest-sibling differential, name-only clone, IRV trap."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import family as F  # noqa: E402
import tabulate as T  # noqa: E402

ART = REPO / "command-center/design/council/CNL-0109-strategy-and-constrained-prioritisation-family.md"


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNL-0109-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    presets = doc.get("presets") or []
    if len(presets) < 2:
        print("FAILED:CNL-0109-probe2 need two family members")
        return 1

    catalog = F.load_sibling_catalog(REPO)
    siblings = catalog["presets"]
    print(
        f"library present={catalog['library_present']} source={catalog['source']} "
        f"siblings={len(siblings)}"
    )
    if not siblings:
        print("FAILED:CNL-0109-probe2 no named sibling")
        return 1

    for preset in presets:
        live = F.nearest_sibling(preset, siblings)
        print(
            f"nearest of {preset['id']} -> {live['named']} "
            f"dist={live['profile_distance']} axes={live['differing_axes']}"
        )
        if live["profile_distance"] < 2:
            print("FAILED:CNL-0109-probe2 differential is only the name")
            return 1
        recorded = doc.get("nearest_sibling") or {}
        if recorded.get("named") != live["named"] and preset is presets[0]:
            print(
                f"FAILED:CNL-0109-probe2 artifact sibling {recorded.get('named')} "
                f"!= live {live['named']}"
            )
            return 1
        if preset is presets[0]:
            if int(recorded.get("profile_distance") or 0) != live["profile_distance"]:
                print("FAILED:CNL-0109-probe2 profile_distance mismatch")
                return 1
            if sorted(recorded.get("differing_axes") or []) != sorted(live["differing_axes"]):
                print("FAILED:CNL-0109-probe2 differing_axes mismatch")
                return 1

    clone = F.name_only_clone(
        presets[0], presets[0]["id"] + ".NAME-ONLY"
    )
    clone_caught = False
    try:
        F.nearest_sibling(clone, [presets[0]])
    except ValueError as exc:
        clone_caught = True
        print("name_only_clone rejected:", exc)
    if not clone_caught:
        print("FAILED:CNL-0109-probe2 name-only clone accepted")
        return 1

    trap = T.trap_fixture()
    print(
        f"irv_winner={trap['irv_winner']} irv_value={trap['irv_portfolio']['value']} "
        f"knapsack={trap['knapsack']['set']} knapsack_value={trap['knapsack']['value']} "
        f"trap_fires={trap['trap_fires']}"
    )
    if not trap["trap_fires"]:
        print("FAILED:CNL-0109-probe2 IRV trap did not fire")
        return 1
    rec = doc.get("rcv_trap") or {}
    if rec.get("irv_winner") != trap["irv_winner"]:
        print("FAILED:CNL-0109-probe2 irv_winner mismatch")
        return 1
    if rec.get("knapsack_value") != trap["knapsack"]["value"]:
        print("FAILED:CNL-0109-probe2 knapsack_value mismatch")
        return 1
    if rec.get("irv_portfolio_value") != trap["irv_portfolio"]["value"]:
        print("FAILED:CNL-0109-probe2 irv_portfolio_value mismatch")
        return 1
    if trap["knapsack"]["value"] <= trap["irv_portfolio"]["value"]:
        print("FAILED:CNL-0109-probe2 knapsack did not beat IRV portfolio")
        return 1

    print(
        f"SUCCESS:CNL-0109-probe2 sibling={siblings[0]['id']} "
        f"trap irv={trap['irv_winner']} knapsack={trap['knapsack']['set']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
