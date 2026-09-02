#!/usr/bin/env python3
"""Probe 2: adversarial overclaim + both-states of the novelty checker.

A NEW row whose novelty text is only a both-states paraphrase must be
rejected. Relabelling a restated-null row as NEW must fire. The live
record must stay silent. Numbers in NEW rows must match the frozen snapshot.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check as C  # noqa: E402

ART = C.REPO / C.ART_REL


def main() -> int:
    if not ART.is_file():
        print("FAILED:RES-0097-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    ok, why = C.overclaim_ok(doc)
    print(f"overclaim_ok={ok} {why}")
    if not ok:
        print("FAILED:RES-0097-probe2 live record failed overclaim check")
        return 1

    # Bad state 1: dress a restated-null row as NEW with fire/silent paraphrase.
    mutant = copy.deepcopy(doc)
    rest = list((mutant.get("new_versus_restated") or {}).get("restated_null_results") or [])
    if not rest:
        print("FAILED:RES-0097-probe2 no restated row to relabel")
        return 1
    victim = rest[0]
    mutant["new_versus_restated"]["new"] = list(
        mutant["new_versus_restated"].get("new") or []
    ) + [victim]
    mutant["new_versus_restated"]["restated_null_results"] = [x for x in rest if x != victim]
    found = False
    for m in mutant["mechanisms"]:
        if m.get("id") == victim:
            m["split"] = "NEW"
            m["not_already_in_rule"] = (
                "This is new because the detector fires on bad and is silent on good "
                "in both-states known-broken and known-good fixtures."
            )
            found = True
            break
    if not found:
        print("FAILED:RES-0097-probe2 victim row missing")
        return 1
    mok, mwhy = C.overclaim_ok(mutant)
    print(f"mutant_relabel_restated_as_new overclaim_ok={mok} {mwhy}")
    if mok:
        print("FAILED:RES-0097-probe2 restated-as-NEW paraphrase was accepted")
        return 1

    # Bad state 2: strip numbers from a NEW row.
    nmut = copy.deepcopy(doc)
    stripped = False
    for m in nmut["mechanisms"]:
        if m.get("id") == "M-U-COMPARABLE":
            m["effect_size"] = "large protective association"
            stripped = True
            break
    if not stripped:
        print("FAILED:RES-0097-probe2 no Jackson row")
        return 1
    nok, nwhy = C.overclaim_ok(nmut)
    print(f"mutant_drop_jackson_number overclaim_ok={nok} {nwhy}")
    if nok:
        print("FAILED:RES-0097-probe2 headline-without-baseline-token was accepted")
        return 1

    print("fired_on_bad=True silent_on_good=True")
    print("SUCCESS:RES-0097-probe2 overclaim anchors both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
