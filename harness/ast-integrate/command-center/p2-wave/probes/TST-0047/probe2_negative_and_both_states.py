#!/usr/bin/env python3
"""Probe 2: one negative case per contract rule, plus a both-states control.

The conforming registry stays green. Each planted defect turns the suite red
on the named rule (and the suite is not a vacuous always-pass).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from engine import good_registry  # noqa: E402
from fixtures import (  # noqa: E402
    CONTRACT_RULES,
    UNPARSEABLE,
    all_conforming_sources,
    plants,
)
from suite import evaluate  # noqa: E402


def fail(msg: str, extra: object | None = None) -> int:
    print(f"FAILED:TST-0047-probe2 {msg}")
    if extra is not None:
        text = extra if isinstance(extra, str) else json.dumps(extra, indent=2, default=str)
        print(text[:4000])
    return 1


def main() -> int:
    sources = all_conforming_sources()
    garbage = REPO / UNPARSEABLE[0]
    if not garbage.is_file():
        return fail("unparseable fixture missing")

    good = evaluate(good_registry(), sources)
    if not good["ok"]:
        return fail("both-states: conforming registry was red", good["rules"])

    planted = plants()
    found_rules = {p.rule for p in planted}
    missing_rules = [r for r in CONTRACT_RULES if r not in found_rules]
    if missing_rules:
        return fail(f"no negative case for rules {missing_rules}")

    rows = []
    for plant in planted:
        extra = garbage if plant.include_unparseable else None
        report = evaluate(
            plant.registry, sources, include_unparseable=extra
        )
        rule_ok = report["rules"][plant.rule]["ok"]
        rows.append(
            {
                "plant": plant.id,
                "rule": plant.rule,
                "suite_ok": report["ok"],
                "rule_ok": rule_ok,
            }
        )
        print(
            f"plant {plant.id} rule={plant.rule} suite_ok={report['ok']} "
            f"rule_ok={rule_ok}"
        )
        if report["ok"]:
            return fail(f"plant {plant.id} stayed green", report["rules"])
        if rule_ok:
            return fail(
                f"plant {plant.id} did not turn {plant.rule} red",
                report["rules"],
            )

    good_again = evaluate(good_registry(), sources)
    if not good_again["ok"]:
        return fail("both-states: conforming registry went red after plants")

    out = {
        "probe": "probe2-negative-and-both-states",
        "unit_id": "TST-0047",
        "good_green": True,
        "good_green_after_plants": True,
        "plants": rows,
        "rules_with_negative": sorted(found_rules),
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"plants={len(rows)} good_green=True good_after=True "
        f"rules={sorted(found_rules)}"
    )
    print("SUCCESS:TST-0047-probe2 negative cases and both-states control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
