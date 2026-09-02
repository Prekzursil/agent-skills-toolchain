#!/usr/bin/env python3
"""Probe 2: mechanical independence of the replay panel + weak-entry both-states."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

REPO = HERE.parents[3]
OUT = REPO / E.OUT_REL


def main() -> int:
    gate = E.independence_review(
        E.ORIGINAL_SEATS, E.ORIGINAL_ORDER, E.REPLAY_SEATS, E.REPLAY_ORDER
    )
    if "winner" in gate or "ranking" in gate:
        print("FAILED:ARC-0076-probe2 independence gate leaked results")
        return 1
    if gate["checked_before_results"] is not True:
        print("FAILED:ARC-0076-probe2 gate did not declare checked_before_results")
        return 1
    if not gate["ok"]:
        print("FAILED:ARC-0076-probe2 replay is not mechanically different")
        print(json.dumps(gate, sort_keys=True))
        return 1
    if not gate["seat_ids_disjoint"]:
        print("FAILED:ARC-0076-probe2 seat roster is not disjoint")
        return 1
    if not gate["order_differs"]:
        print("FAILED:ARC-0076-probe2 presentation order is unchanged")
        return 1
    if not gate["vendor_multiset_differs"]:
        print("FAILED:ARC-0076-probe2 vendor mix is unchanged")
        return 1

    same = E.independence_review(
        E.ORIGINAL_SEATS, E.ORIGINAL_ORDER, E.ORIGINAL_SEATS, E.ORIGINAL_ORDER
    )
    if same["ok"]:
        print("FAILED:ARC-0076-probe2 identical configuration was accepted as independent")
        return 1

    ident = E.identical_config_is_not_a_second_signal()
    if not ident["deterministic"]:
        print("FAILED:ARC-0076-probe2 identical config was not deterministic")
        return 1

    weak = E.both_states_weak()
    if not weak["never_wins"] or weak["weak_wins"] != 0 or weak["placements"] < 6:
        print(f"FAILED:ARC-0076-probe2 weak entry control {weak}")
        return 1

    if OUT.is_file():
        doc = json.loads(OUT.read_text(encoding="utf-8"))
        indep = doc.get("independence") or {}
        if indep.get("seat_ids_disjoint") is not True:
            print("FAILED:ARC-0076-probe2 artifact independence.seat_ids_disjoint")
            return 1
        if indep.get("order_differs") is not True:
            print("FAILED:ARC-0076-probe2 artifact independence.order_differs")
            return 1
        if indep.get("checked_before_results") is not True:
            print("FAILED:ARC-0076-probe2 artifact independence.checked_before_results")
            return 1
        bs = doc.get("both_states") or {}
        if bs.get("never_wins") is not True:
            print("FAILED:ARC-0076-probe2 artifact both_states.never_wins")
            return 1
        if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print("FAILED:ARC-0076-probe2 artifact self-declared not delivering")
            return 1
        if "SUCCESS:ARC-0076" not in OUT.read_text(encoding="utf-8"):
            print("FAILED:ARC-0076-probe2 sentinel absent")
            return 1

    payload = {
        "probe": "probe2-independence-and-weak",
        "unit_id": "ARC-0076",
        "seat_ids_disjoint": True,
        "order_differs": True,
        "vendor_multiset_differs": True,
        "identical_config_rejected_as_independent": True,
        "identical_config_deterministic": True,
        "weak_never_wins": True,
        "weak_placements": weak["placements"],
        "checked_before_results": True,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:ARC-0076-probe2 disjoint seats, different order, "
        f"weak-entry never wins ({weak['placements']} placements)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
