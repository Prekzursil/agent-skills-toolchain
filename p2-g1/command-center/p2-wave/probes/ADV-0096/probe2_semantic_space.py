#!/usr/bin/env python3
"""Probe 2: second similarity space on the same planted mutant set.

Lexical = token Jaccard. Second space = canonical mechanism identity.
A class that survives both is a real gap; a class caught by only one
localises the blind space. Distinct idea must be accepted in both.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from probe_common import (  # noqa: E402
    ALL_CLASSES,
    ART,
    UNIT,
    artifact_ok_if_present,
    run_probe2,
)

OUT = HERE / "probe2-semantic-space.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    result = run_probe2()
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not result.get("pass"):
        return fail("two-space matrix or distinct/reject-all control did not complete")
    overlay = result["overlay_lexical_vs_mechanism"]
    got = [row["class"] for row in overlay]
    if got != list(ALL_CLASSES):
        return fail(f"class order {got}")
    if result["mechanism_discrimination"]["distinct_accepted"] is not True:
        return fail("mechanism space rejected the genuinely distinct idea")
    if result["lexical_discrimination"]["distinct_accepted"] is not True:
        return fail("lexical space rejected the genuinely distinct idea")
    nc = result["negative_control"]
    if not nc["fired_on_bad_state"] or not nc["silent_on_good_state"]:
        return fail("NC-REJECT-ALL-CALIBRATION both-states failed")
    # Detector must not be constant-green: mechanism space catches at least one variant.
    if result["mechanism_discrimination"]["true_positive_rejects"] < 1:
        return fail("mechanism space caught zero gaming classes")
    art_err = artifact_ok_if_present()
    if art_err:
        return fail(art_err)
    print(json.dumps(
        {
            "probe": result["probe"],
            "overlay": overlay,
            "live_vs_mechanism": result["overlay_live_vs_mechanism"],
            "gaming_survives_both_spaces": result["gaming_classes_surviving_both_spaces"],
            "caught_by_only_one": result["classes_caught_by_only_one_space"],
            "lexical_recall": result["lexical_discrimination"]["recall_on_gaming_classes"],
            "mechanism_recall": result["mechanism_discrimination"]["recall_on_gaming_classes"],
            "verdict": result["verdict"],
        },
        indent=2,
        sort_keys=True,
    ))
    print(
        "SUCCESS:ADV-0096-probe2 two-space matrix "
        f"lex_recall={result['lexical_discrimination']['recall_on_gaming_classes']} "
        f"mech_recall={result['mechanism_discrimination']['recall_on_gaming_classes']} "
        f"survive_both={result['gaming_classes_surviving_both_spaces']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
