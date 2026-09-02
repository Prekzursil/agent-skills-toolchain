#!/usr/bin/env python3
"""Named probe 2: known-broken uninstall caught by the differ + second seed.

Mechanically different from probe 1: this probe's primary signal is that a
package which deletes a seeded user file produces a NON-EMPTY filesystem diff.
The reviewer path repeats healthy uninstall on seed B (not seed A).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from harness import SEED_A, SEED_B, healthy_lifecycle, known_broken_caught  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0178.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0178-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:CNF-0178" not in json.dumps(doc):
        print("FAILED:CNF-0178-probe2 sentinel absent")
        return 1

    broken_a = known_broken_caught(SEED_A)
    if not broken_a.get("caught"):
        print("FAILED:CNF-0178-probe2 differ silent on known-broken A")
        return 1
    if not broken_a["diff"]["removed"] and not broken_a["diff"]["changed"]:
        print("FAILED:CNF-0178-probe2 broken diff has no removed/changed paths")
        return 1

    # Reviewer: different seeded data set, healthy uninstall must still preserve bytes.
    healthy_b = healthy_lifecycle(SEED_B)
    if not healthy_b.get("ok") or not healthy_b.get("user_data_byte_identical_after_uninstall"):
        print("FAILED:CNF-0178-probe2 reviewer seed B uninstall mutated user data")
        return 1
    if healthy_b["behaviors"]["rollback"] != "BEHAVIOR:alpha-v1":
        print("FAILED:CNF-0178-probe2 reviewer rollback behaviour")
        return 1

    broken_b = known_broken_caught(SEED_B)
    if not broken_b.get("caught"):
        print("FAILED:CNF-0178-probe2 differ silent on known-broken B")
        return 1

    recorded = doc.get("corrected_repro") or {}
    if not recorded.get("caught"):
        print("FAILED:CNF-0178-probe2 artifact missing known-broken catch")
        return 1
    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") != "PASS":
        print("FAILED:CNF-0178-probe2 reviewer verdict")
        return 1

    payload = {
        "pass": True,
        "probe": "probe2-known-broken-differ",
        "unit_id": "CNF-0178",
        "known_broken_caught_seed_a": True,
        "known_broken_caught_seed_b": True,
        "reviewer_seed_b_intact": True,
        "broken_a_removed": broken_a["diff"]["removed"],
        "broken_b_removed": broken_b["diff"]["removed"],
        "computed_not_asserted": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "broken_caught_A=True broken_caught_B=True "
        f"removed_A={broken_a['diff']['removed']} reviewer_B_intact=True"
    )
    print("SUCCESS:CNF-0178-probe2 known-broken differ and reviewer seed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
