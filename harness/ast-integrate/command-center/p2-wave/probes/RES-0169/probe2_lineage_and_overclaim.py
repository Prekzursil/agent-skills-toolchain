#!/usr/bin/env python3
"""Probe 2: lineage sha match, two signals, docs-only cannot be NATIVE."""
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
    if not ART.is_file() or not (C.REPO / C.SCHEMA_REL).is_file():
        print("FAILED:RES-0169-probe2 artifact or schema missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    index = C.load_index()
    ok, why = K.well_formed(doc, index)
    print(f"lineage_ok={ok} {why}")
    if not ok:
        print("FAILED:RES-0169-probe2 live artifact failed lineage/overclaim")
        return 1

    mutant = copy.deepcopy(doc)
    mutant["cells"][0]["signals"][0].pop("sha256", None)
    mok, mwhy = K.well_formed(mutant, index)
    print(f"mutant_drop_sha ok={mok} {mwhy}")
    if mok:
        print("FAILED:RES-0169-probe2 missing sha256 was accepted")
        return 1

    mutant2 = copy.deepcopy(doc)
    mutant2["claims"] = mutant2["claims"][:1]
    mutant2["claims"][0]["signals"] = mutant2["claims"][0]["signals"][:1]
    m2ok, m2why = K.well_formed(mutant2, index)
    print(f"mutant_single_signal ok={m2ok} {m2why}")
    if m2ok:
        print("FAILED:RES-0169-probe2 single-signal mutant was accepted")
        return 1

    mutant3 = copy.deepcopy(doc)
    promoted = False
    for cell in mutant3["cells"]:
        if cell.get("backend") == "tavily" and cell.get("filter") == "domain":
            cell["verdict"] = "NATIVE"
            cell["evidence_basis"] = "docs-only"
            cell["differential"]["strongly_changed"] = True
            promoted = True
            break
    if not promoted:
        print("FAILED:RES-0169-probe2 no tavily/domain cell")
        return 1
    m3ok, m3why = K.well_formed(mutant3, index)
    print(f"mutant_docs_as_native ok={m3ok} {m3why}")
    if m3ok:
        print("FAILED:RES-0169-probe2 docs-only NATIVE mutant was accepted")
        return 1

    print("SUCCESS:RES-0169-probe2 lineage two-signal docs-only-not-native mutants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
