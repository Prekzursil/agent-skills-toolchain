#!/usr/bin/env python3
"""Probe 1: three shuffled runs with distinct recorded seeds.

Also asserts the shuffle plugin actually reorders (lab + product collectible
set) and that the identity (no-shuffle) control does not. A green result
without an order difference would mean the shuffle never happened.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import constants as C  # noqa: E402
import census as N  # noqa: E402

ART = C.REPO / C.OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0052-probe1 {msg}")
    return 1


def main() -> int:
    live = N.probe1_live()
    payload = {
        "probe": "probe1-three-seeds",
        "unit_id": C.UNIT,
        "seeds": live["seeds"],
        "lab_collected": live["lab_collected"],
        "product_collected": live["product_collected"],
        "lab_orders_differ": live["lab_orders_differ"],
        "product_orders_differ": live["product_orders_differ"],
        "identity_equal": live["identity_equal"],
        "declaration_get": live["declaration_get"],
        "shuffle_get": live["shuffle_get"],
        "get_failed_under_shuffle": "failed" in live["shuffle_get"],
    }
    print(json.dumps(payload, sort_keys=True))
    if len(set(live["seeds"])) != 3:
        return fail("seeds not distinct")
    if live["product_collected"] < C.PRODUCT_COLLECT_FLOOR:
        return fail(f"product collect {live['product_collected']} below floor")
    if not live["lab_orders_differ"]:
        return fail("lab collection order identical across seeds; shuffle never happened")
    if not live["product_orders_differ"]:
        return fail("product collection order identical across seeds; shuffle never happened")
    if not live["identity_equal"]:
        return fail("identity control reordered")
    if live["declaration_get"] != "passed":
        return fail("test_get did not pass in declaration order")
    if "failed" not in live["shuffle_get"]:
        return fail("test_get never failed under shuffle")
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != C.UNIT:
        return fail("artifact unit_id")
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"artifact state {doc.get('state')}")
    text = ART.read_text(encoding="utf-8")
    unit = N.catalog_unit()
    sentinel = str(unit.get("completion_sentinel") or "")
    if sentinel not in text:
        return fail("completion sentinel absent")
    art_seeds = doc.get("census", {}).get("seeds") or doc.get("seeds")
    if list(art_seeds) != list(live["seeds"]):
        return fail(f"artifact seeds {art_seeds} != live {live['seeds']}")
    art_od = doc.get("census", {}).get("classification", {}).get("order_dependent") or []
    if live["get_id"] not in art_od:
        return fail("artifact missing planted order-dep")
    if not doc.get("census", {}).get("lab_orders_differ"):
        return fail("artifact lab_orders_differ false")
    print(
        f"seeds={live['seeds']} lab_differ={live['lab_orders_differ']} "
        f"product_differ={live['product_orders_differ']} "
        f"identity_equal={live['identity_equal']} "
        f"get_decl={live['declaration_get']} get_shuffle={live['shuffle_get']}"
    )
    print("SUCCESS:AUD-0052-probe1 three-seeds reorder-control planted-order-dep")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
