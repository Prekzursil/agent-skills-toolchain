#!/usr/bin/env python3
"""Probe 1: planted co-change is FLAGGED; unrelated source+snapshot is not.

Both-states control for the intersection itself. An always-empty mutant
must miss the planted pair. Recomputes live and checks the receipt.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import cochange as C  # noqa: E402

ART = REPO / C.OUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:{C.UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    if C.SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if doc.get("unit_id") != C.UNIT:
        return fail(f"unit_id={doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")

    live = C.run_named_scenarios()
    if not live["all_pass"]:
        return fail(f"live scenarios {live['tests']}")

    planted = live["scenarios"]["planted"]
    unrelated = live["scenarios"]["unrelated"]
    paths = live["paths"]
    want_pair = f"{paths['widget_snap']} ++ {paths['widget_src']}"

    if planted["verdict"] != "FLAGGED":
        return fail(f"planted verdict={planted['verdict']}")
    if planted["named_pairs"] != [want_pair]:
        return fail(f"planted pairs={planted['named_pairs']}")
    if planted["intersection"][0]["justification_class"] != "UNJUSTIFIED":
        return fail("planted pair not UNJUSTIFIED")

    if unrelated["intersection_size"] != 0 or unrelated["verdict"] != "PASS":
        return fail(
            f"unrelated flagged pairs={unrelated['named_pairs']} "
            f"verdict={unrelated['verdict']}"
        )

    mutant = C.mutant_empty_intersection(
        planted["changed_files"],
        C.load_coverage(REPO / paths["coverage"]),
    )
    if mutant:
        return fail("always-empty mutant unexpectedly reported pairs")

    art_planted = (doc.get("scenarios") or {}).get("planted") or {}
    art_unrelated = (doc.get("scenarios") or {}).get("unrelated") or {}
    if art_planted.get("verdict") != "FLAGGED":
        return fail(f"receipt planted verdict={art_planted.get('verdict')}")
    if art_planted.get("named_pairs") != [want_pair]:
        return fail(f"receipt planted pairs={art_planted.get('named_pairs')}")
    if art_unrelated.get("verdict") != "PASS":
        return fail(f"receipt unrelated verdict={art_unrelated.get('verdict')}")
    if art_unrelated.get("intersection_size") != 0:
        return fail("receipt unrelated intersection not empty")

    print(
        json.dumps(
            {
                "probe": "probe1-planted-and-unrelated",
                "planted_verdict": planted["verdict"],
                "planted_named_pairs": planted["named_pairs"],
                "unrelated_verdict": unrelated["verdict"],
                "unrelated_intersection_size": unrelated["intersection_size"],
                "mutant_empty": True,
                "receipt_matches": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"SUCCESS:{C.UNIT}-probe1 planted={want_pair} FLAGGED; "
        "unrelated gadget.py+widget.snap not flagged"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
