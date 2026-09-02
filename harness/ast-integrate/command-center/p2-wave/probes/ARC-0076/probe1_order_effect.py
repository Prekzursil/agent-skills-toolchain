#!/usr/bin/env python3
"""Probe 1: order-effect control + published stability metric."""
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
    orders = E.unique_orders(24)
    if len(set(orders)) != 24:
        print("FAILED:ARC-0076-probe1 expected 24 distinct orders")
        return 1
    if orders[0] != E.ORIGINAL_ORDER:
        print("FAILED:ARC-0076-probe1 first order must be the original presentation")
        return 1
    fx = E.order_effect_control(24)
    if not fx["orders_all_distinct"] or fx["n_permutations"] != 24:
        print("FAILED:ARC-0076-probe1 permutations")
        return 1
    if not fx["position_bias_measured"]:
        print("FAILED:ARC-0076-probe1 position bias was not measured")
        return 1
    if len(fx["slot_means"]) != 9:
        print("FAILED:ARC-0076-probe1 slot_means length")
        return 1
    # Primacy term is declared on at least one original seat; slot 0 must
    # outscore slot 8 when the same panel sees permuted orders.
    if fx["primacy_effect"] <= 0:
        print(
            "FAILED:ARC-0076-probe1 primacy_effect "
            f"{fx['primacy_effect']} was not positive; order control is vacuous"
        )
        return 1
    replays = E.run_replays()
    n = replays["n_replays"]
    p = replays["probability_same_winner"]
    if n < 2 or not (0.0 <= p <= 1.0):
        print(f"FAILED:ARC-0076-probe1 stability n={n} p={p}")
        return 1
    if not replays["identical_configuration_excluded"]:
        print("FAILED:ARC-0076-probe1 identical configuration was counted")
        return 1
    if OUT.is_file():
        doc = json.loads(OUT.read_text(encoding="utf-8"))
        art_p = doc["stability"]["probability_same_winner"]
        art_n = doc["stability"]["n_replays"]
        art_pe = doc["order_effect"]["primacy_effect"]
        if art_n != n or abs(art_p - p) > 1e-9:
            print(f"FAILED:ARC-0076-probe1 artifact stability mismatch n={art_n}/{n} p={art_p}/{p}")
            return 1
        if abs(art_pe - fx["primacy_effect"]) > 1e-9:
            print("FAILED:ARC-0076-probe1 artifact primacy_effect mismatch")
            return 1
        if doc["stability"]["identical_configuration_excluded"] is not True:
            print("FAILED:ARC-0076-probe1 artifact counted identical config")
            return 1
    payload = {
        "probe": "probe1-order-effect",
        "unit_id": "ARC-0076",
        "n_permutations": fx["n_permutations"],
        "primacy_effect": fx["primacy_effect"],
        "slot_means": fx["slot_means"],
        "order_winner_set": fx["winner_set"],
        "n_replays": n,
        "probability_same_winner": p,
        "identical_configuration_excluded": True,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:ARC-0076-probe1 order-effect control and stability metric "
        f"p={p} n={n} primacy_effect={fx['primacy_effect']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
