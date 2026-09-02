#!/usr/bin/env python3
"""Probe 1: both-states control — IGNORED only after a positive-control change."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check as K  # noqa: E402
import common as C  # noqa: E402

ART = C.REPO / C.ART_REL


def main() -> int:
    if not ART.is_file():
        print("FAILED:RES-0169-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    index = C.load_index()
    ok, why = K.well_formed(doc, index)
    print(f"well_formed={ok} {why}")
    if not ok:
        print("FAILED:RES-0169-probe1 well_formed")
        return 1

    lang = C.pair_stats(index, "wikipedia", "language")
    dom = C.pair_stats(index, "wikipedia", "domain")
    pc = C.positive_control_changed(index, "wikipedia")
    emu = C.emulate_wikipedia_domain(index)
    print(
        "wikipedia language changed={lc} jac={lj} domain changed={dc} jac={dj} "
        "pc={pc} emulation_changed={ec} n={n}->{m}".format(
            lc=lang["strongly_changed"],
            lj=lang["id_jaccard"],
            dc=dom["strongly_changed"],
            dj=dom["id_jaccard"],
            pc=pc,
            ec=emu["changed"],
            n=emu["n_unfiltered"],
            m=emu["n_after"],
        )
    )
    if not lang["strongly_changed"] or not pc:
        print("FAILED:RES-0169-probe1 positive control did not change")
        return 1
    if dom["strongly_changed"]:
        print("FAILED:RES-0169-probe1 domain pair strongly changed; cannot label IGNORED")
        return 1
    if not emu["changed"] or emu["n_after"] != 0:
        print("FAILED:RES-0169-probe1 client emulation did not empty arxiv.org set")
        return 1

    mutant = copy.deepcopy(doc)
    for cell in mutant["cells"]:
        if cell.get("backend") == "wikipedia" and cell.get("filter") == "domain":
            cell["verdict"] = "NATIVE"
            cell["differential"]["strongly_changed"] = True
            break
    mok, mwhy = K.well_formed(mutant, index)
    print(f"mutant_ignored_as_native ok={mok} {mwhy}")
    if mok:
        print("FAILED:RES-0169-probe1 NATIVE-without-change mutant was accepted")
        return 1

    mutant2 = copy.deepcopy(doc)
    for cell in mutant2["cells"]:
        if cell.get("backend") == "wikipedia" and cell.get("filter") == "domain":
            cell["differential"]["positive_control_changed"] = False
            break
    else:
        print("FAILED:RES-0169-probe1 no wikipedia/domain cell")
        return 1
    m2ok, m2why = K.well_formed(mutant2, index)
    print(f"mutant_ignored_without_pc ok={m2ok} {m2why}")
    if m2ok:
        print("FAILED:RES-0169-probe1 IGNORED-without-positive-control mutant was accepted")
        return 1

    print("fired_on_bad=True silent_on_good=True")
    print("SUCCESS:RES-0169-probe1 both-states IGNORED requires a changing positive control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
