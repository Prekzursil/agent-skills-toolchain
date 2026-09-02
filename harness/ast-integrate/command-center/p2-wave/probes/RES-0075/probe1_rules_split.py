#!/usr/bin/env python3
"""Probe 1: live artifact has an empirical/conventional split that re-derives.

Both-states: stripping the baseline from a promoting rule demotes it to E3
and removes it from empirically_supported. A silent split would pass both
states and measures nothing.
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from contract import (  # noqa: E402
    SENTINEL,
    SPLIT_PHRASE,
    can_promote,
    demote_headline_without_baseline,
)
import record as R  # noqa: E402

ART = REPO / "command-center/research/RES-0075.json"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0075-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 400:
        return fail("artifact missing or tiny")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    if SPLIT_PHRASE not in text:
        return fail("split-phrase-absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    if doc.get("unit_id") != "RES-0075":
        return fail(f"unit_id {doc.get('unit_id')!r}")

    live_split = doc.get("rules_split") or {}
    emp_ids = list(live_split.get("empirically_supported_ids") or [])
    conv_ids = list(live_split.get("conventional_ids") or [])
    if len(emp_ids) < 1 or len(conv_ids) < 1:
        return fail(f"split empty empirical={emp_ids} conventional={conv_ids}")

    derived = R.split_rules()
    if derived["empirically_supported"] != emp_ids:
        return fail(
            f"empirical ids drifted live={emp_ids} derived={derived['empirically_supported']}"
        )
    if derived["conventional"] != conv_ids:
        return fail(
            f"conventional ids drifted live={conv_ids} derived={derived['conventional']}"
        )

    for row in live_split.get("empirically_supported") or []:
        if not can_promote(row):
            return fail(f"non-promotable row in empirical list {row.get('id')}")
        if row.get("evidence_tier") not in {"E1", "E2"}:
            return fail(f"empirical row not E1/E2 {row.get('id')}")

    for row in live_split.get("conventional") or []:
        if can_promote(row) and row.get("rule_class") == "empirically-supported":
            return fail(f"promotable empirical parked as conventional {row.get('id')}")

    # Both-states: drop baseline from a live promoter; it must leave the set.
    promoter = deepcopy((live_split.get("empirically_supported") or [None])[0])
    if not isinstance(promoter, dict):
        return fail("no empirical row to mutate")
    mutant = deepcopy(promoter)
    mutant["baseline"] = ""
    mutant["effect_size"] = "Delphi is more accurate"
    mutant = demote_headline_without_baseline(mutant)
    if can_promote(mutant) or mutant.get("evidence_tier") != "E3":
        return fail("headline-without-baseline still promotable (silent in broken state)")
    if mutant.get("id") in emp_ids and can_promote(mutant):
        return fail("mutant remained in empirical set")

    green_ok = can_promote(promoter)
    red_ok = (not can_promote(mutant)) and mutant.get("evidence_tier") == "E3"
    if not (green_ok and red_ok):
        return fail(f"both-states failed green={green_ok} red={red_ok}")

    print(f"empirical={emp_ids}")
    print(f"conventional={conv_ids}")
    print(f"both_states green_promote={green_ok} red_e3={mutant.get('evidence_tier')}")
    print("SUCCESS:RES-0075-probe1 rules-split empirical-vs-conventional")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
