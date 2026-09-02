#!/usr/bin/env python3
"""Probe 2 (reviewer B, disjoint sources): adopt-native corroborate-or-refute.

Partition B is ToolkenGPT / AnyTool / HuggingGPT / native PD only.
The inherited adopt-native grade must carry an explicit REFUTE or CORROBORATE
with deciding evidence and a named settling comparison.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import check as C  # noqa: E402
import evidence as E  # noqa: E402

ART = REPO / "command-center/research/RES-0100.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:RES-0100-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    ok, why = C.check_record(doc, REPO)
    print(f"checker_ok={ok}")
    if not ok:
        for line in why:
            print(" ", line)
        print("FAILED:RES-0100-probe2 checker red")
        return 1

    figs = [f for f in C.figures(doc) if f.get("partition") == "B"]
    want = {f["id"] for f in E.figures_for("B")}
    got = {f["id"] for f in figs}
    if want - got:
        print(f"FAILED:RES-0100-probe2 missing partition-B figures {sorted(want - got)}")
        return 1
    families = {f.get("family") for f in figs}
    if families & set(E.PART_A):
        print(f"FAILED:RES-0100-probe2 partition B leaked A families {families & set(E.PART_A)}")
        return 1

    reviewers = doc.get("reviewers") or []
    if len(reviewers) < 2:
        print("FAILED:RES-0100-probe2 need two partitioned reviewers")
        return 1
    a = set(reviewers[0].get("source_partition") or [])
    b = set(reviewers[1].get("source_partition") or [])
    if a & b:
        print(f"FAILED:RES-0100-probe2 overlapping partitions {sorted(a & b)}")
        return 1
    print(f"partitions A={sorted(a)} B={sorted(b)}")

    verdict = doc.get("adopt_native_verdict") or {}
    v = str(verdict.get("verdict") or "").upper()
    print(f"adopt_native_verdict={v}")
    if v not in C.VERDICTS:
        print("FAILED:RES-0100-probe2 corroborate-or-refute missing")
        return 1
    if "RES-0101" not in str(verdict.get("settling_comparison") or ""):
        print("FAILED:RES-0100-probe2 settling comparison does not name RES-0101")
        return 1
    if not verdict.get("deciding_evidence") and not verdict.get("deciding_figure_ids"):
        print("FAILED:RES-0100-probe2 deciding evidence missing")
        return 1

    # Rule-based router must not be promoted from a planning number.
    for fig in figs:
        if fig.get("family") == "hugginggpt" and fig.get("can_promote") is True:
            print("FAILED:RES-0100-probe2 HuggingGPT planning Acc was promoted")
            return 1
        if fig.get("family") == "native-pd" and fig.get("can_promote") is True:
            print("FAILED:RES-0100-probe2 unmeasured native PD was promoted")
            return 1

    mutant = C.mutant_strip_catalog_size(doc)
    mok, mwhy = C.check_record(mutant, REPO)
    print(f"mutant_ok={mok} mutant_head={mwhy[:2]}")
    if mok:
        print("FAILED:RES-0100-probe2 silent in both states (mutant accepted)")
        return 1

    claims = {c.get("claim_id"): c for c in (doc.get("claims") or []) if isinstance(c, dict)}
    native = claims.get("RES-0100-C-ADOPT-NATIVE") or {}
    if str(native.get("evidence_tier") or "") != "E3":
        print("FAILED:RES-0100-probe2 inherited adopt-native must stay E3")
        return 1

    if "SUCCESS:RES-0100" not in ART.read_text(encoding="utf-8"):
        print("FAILED:RES-0100-probe2 sentinel absent")
        return 1
    print("SUCCESS:RES-0100-probe2 adopt-native refute + disjoint partition B")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
