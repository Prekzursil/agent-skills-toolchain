#!/usr/bin/env python3
"""Probe 2: five identical-order repeats.

Separates order dependence from nondeterminism: the planted order-dep test
must be stable across identical-order repeats, and the planted flake must
vary. A single shuffled failure cannot distinguish the two.
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
    print(f"FAILED:AUD-0052-probe2 {msg}")
    return 1


def main() -> int:
    live = N.probe2_live()
    payload = {
        "probe": "probe2-five-repeats",
        "unit_id": C.UNIT,
        "n_repeats": live["n_repeats"],
        "identical_order": live["identical_order"],
        "get_outcomes": live["get_outcomes"],
        "flake_outcomes": live["flake_outcomes"],
        "get_stable": live["get_stable"],
        "flake_varies": live["flake_varies"],
        "flake_not_order_dep": live["flake_varies"] and live["get_stable"],
    }
    print(json.dumps(payload, sort_keys=True))
    if live["n_repeats"] != 5:
        return fail("not five repeats")
    if not live["identical_order"]:
        return fail("repeat runs were not identical order")
    if not live["get_stable"]:
        return fail("order-dep test_get was unstable on identical-order repeats")
    if live["get_outcomes"] != ["passed"] * 5:
        return fail(f"test_get identical-order outcomes {live['get_outcomes']}")
    if not live["flake_varies"]:
        return fail("planted flake did not vary; cannot separate flake from order-dep")
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    classes = doc.get("census", {}).get("classification") or {}
    if live["get_id"] not in (classes.get("order_dependent") or []):
        return fail("artifact does not list test_get as order-dependent")
    if live["flake_id"] not in (classes.get("flakes") or []):
        return fail("artifact does not list planted flake")
    if live["flake_id"] in (classes.get("order_dependent") or []):
        return fail("artifact classifies planted flake as order-dependent")
    headline = int((doc.get("summary") or {}).get("headline_count") or -1)
    live_headline = 1  # executed order-dep subjects; planted get only
    if headline != live_headline:
        return fail(
            f"headline_count {headline} != live executed order-dep count {live_headline}"
        )
    print(
        f"repeats={live['n_repeats']} identical_order={live['identical_order']} "
        f"get={live['get_outcomes']} flake={live['flake_outcomes']} "
        f"headline={headline}"
    )
    print("SUCCESS:AUD-0052-probe2 five-repeats flake-vs-order-dep falsify-headline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
