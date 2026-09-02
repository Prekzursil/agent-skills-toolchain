#!/usr/bin/env python3
"""Probe 2: N=1 omit control — both states (silent on honest omit, fires on fake keep)."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from engine import OMIT_ID, check_artifact, n1_can_honour  # noqa: E402

OUT = REPO / "command-center/research/RES-0059.json"


def main() -> int:
    if not OUT.is_file():
        print("FAILED:RES-0059-probe2 artifact missing")
        return 1
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    good = check_artifact(doc)
    honour = n1_can_honour(OMIT_ID)

    mutant = copy.deepcopy(doc)
    omitted = mutant.get("omitted_clauses") or []
    target = next((c for c in omitted if c.get("id") == OMIT_ID), None)
    if target is None:
        print("FAILED:RES-0059-probe2 omitted clause missing")
        return 1
    fake = copy.deepcopy(target)
    fake["honourable_at_n1"] = True
    fake.pop("must_omit_rather_than_fake", None)
    mutant["omitted_clauses"] = [c for c in omitted if c.get("id") != OMIT_ID]
    mutant.setdefault("minimal_clause_set", []).append(fake)
    bad = check_artifact(mutant)

    silent_on_good = good == []
    fires_on_bad = len(bad) > 0
    print(f"omit_id={OMIT_ID} n1_can_honour={honour}")
    print(f"good_fails={good} silent_on_good={silent_on_good}")
    print(f"mutant_fails={bad} fires_on_bad={fires_on_bad}")
    if honour:
        print("FAILED:RES-0059-probe2 engine would honour the omitted clause")
        return 1
    if not silent_on_good:
        print("FAILED:RES-0059-probe2 honest artifact did not pass")
        return 1
    if not fires_on_bad:
        print("FAILED:RES-0059-probe2 mutant that fakes the omitted clause was silent")
        return 1
    print("SUCCESS:RES-0059-probe2 N=1 omit control (both states)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
