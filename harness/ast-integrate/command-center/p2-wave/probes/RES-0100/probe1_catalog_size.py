#!/usr/bin/env python3
"""Probe 1 (reviewer A, retrieval partition): catalog-size control.

Every accuracy figure must carry catalog_size. Retrieval-family pins must
resolve in the frozen snapshots. A record that drops catalog_size must go red.
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
        print("FAILED:RES-0100-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    ok, why = C.check_record(doc, REPO)
    print(f"checker_ok={ok}")
    if not ok:
        for line in why:
            print(" ", line)
        print("FAILED:RES-0100-probe1 checker red")
        return 1

    figs = [f for f in C.figures(doc) if f.get("partition") == "A"]
    want = {f["id"] for f in E.figures_for("A")}
    got = {f["id"] for f in figs}
    if want - got:
        print(f"FAILED:RES-0100-probe1 missing partition-A figures {sorted(want - got)}")
        return 1
    families = {f.get("family") for f in figs}
    if families & set(E.PART_B):
        print(f"FAILED:RES-0100-probe1 partition A leaked B families {families & set(E.PART_B)}")
        return 1
    sizes = sorted({int(f["catalog_size"]) for f in figs})
    print(f"partition_A n={len(figs)} catalog_sizes={sizes}")
    if len(sizes) < 3:
        print("FAILED:RES-0100-probe1 retrieval figures span <3 catalog sizes")
        return 1
    for fig in figs:
        if "baseline" not in fig:
            print(f"FAILED:RES-0100-probe1 {fig.get('id')} missing baseline")
            return 1

    mutant = C.mutant_strip_catalog_size(doc)
    mok, mwhy = C.check_record(mutant, REPO)
    print(f"mutant_ok={mok} mutant_head={mwhy[:2]}")
    if mok:
        print("FAILED:RES-0100-probe1 silent in both states (mutant accepted)")
        return 1

    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:RES-0100" not in text:
        print("FAILED:RES-0100-probe1 sentinel absent")
        return 1
    print("SUCCESS:RES-0100-probe1 catalog-size control + retrieval partition")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
