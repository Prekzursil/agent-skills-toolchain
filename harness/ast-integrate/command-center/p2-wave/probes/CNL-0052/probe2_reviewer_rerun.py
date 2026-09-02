#!/usr/bin/env python3
"""Probe 2: independent reviewer re-runs the both-states control.

Uses connected-components clustering (not the author's union-find) on the
same merge predicates. A number disagreement blocks the unit. A review
that did not execute the control is rejected.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import attack  # noqa: E402
import f01  # noqa: E402

ART = REPO / (
    "command-center/design/council/"
    "CNL-0052-adversarial-attack-on-the-unique-idea-counter-count-gaming.md"
)


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNL-0052-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))

    gamed = attack.suffix_attack(attack.SEED, attack.TARGET)
    distinct = list(attack.DISTINCT_IDEAS)

    # Independent algorithm: BFS connected components, not union-find.
    bad_cc = f01.unique_count_connected_components(gamed)
    good_cc = f01.unique_count_connected_components(distinct)
    naive_bad = f01.naive_unique(gamed)

    print(f"reviewer_algorithm=connected_components")
    print(f"executed_both_states=True")
    print(f"bad_cc_unique={bad_cc} naive_bad={naive_bad} gate_ge_100={f01.gate_unique_ge(bad_cc)}")
    print(f"good_cc_unique={good_cc} gate_ge_100={f01.gate_unique_ge(good_cc)}")

    if naive_bad < 100:
        print("FAILED:CNL-0052-probe2 named failure not visible on independent recount")
        return 1
    if bad_cc >= 100:
        print("FAILED:CNL-0052-probe2 F01 connected-components did not reject gamed corpus")
        return 1
    if good_cc != 100:
        print("FAILED:CNL-0052-probe2 F01 connected-components over-merged distinct corpus")
        return 1

    art_bad = int(doc["both_states"]["planted_bad"]["f01_unique"])
    art_good = int(doc["both_states"]["known_good"]["f01_unique"])
    if art_bad != bad_cc:
        print(f"FAILED:CNL-0052-probe2 number disagreement bad art={art_bad} cc={bad_cc}")
        return 1
    if art_good != good_cc:
        print(f"FAILED:CNL-0052-probe2 number disagreement good art={art_good} cc={good_cc}")
        return 1

    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True:
        print("FAILED:CNL-0052-probe2 reviewer.independent is not true")
        return 1
    if rev.get("executed_both_states") is not True:
        print("FAILED:CNL-0052-probe2 reviewer did not execute both-states")
        return 1
    if str(rev.get("verdict") or "").upper() != "PASS":
        print("FAILED:CNL-0052-probe2 reviewer verdict is not PASS")
        return 1

    nc = doc.get("negative_control") or {}
    if "f01_unique=1" not in str(nc.get("verbatim") or ""):
        print("FAILED:CNL-0052-probe2 negative-control verbatim missing F01 number")
        return 1

    if "SUCCESS:CNL-0052" not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNL-0052-probe2 sentinel absent")
        return 1
    print("SUCCESS:CNL-0052-probe2 independent both-states recount")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
