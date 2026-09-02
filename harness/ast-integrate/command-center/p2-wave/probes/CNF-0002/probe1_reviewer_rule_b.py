#!/usr/bin/env python3
"""Probe 1: planted reviewer must be rejected by (b) and accepted by authorship-only.

If both rules agree, (b) is inert. Also re-computes the catalog author census
and checks the artifact states 0-of-0 rather than treating empty as a pass.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from corpus import catalog_author_census, domain_view  # noqa: E402
from predicate import planted_independent_case, planted_reviewer_case  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0002-independence-predicate.json"


def main() -> int:
    plant = planted_reviewer_case()
    pos = planted_independent_case()
    if not plant["pass"]:
        print("FAILED:CNF-0002-probe1 reviewer planted case did not split (a) vs (b)")
        print(json.dumps(plant, indent=2, sort_keys=True))
        return 1
    if plant["b_is_inert"]:
        print("FAILED:CNF-0002-probe1 rule (b) is inert (agrees with authorship-only)")
        return 1
    if not pos["pass"]:
        print("FAILED:CNF-0002-probe1 positive control was rejected (detector-failure)")
        print(json.dumps(pos, indent=2, sort_keys=True))
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0002-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    payload = domain_view(doc)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0002-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:CNF-0002 emitted only when" not in json.dumps(doc):
        print("FAILED:CNF-0002-probe1 catalog sentinel absent")
        return 1
    live = catalog_author_census()
    recorded = payload.get("catalog_author_census") or {}
    if recorded.get("backlog_stated") != live["backlog_stated"]:
        print(
            "FAILED:CNF-0002-probe1 backlog census drift "
            f"artifact={recorded.get('backlog_stated')} live={live['backlog_stated']}"
        )
        return 1
    if recorded.get("work_units_stated") != live["work_units_stated"]:
        print(
            "FAILED:CNF-0002-probe1 work_unit census drift "
            f"artifact={recorded.get('work_units_stated')} live={live['work_units_stated']}"
        )
        return 1
    if live["backlog_items_that_can_name_an_author"] != 0:
        print(
            "FAILED:CNF-0002-probe1 unexpected catalog authors "
            f"{live['backlog_stated']}"
        )
        return 1
    planted_art = (payload.get("planted") or {}).get("reviewer_rule_b") or {}
    if planted_art.get("pass") is not True or planted_art.get("rule_b_reject") is not True:
        print("FAILED:CNF-0002-probe1 artifact planted reviewer row missing/false")
        return 1
    print(json.dumps({"planted_reviewer": plant, "positive": pos, "census": {
        "backlog_stated": live["backlog_stated"],
        "work_units_stated": live["work_units_stated"],
    }}, sort_keys=True))
    print(
        "rule_b_reject=True authorship_only_accept="
        f"{plant['authorship_only_accept']} b_inert={plant['b_is_inert']}"
    )
    print("SUCCESS:CNF-0002-probe1 reviewer (b) vs authorship-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
