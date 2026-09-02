#!/usr/bin/env python3
"""Probe 1: forward omitted-dissent accounting.

Enumerates contradiction pairs in the raw inputs and classifies each
against the synthesis as represented / resolved-with-reason / silently-dropped.
Mechanically different from probe 2, which starts from synthesis agreement claims.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import account as A  # noqa: E402

ART = REPO / A.OUT_REL
SENTINEL = A.COMPLETION_SENTINEL


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:ADV-0109-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:ADV-0109-probe1 unparseable {exc}")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ADV-0109-probe1 self-declared {doc.get('state')}")
        return 1
    if SENTINEL not in text:
        print("FAILED:ADV-0109-probe1 sentinel-absent")
        return 1

    cases = A.load_cases()
    live = A.classify_all(cases)
    represented = A.control_represented(live)
    planted = A.control_planted_drop(live)
    if not represented["pass"]:
        print("FAILED:ADV-0109-probe1 represented control", represented)
        return 1
    if not planted["pass"]:
        print("FAILED:ADV-0109-probe1 planted drop control", planted)
        return 1
    if not live["expect_match"]:
        print("FAILED:ADV-0109-probe1 expect mismatch", live["mismatches"])
        return 1

    mutant = A.classify_all(A.mutant_strip_conflict_markers(cases))
    mut_row = next(r for r in mutant["rows"] if r["id"] == "SYN-REPRESENTED")
    mut_class = mut_row["pairs"][0]["class"]
    if mut_class == "represented":
        print("FAILED:ADV-0109-probe1 conflict-strip mutant still represented")
        return 1
    if mut_class != "silently-dropped":
        print("FAILED:ADV-0109-probe1 conflict-strip mutant unexpected", mut_class)
        return 1

    silent_mutant = A.classify_all(A.mutant_strip_drop_pair(cases))
    silent_row = next(r for r in silent_mutant["rows"] if r["id"] == "SYN-DROP")
    if silent_row["counts"]["silently-dropped"] != 0:
        print("FAILED:ADV-0109-probe1 drop-pair strip did not go silent", silent_row)
        return 1

    art_pairs = {
        p["pair_id"]: p["class"]
        for row in (doc.get("forward_accounting") or {}).get("rows") or []
        for p in row.get("pairs") or []
    }
    live_pairs = {
        p["pair_id"]: p["class"]
        for row in live["rows"]
        for p in row["pairs"]
    }
    if art_pairs != live_pairs:
        print("FAILED:ADV-0109-probe1 artifact/live class drift", art_pairs, live_pairs)
        return 1

    payload = {
        "probe": "probe1-omitted-dissent",
        "represented_control": represented,
        "planted_drop_control": planted,
        "counts": live["totals"],
        "ratio": live["ratio"],
        "conflict_strip_mutant_class": mut_class,
        "drop_pair_strip_silent": True,
        "pair_classes": live_pairs,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"represented={live['totals']['represented']} "
        f"resolved={live['totals']['resolved-with-reason']} "
        f"dropped={live['totals']['silently-dropped']} "
        f"drop_rate={live['ratio']['drop_rate']}"
    )
    print(
        "SUCCESS:ADV-0109-probe1 forward classification, represented control, "
        "planted silent-drop caught, both-states mutants discriminate"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
