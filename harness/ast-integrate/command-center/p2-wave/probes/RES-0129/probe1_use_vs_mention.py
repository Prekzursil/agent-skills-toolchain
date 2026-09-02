#!/usr/bin/env python3
"""Probe 1: schema-field use vs prose mention (both states)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import extract as E  # noqa: E402
from contract import errors_for, load_art, mention_mutant  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:RES-0129-probe1 {msg}")
    return 1


def main() -> int:
    doc = load_art()
    live = E.extract_all()
    live_err = errors_for(doc, live)
    mutant_st = E.mention_mutant_statuses(live)
    red = mention_mutant(doc, mutant_st)
    red_err = errors_for(red, live)
    # The mention mutant must disagree with the live schema extractor.
    drift = 0
    for client, row in live.items():
        for concept, st in row["statuses"].items():
            if mutant_st[client][concept] != st:
                drift += 1
    print(
        json.dumps(
            {
                "probe": "probe1-use-vs-mention",
                "live_errors": live_err,
                "mention_mutant_errors": red_err,
                "mention_mutant_drift_cells": drift,
                "live_pass": not live_err,
                "red_fires": bool(red_err),
            },
            sort_keys=True,
        )
    )
    if live_err:
        return fail("live " + ";".join(live_err[:8]))
    if drift < 1:
        return fail("mention-mutant identical to schema extractor")
    if not red_err:
        return fail("mention-mutant silent (both-states failed)")
    # Prefer that the mutant creates an all-green client row or status drift.
    if not any("drift:" in e or "all-green" in e for e in red_err):
        return fail("mention-mutant errors not about use-vs-mention: " + ";".join(red_err[:6]))
    print("live_pass=True mention_mutant_fires=True")
    print("SUCCESS:RES-0129-probe1 schema fields used; prose-mention mutant fires")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
