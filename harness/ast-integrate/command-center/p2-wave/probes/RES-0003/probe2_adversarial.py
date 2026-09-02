#!/usr/bin/env python3
"""Probe 2: known-good / known-broken both-states plus adversarial fixtures.

Hedge words are a tell, not the definition:
  * E1 padded with hedges must stay E1
  * confident E4 inference must stay E4
The hedge-only detector is the known-broken detector: it fails both.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from fixtures import (  # noqa: E402
    ADV_CONFIDENT_E4,
    ADV_HEDGE_E1,
    KNOWN_BROKEN,
    KNOWN_GOOD,
    both_states_pair,
)
from grader import grade, hedge_only_grade  # noqa: E402

ART = REPO / "command-center/research/RES-0003.json"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0003-probe2 {msg}")
    return 1


def main() -> int:
    g_good = grade(KNOWN_GOOD)
    g_broken = grade(KNOWN_BROKEN)
    print(json.dumps(
        {
            "known_good": {"id": KNOWN_GOOD["id"], "expect": KNOWN_GOOD["expect"], "got": g_good},
            "known_broken": {
                "id": KNOWN_BROKEN["id"],
                "expect": KNOWN_BROKEN["expect"],
                "got": g_broken,
            },
        },
        sort_keys=True,
    ))
    if g_good != KNOWN_GOOD["expect"]:
        return fail(f"known-good got {g_good} want {KNOWN_GOOD['expect']}")
    if g_broken != KNOWN_BROKEN["expect"]:
        return fail(f"known-broken got {g_broken} want {KNOWN_BROKEN['expect']}")
    if g_good == g_broken:
        return fail("detector silent in both states (good==broken)")

    live_good, live_mutant = both_states_pair()
    a, b = grade(live_good), grade(live_mutant)
    print(f"both_states good={a} mutant={b}")
    if a != "E1" or b != "E4":
        return fail(f"both-states pair good={a} mutant={b}")
    if a == b:
        return fail("mutation silent")

    hedge = grade(ADV_HEDGE_E1)
    conf = grade(ADV_CONFIDENT_E4)
    print(f"adversarial hedge_padded_E1={hedge} confident_E4={conf}")
    if hedge != "E1":
        return fail(f"hedge-padded E1 demoted to {hedge}")
    if conf != "E4":
        return fail(f"confident E4 missed, got {conf}")

    h_hedge = hedge_only_grade(ADV_HEDGE_E1)
    h_conf = hedge_only_grade(ADV_CONFIDENT_E4)
    print(f"broken_detector hedge_only padded={h_hedge} confident={h_conf}")
    if h_hedge != "E4" or h_conf != "E1":
        return fail("hedge-only detector did not make the known errors")
    if h_hedge == hedge and h_conf == conf:
        return fail("live grader indistinguishable from hedge-only detector")

    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    fx = doc.get("fixture_runs") or {}
    if fx.get("known_good_output") != "E1":
        return fail("artifact known_good_output")
    if fx.get("known_broken_output") != "E4":
        return fail("artifact known_broken_output")
    if fx.get("hedge_padded_e1_output") != "E1":
        return fail("artifact hedge_padded")
    if fx.get("confident_e4_output") != "E4":
        return fail("artifact confident_e4")
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    print("SUCCESS:RES-0003-probe2 both-states and adversarial fixtures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
