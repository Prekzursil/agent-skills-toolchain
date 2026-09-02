#!/usr/bin/env python3
"""Probe 1: explicit new-versus-restated split, null labelled as null, citation fields.

Good record must pass well_formed. A mutant that drops the split object must
fail (this probe's bad state). Reverting the mutant is the good state.
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
        print("FAILED:RES-0097-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    ok, why = C.well_formed(doc)
    print(f"well_formed={ok} {why}")
    split = doc.get("new_versus_restated") or {}
    print(
        "split new={n} restated_null={r} e3={e}".format(
            n=split.get("new"),
            r=split.get("restated_null_results"),
            e=split.get("not_promoted_e3"),
        )
    )
    print(f"null_result_statement_present={bool(doc.get('null_result_statement'))}")
    if not ok:
        print("FAILED:RES-0097-probe1 well_formed")
        return 1

    mutant = copy.deepcopy(doc)
    mutant.pop("new_versus_restated", None)
    mok, mwhy = C.well_formed(mutant)
    print(f"mutant_drop_split well_formed={mok} {mwhy}")
    if mok:
        print("FAILED:RES-0097-probe1 mutant without split was accepted")
        return 1

    e3_mut = copy.deepcopy(doc)
    promoted = False
    for m in e3_mut.get("mechanisms") or []:
        if m.get("split") == "E3-NOT-PROMOTED":
            m["split"] = "NEW"
            m["evidence_tier"] = "E3"
            e3_mut.setdefault("new_versus_restated", {}).setdefault("new", [])
            if m.get("id") not in e3_mut["new_versus_restated"]["new"]:
                e3_mut["new_versus_restated"]["new"].append(m.get("id"))
            promoted = True
            break
    if not promoted:
        print("FAILED:RES-0097-probe1 no E3 row to promote")
        return 1
    eok, ewhy = C.well_formed(e3_mut)
    print(f"mutant_promote_e3 well_formed={eok} {ewhy}")
    if eok:
        print("FAILED:RES-0097-probe1 E3 promotion was accepted")
        return 1

    print("fired_on_bad=True silent_on_good=True")
    print("SUCCESS:RES-0097-probe1 new-versus-restated split and E3 gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
