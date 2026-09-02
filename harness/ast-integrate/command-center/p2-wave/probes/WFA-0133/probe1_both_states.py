#!/usr/bin/env python3
"""Probe 1: both-states fusion scoring (unmeasured refuse / measured accept).

Live. Does not read the foundry artifact narrative.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import corpus  # noqa: E402
import ledger as L  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0133-probe1 {msg}")
    return 1


def main() -> int:
    loaded = corpus.load_merge_units()
    units = loaded["units"]
    if len(units) != 30:
        return fail(f"corpus n={len(units)} != 30")
    with tempfile.TemporaryDirectory(prefix="wfa0133-p1-") as td:
        scratch = Path(td) / "scratch.json"
        both = L.both_states(units, scratch)
        if not both.get("ok"):
            print(json.dumps(both, indent=2, sort_keys=True)[:4000])
            return fail("both-states did not discriminate")
        flagged = next(u for u in units if u["sources_unresolved"])
        book = L.BaselineLedger(Path(td) / "unresolved.json")
        book.measure_all_sources(flagged)
        scored = book.score_fusion(flagged)
        if not scored.get("accepted"):
            return fail(
                f"unresolved-source unit refused after resolved baselines: {scored}"
            )
        if book.missing_sources(flagged):
            return fail("unresolved ids leaked into missing_sources")
    doc = {
        "both_states": both,
        "corpus_source": loaded["source"],
        "pass": True,
        "probe": "probe1-both-states",
        "unresolved_not_required": True,
        "unit_id": "WFA-0133",
    }
    print(json.dumps(doc, sort_keys=True))
    print("SUCCESS:WFA-0133-probe1 both-states unmeasured-refuse measured-accept")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
