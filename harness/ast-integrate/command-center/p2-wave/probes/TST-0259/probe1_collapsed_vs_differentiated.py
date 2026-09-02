#!/usr/bin/env python3
"""Probe 1: planted collapsed FAIL vs planted differentiated PASS.

Both-states control for the divergence floor. A relabeled clone (role names
changed, script unchanged) must still FAIL. An inverted detector must be
wrong on both states. Two runs of each cast are byte-identical.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from divergence import floor_value, score_transcript  # noqa: E402
from simulate import canonical_bytes, run_named  # noqa: E402

UNIT = "TST-0259"


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def inverted_panel(d: float, floor: float) -> str:
    """Mutant: treat high divergence as collapse. Must be wrong on both states."""
    return "FAIL" if d >= floor else "PASS"


def main() -> int:
    floor = floor_value()
    collapsed = run_named("collapsed")
    differentiated = run_named("differentiated")
    relabeled = run_named("relabeled")
    c2 = run_named("collapsed")
    d2 = run_named("differentiated")
    if canonical_bytes(collapsed) != canonical_bytes(c2):
        return fail("collapsed transcript not deterministic")
    if canonical_bytes(differentiated) != canonical_bytes(d2):
        return fail("differentiated transcript not deterministic")

    sc = score_transcript(collapsed)
    sd = score_transcript(differentiated)
    sr = score_transcript(relabeled)

    if sc["D"] >= floor:
        return fail("collapsed D not below floor", sc)
    if sc["panel"] != "FAIL" or not sc["collapsed"]:
        return fail("collapsed panel did not FAIL", sc)
    if sd["D"] < floor:
        return fail("differentiated D not at or above floor", sd)
    if sd["panel"] != "PASS" or sd["collapsed"]:
        return fail("differentiated panel did not PASS", sd)
    if sr["D"] >= floor or sr["panel"] != "FAIL":
        return fail("relabeled clone escaped the floor (scoring labels, not behaviour)", sr)
    if abs(sr["D"] - sc["D"]) > 1e-12:
        return fail("relabel changed D; statistic is reading role strings", {"c": sc["D"], "r": sr["D"]})

    if inverted_panel(sc["D"], floor) == "FAIL":
        return fail("inverted detector accidentally correct on collapsed")
    if inverted_panel(sd["D"], floor) == "PASS":
        return fail("inverted detector accidentally correct on differentiated")
    if inverted_panel(sc["D"], floor) != "PASS" or inverted_panel(sd["D"], floor) != "FAIL":
        return fail("inverted detector did not go red on both states")

    if sc["D"] >= sd["D"]:
        return fail("collapsed D not strictly below differentiated D", {"c": sc["D"], "d": sd["D"]})

    summary = {
        "floor": floor,
        "collapsed_D": sc["D"],
        "collapsed_panel": sc["panel"],
        "differentiated_D": sd["D"],
        "differentiated_panel": sd["panel"],
        "relabeled_D": sr["D"],
        "components_collapsed": {
            "claim": sc["claim_jaccard_distance"],
            "evidence": sc["evidence_jaccard_distance"],
            "vote": sc["vote_dispersion"],
            "lexical": sc["lexical_jaccard_distance"],
        },
        "components_differentiated": {
            "claim": sd["claim_jaccard_distance"],
            "evidence": sd["evidence_jaccard_distance"],
            "vote": sd["vote_dispersion"],
            "lexical": sd["lexical_jaccard_distance"],
        },
        "inverted_detector_wrong_on_both_states": True,
        "deterministic": True,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(
        f"collapsed_D={sc['D']:.6f} differentiated_D={sd['D']:.6f} floor={floor:.6f}"
    )
    print(f"SUCCESS:{UNIT}-probe1 collapsed-FAIL differentiated-PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
