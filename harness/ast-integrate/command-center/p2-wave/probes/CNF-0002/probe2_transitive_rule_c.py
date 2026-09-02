#!/usr/bin/env python3
"""Probe 2: planted dependency-author must be rejected by (c) while (a) lets through.

Re-derives that verdict from the fixture BEFORE reading the artifact conclusion.
Then checks the live corpus measurement, including any 0-of-0, is stated.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from corpus import domain_view, measure_real_corpus  # noqa: E402
from predicate import (  # noqa: E402
    evaluate_confirmation,
    load_planted,
    planted_ancestor_case,
)

ART = REPO / "command-center/confirmation/CNF-0002-independence-predicate.json"


def main() -> int:
    fixture = load_planted("planted_ancestor.json")
    derived = evaluate_confirmation(
        fixture["confirmation"],
        fixture["implementation"],
        fixture.get("ancestors") or [],
    )
    if not derived.c_rejects_a_lets_through or derived.rule_a_reject or derived.independent:
        print("FAILED:CNF-0002-probe2 re-derived verdict is not (c) minus (a)")
        print(json.dumps({
            "independent": derived.independent,
            "rule_a_reject": derived.rule_a_reject,
            "rule_c_reject": derived.rule_c_reject,
            "c_rejects_a_lets_through": derived.c_rejects_a_lets_through,
        }, indent=2, sort_keys=True))
        return 1
    plant = planted_ancestor_case()
    if not plant["pass"]:
        print("FAILED:CNF-0002-probe2 planted ancestor helper disagreed with re-derive")
        return 1

    live = measure_real_corpus()
    if live["empty_set_read_as_pass"] is not False:
        print("FAILED:CNF-0002-probe2 empty corpus was treated as a pass")
        return 1
    if live["size"] == 0:
        if live["rule_a"]["stated"] != "0 of 0" or live["rule_c"]["stated"] != "0 of 0":
            print("FAILED:CNF-0002-probe2 empty corpus did not state 0 of 0")
            print(json.dumps(live["rule_a"], sort_keys=True))
            return 1
        if live["c_rejects_a_lets_through"]["stated"] != "0 of 0":
            print("FAILED:CNF-0002-probe2 c-minus-a did not state 0 of 0")
            return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0002-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    payload = domain_view(doc)
    if payload.get("empty_set_read_as_pass") is not False:
        print("FAILED:CNF-0002-probe2 artifact empty_set_read_as_pass is not false")
        return 1
    if (payload.get("rule_a") or {}).get("stated") != live["rule_a"]["stated"]:
        print(
            "FAILED:CNF-0002-probe2 rule_a drift "
            f"artifact={payload.get('rule_a')} live={live['rule_a']}"
        )
        return 1
    if (payload.get("rule_c") or {}).get("stated") != live["rule_c"]["stated"]:
        print(
            "FAILED:CNF-0002-probe2 rule_c drift "
            f"artifact={payload.get('rule_c')} live={live['rule_c']}"
        )
        return 1
    planted_art = (payload.get("planted") or {}).get("ancestor_rule_c") or {}
    if planted_art.get("c_rejects_a_lets_through") is not True:
        print("FAILED:CNF-0002-probe2 artifact did not record (c) minus (a)")
        return 1
    if "SUCCESS:CNF-0002 emitted only when" not in json.dumps(doc):
        print("FAILED:CNF-0002-probe2 catalog sentinel absent")
        return 1

    print(json.dumps({
        "rederived_before_artifact": {
            "c_rejects_a_lets_through": derived.c_rejects_a_lets_through,
            "independent": derived.independent,
            "rule_a_reject": derived.rule_a_reject,
            "rule_c_reject": derived.rule_c_reject,
        },
        "corpus": {
            "rule_a": live["rule_a"]["stated"],
            "rule_c": live["rule_c"]["stated"],
            "c_minus_a": live["c_rejects_a_lets_through"]["stated"],
            "size": live["size"],
            "empty_set_read_as_pass": live["empty_set_read_as_pass"],
        },
    }, sort_keys=True))
    print("SUCCESS:CNF-0002-probe2 transitive (c) vs direct (a); 0-of-0 stated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
