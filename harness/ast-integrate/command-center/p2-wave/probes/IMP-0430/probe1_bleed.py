#!/usr/bin/env python3
"""Probe 1: two concurrent fixture sessions must not read each other's goal.

Session-keyed store: isolated. Project-keyed mutant: bleeds (negative control).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bleed as B  # noqa: E402

OUT = HERE / "probe1-bleed.raw.json"


def main() -> int:
    doc = B.bleed_both_states()
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    good = doc["session_keyed"]
    bad = doc["project_keyed_mutant"]
    print(
        f"session isolated={good['isolated']} bled={good['bled']} "
        f"read_a={good['read_a']!r} read_b={good['read_b']!r}"
    )
    print(
        f"project-mutant isolated={bad['isolated']} bled={bad['bled']} "
        f"read_a={bad['read_a']!r} read_b={bad['read_b']!r}"
    )
    print(f"per_store_ok={ {k: v['ok'] for k, v in doc['per_store'].items()} }")
    if not doc["pass"]:
        print("FAILED:IMP-0430-probe1 bleed test")
        return 1
    if not good["isolated"] or good["bled"]:
        print("FAILED:IMP-0430-probe1 session-keyed still bleeds")
        return 1
    if not bad["bled"] or bad["isolated"]:
        print("FAILED:IMP-0430-probe1 project-keyed mutant did not bleed")
        return 1
    print("SUCCESS:IMP-0430-probe1 concurrent sessions isolated; project mutant bleeds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
