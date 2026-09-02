#!/usr/bin/env python3
"""Probe 1: 40-pair truth table, algorithm vs hand vs independent recompute."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "command-center" / "leases"))

import independent_overlap as ind  # noqa: E402
import overlap  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0411.json"
SENTINEL = "SENTINEL:IMP-0411:OVERLAP-ALGORITHM-EXACT"


def main() -> int:
    pairs = overlap.load_corpus()
    if len(pairs) != 40:
        print(f"FAILED:IMP-0411-probe1 corpus_n={len(pairs)} want=40")
        return 1
    classes = Counter(str(p.get("class")) for p in pairs)
    if classes["case-only-windows"] != 10:
        print(f"FAILED:IMP-0411-probe1 case-only={classes['case-only-windows']} want=10")
        return 1
    if classes["glob-versus-literal"] != 8:
        print(f"FAILED:IMP-0411-probe1 glob-vs-lit={classes['glob-versus-literal']} want=8")
        return 1

    rows = []
    disagree = []
    for p in pairs:
        algo = overlap.evaluate_pair(p)
        indep = overlap.evaluate_pair(p, overlap_fn=ind.pathsets_overlap)
        row = {
            "id": p["id"],
            "class": p["class"],
            "a": p["a"],
            "b": p["b"],
            "os_family": p["os_family"],
            "algorithm_overlap": algo["algorithm_overlap"],
            "independent_overlap": indep["algorithm_overlap"],
            "hand_overlap": p["hand_overlap"],
            "reason": p["reason"],
        }
        rows.append(row)
        if not (
            row["algorithm_overlap"] is row["hand_overlap"]
            and row["independent_overlap"] is row["hand_overlap"]
        ):
            disagree.append(row)

    payload = {
        "corpus_n": len(pairs),
        "case_only_windows": classes["case-only-windows"],
        "glob_versus_literal": classes["glob-versus-literal"],
        "algorithm_agreements": len(pairs) - len(disagree),
        "independent_agreements": sum(
            1 for r in rows if r["independent_overlap"] is r["hand_overlap"]
        ),
        "disagree": disagree,
        "computed_not_asserted": True,
        "method": "set-membership overlap.py vs regex/witness independent_overlap.py vs hand",
    }
    print(json.dumps(payload, indent=2))
    if disagree:
        print(f"FAILED:IMP-0411-probe1 disagreements={len(disagree)}")
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:IMP-0411-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:IMP-0411-probe1 sentinel absent")
        return 1
    doc = json.loads(text)
    if doc.get("unit_id") != "IMP-0411":
        print("FAILED:IMP-0411-probe1 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:IMP-0411-probe1 self-declared", doc.get("state"))
        return 1
    table = doc.get("truth_table") or []
    if len(table) != 40:
        print(f"FAILED:IMP-0411-probe1 receipt table n={len(table)} want=40")
        return 1
    by_id = {r["id"]: r for r in rows}
    for rec in table:
        live = by_id.get(rec.get("id"))
        if live is None:
            print("FAILED:IMP-0411-probe1 unknown table id", rec.get("id"))
            return 1
        if rec.get("algorithm_overlap") is not live["algorithm_overlap"]:
            print("FAILED:IMP-0411-probe1 receipt/live mismatch", rec.get("id"))
            return 1
        if rec.get("hand_overlap") is not live["hand_overlap"]:
            print("FAILED:IMP-0411-probe1 receipt hand mismatch", rec.get("id"))
            return 1

    print(
        f"corpus=40 case_only=10 glob_vs_lit=8 "
        f"algo_agree=40 independent_agree=40"
    )
    print("SUCCESS:IMP-0411-probe1 truth table algorithm=hand=independent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
