#!/usr/bin/env python3
"""Probe 1: disagreeing children reach a defined outcome, including irreducible."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from fanin import fan_in, majority_would_pass  # noqa: E402
from scenarios import (  # noqa: E402
    agreeing_pass,
    claim_without_artifact,
    completion_split,
    disagree_irreducible,
    majority_trap,
)

ART = (
    "command-center/design/council/"
    "CNL-0037-nested-subcouncils-and-council-of-councils-fan-in.md"
)


def main() -> int:
    agree = fan_in(agreeing_pass())
    split = fan_in(disagree_irreducible())
    trap_payload = majority_trap()
    trap = fan_in(trap_payload)
    incomplete = fan_in(claim_without_artifact())
    nested = fan_in(completion_split())
    print(json.dumps({
        "agree_outcome": agree["outcome"],
        "agree_complete": agree["parent_complete"],
        "split_outcome": split["outcome"],
        "split_complete": split["parent_complete"],
        "split_defined": split["fan_in_defined"],
        "split_dissent": split["forwarded_dissent_ids"],
        "trap_outcome": trap["outcome"],
        "trap_complete": trap["parent_complete"],
        "majority_would_pass": majority_would_pass(trap_payload),
        "incomplete_outcome": incomplete["outcome"],
        "completion_split_outcome": nested["outcome"],
        "completion_split_complete": nested["parent_complete"],
    }, sort_keys=True))
    if agree["outcome"] != "PASS" or agree["parent_complete"] is not True:
        print("FAILED:CNL-0037-probe1 agreeing children did not PASS")
        return 1
    if (split["outcome"] != "IRREDUCIBLE_DISAGREEMENT" or split["parent_complete"] is not False or split["fan_in_defined"] is not True):
        print("FAILED:CNL-0037-probe1 disagreeing children lacked defined irreducible outcome")
        return 1
    if "dissent-gamma-1" not in split["forwarded_dissent_ids"]:
        print("FAILED:CNL-0037-probe1 child dissent dropped at fan-in")
        return 1
    if majority_would_pass(trap_payload) is not True:
        print("FAILED:CNL-0037-probe1 majority trap fixture is not a majority PASS")
        return 1
    if trap["outcome"] == "PASS" or trap["parent_complete"] is True or trap["outcome"] != "IRREDUCIBLE_DISAGREEMENT":
        print("FAILED:CNL-0037-probe1 majority of child verdicts was accepted as PASS")
        return 1
    if incomplete["outcome"] != "INCOMPLETE" or incomplete["parent_complete"] is True:
        print("FAILED:CNL-0037-probe1 claim-without-artifact was treated as complete")
        return 1
    if nested["outcome"] != "IRREDUCIBLE_DISAGREEMENT" or nested["parent_complete"] is True:
        print("FAILED:CNL-0037-probe1 completion-split was averaged or marked complete")
        return 1
    art = REPO / ART
    if not art.is_file():
        print("FAILED:CNL-0037-probe1 design note missing")
        return 1
    if "SUCCESS:CNL-0037" not in art.read_text(encoding="utf-8"):
        print("FAILED:CNL-0037-probe1 sentinel-absent")
        return 1
    print("disagreeing-children defined=IRREDUCIBLE_DISAGREEMENT majority_suppressed=True")
    print("SUCCESS:CNL-0037-probe1 disagreeing-children defined-outcome")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
