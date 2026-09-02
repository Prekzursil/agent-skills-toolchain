#!/usr/bin/env python3
"""Probe 1: at least five randomised orders run; shuffle reorders; same seed reproduces."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from runner import NODE_IDS, run_census, run_seed, seeded_order  # noqa: E402
from suite import NODE_IDS as SUITE_IDS  # noqa: E402

ART = REPO / "command-center/receipts/TST-0127.json"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def fail(msg: str) -> int:
    print(f"FAILED:TST-0127-probe1 {msg}")
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
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return fail(f"self-declared:{st}")

    census = run_census()
    if census["n_orders"] < 5:
        return fail(f"n_orders={census['n_orders']} want>=5")
    if census["n_distinct_orders"] < 5:
        return fail(
            f"n_distinct_orders={census['n_distinct_orders']} want>=5 "
            "(orders were not actually randomised)"
        )
    if not census["controls"]["shuffle_actually_reordered"]:
        return fail("shuffle did not leave declaration order")
    declaration = tuple(SUITE_IDS)
    live_orders = [tuple(r["order"]) for r in census["runs"]]
    if all(o == declaration for o in live_orders):
        return fail("every recorded order equals declaration order")
    if len(set(live_orders)) < 5:
        return fail("fewer than five distinct live orders")

    seed0 = census["seeds"][0]
    a = run_seed(seed0)
    b = run_seed(seed0)
    if a["order"] != b["order"] or a["outcomes"] != b["outcomes"]:
        return fail(f"same-seed {seed0} reproduction diverged")
    if not census["reproduction"]["orders_equal"] or not census["reproduction"][
        "outcomes_equal"
    ]:
        return fail("census reproduction block diverged")

    want = seeded_order(list(NODE_IDS), seed0)
    if a["order"] != want:
        return fail("run_seed order != seeded_order (shuffle not a function of seed)")

    receipt_n = (doc.get("orders") or {}).get("n")
    if receipt_n != census["n_orders"]:
        return fail(f"receipt orders.n={receipt_n} live={census['n_orders']}")

    payload = {
        "probe": "probe1-five-orders",
        "n_orders": census["n_orders"],
        "n_distinct_orders": census["n_distinct_orders"],
        "seeds": census["seeds"],
        "same_seed_reproduced": True,
        "shuffle_reordered": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:TST-0127-probe1 "
        f"{census['n_orders']} orders / {census['n_distinct_orders']} distinct; "
        f"seed {seed0} reproduced"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
