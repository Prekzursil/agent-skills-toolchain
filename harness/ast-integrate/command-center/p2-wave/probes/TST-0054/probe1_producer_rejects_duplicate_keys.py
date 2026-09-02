#!/usr/bin/env python3
"""Probe 1: producer refuses same-case duplicate keys (both states)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools" / "lib"))
sys.path.insert(0, str(REPO / "tools" / "plugin" / "tests"))

from test_duplicate_keys import (  # noqa: E402
    test_duplicate_key_is_rejected_by_the_producer,
)
import strict_json as sj  # noqa: E402


def main() -> int:
    result = test_duplicate_key_is_rejected_by_the_producer()
    fixture = (HERE / "fixtures" / "duplicate-name.json").read_text(encoding="utf-8").strip()
    if fixture != sj.DUPLICATE_KEY_FIXTURE:
        print("FAILED:TST-0054-probe1 fixture mismatch")
        return 1
    try:
        sj.loads_strict(fixture)
    except sj.DuplicateKeyError as exc:
        if exc.key != "name" or exc.first != "first" or exc.second != "second":
            print(f"FAILED:TST-0054-probe1 both-values {exc}")
            return 1
    else:
        print("FAILED:TST-0054-probe1 fixture was accepted")
        return 1
    unique = sj.dumps_from_pairs([("name", "only"), ("keep", True)], separators=(",", ":"))
    if json.loads(unique)["name"] != "only":
        print("FAILED:TST-0054-probe1 unique emit")
        return 1
    payload = {
        "probe": "probe1-producer-rejects-duplicate-keys",
        "unit_id": "TST-0054",
        "pass": True,
        "unique_silent": result["both_states"]["unique_silent"],
        "duplicate_fires": result["both_states"]["duplicate_fires"],
        "both_values": result["both_values"],
        "nested_duplicate_rejected": result["nested_duplicate_rejected"],
        "unique_emitted": result["unique_emitted"],
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:TST-0054-probe1 producer rejects duplicate keys")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
