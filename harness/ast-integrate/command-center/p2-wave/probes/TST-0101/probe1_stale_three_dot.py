#!/usr/bin/env python3
"""Probe 1: stale mass-deletion both-states, and three-dot vs two-dot control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import tests as T  # noqa: E402

REPO = HERE.parents[3]
ART = REPO / "command-center/receipts/TST-0101.json"


def main() -> int:
    a = T.test_gate_fails_on_a_stale_branch_proposing_mass_deletion()
    b = T.test_gate_uses_three_dot_not_two_dot()
    if a.get("result") != "PASS" or b.get("result") != "PASS":
        print("FAILED:TST-0101-probe1 catalog tests")
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:TST-0101-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0101" not in text:
        print("FAILED:TST-0101-probe1 sentinel-absent")
        return 1
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:TST-0101-probe1 self-declared:{doc.get('state')}")
        return 1
    evidence = doc.get("evidence") or {}
    three = (evidence.get("three_dot") or {})
    two = (evidence.get("two_dot") or {})
    if "..." not in str(three.get("range") or ""):
        print("FAILED:TST-0101-probe1 artifact three-dot range missing")
        return 1
    if str(two.get("range") or "").count(".") < 2:
        print("FAILED:TST-0101-probe1 artifact two-dot range missing")
        return 1
    if evidence.get("surfaces_differ") is not True:
        print("FAILED:TST-0101-probe1 artifact did not record surfaces_differ")
        return 1
    both = doc.get("both_states") or {}
    if not both.get("stale_mass_deletion", {}).get("blocked"):
        print("FAILED:TST-0101-probe1 artifact stale state not blocked")
        return 1
    if both.get("freshly_based", {}).get("blocked") is not False:
        print("FAILED:TST-0101-probe1 artifact fresh state not silent")
        return 1
    print(
        json.dumps(
            {
                "stale_blocked": True,
                "fresh_silent": True,
                "three_dot_range": three.get("range"),
                "two_dot_range": two.get("range"),
                "surfaces_differ": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:TST-0101-probe1 stale-mass-deletion three-dot-not-two-dot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
