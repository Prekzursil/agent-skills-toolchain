#!/usr/bin/env python3
"""Probe 1: known-present 'almost certain' with no anchor must fire.

Both-states: a properly banded and anchored claim must not fire.
Use-vs-mention: a quoted band name must not fire.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))

from bands import FLAG_NO_ANCHOR  # noqa: E402
from corpus import (  # noqa: E402
    both_states_claim,
    known_present_claim,
    mention_claims,
)
from scan import classify_claim  # noqa: E402


def main() -> int:
    planted = classify_claim(known_present_claim(), REPO)
    print(json.dumps({"planted": planted}, sort_keys=True))
    if FLAG_NO_ANCHOR not in planted.get("flags", []):
        print("FAILED:SYN-0014-probe1 planted almost-certain with no anchor did not fire")
        return 1
    if planted.get("band") != "almost-certain":
        print(f"FAILED:SYN-0014-probe1 planted band={planted.get('band')}")
        return 1

    good = classify_claim(both_states_claim(), REPO)
    print(json.dumps({"both_states": {"id": good["id"], "flags": good["flags"], "band": good["band"]}}))
    if good.get("flags"):
        print(f"FAILED:SYN-0014-probe1 supported claim fired flags={good.get('flags')}")
        return 1
    if good.get("band") != "almost-certain":
        print("FAILED:SYN-0014-probe1 supported claim lost its band")
        return 1

    for mention in mention_claims():
        row = classify_claim(mention, REPO)
        print(f"mention {row['id']} band={row.get('band')} flags={row.get('flags')}")
        if FLAG_NO_ANCHOR in (row.get("flags") or []):
            print(f"FAILED:SYN-0014-probe1 quoted mention fired id={row['id']}")
            return 1
        if row.get("band"):
            print(f"FAILED:SYN-0014-probe1 quoted mention mapped to band={row.get('band')}")
            return 1

    print("SUCCESS:SYN-0014-probe1 known-present fires; both-states silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
