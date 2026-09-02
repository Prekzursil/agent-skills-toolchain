#!/usr/bin/env python3
"""Probe 1: gaming attempt per target, independently re-run.

For each of the eight targets, produce input that maximises a naive metric
while failing intent. A metric that cannot be gamed in the attempt is recorded
as evidence (intent_held), not asserted. Recomputes from ops.py; compares with
the emitted artifact numbers.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import ops as O  # noqa: E402

OUT = (
    REPO
    / "command-center/design/council/"
    / "CNL-0009-target-block-which-of-the-8-targets-are-measurable-as-writ.md"
)


def main() -> int:
    live = O.evaluate_gaming()
    if not OUT.is_file():
        print("FAILED:CNL-0009-probe1 artifact missing")
        return 1
    art = json.loads(OUT.read_text(encoding="utf-8"))
    by_id = {row["id"]: row for row in art.get("targets") or []}
    fail = False
    recorded = 0
    for tid in O.TARGETS:
        g = live[tid]
        rec = (by_id.get(tid) or {}).get("gaming") or {}
        match = (
            rec.get("naive_metric") == g["naive_metric"]
            and rec.get("operational_metric") == g["operational_metric"]
            and rec.get("intent_held") is True
            and rec.get("gamed_naive") is True
            and g["intent_held"]
            and g["gamed_naive"]
        )
        recorded += 1
        print(
            f"target={tid} naive={g['naive_metric']} operational={g['operational_metric']} "
            f"gamed_naive={g['gamed_naive']} intent_held={g['intent_held']} artifact_match={match}"
        )
        if not match:
            fail = True
    if recorded != 8:
        fail = True
    if not live["_all_attempts_recorded"] == list(O.TARGETS):
        fail = True
    unmeas = art.get("unmeasurable_as_written") or []
    if unmeas != list(O.TARGETS):
        print(f"FAILED:CNL-0009-probe1 unmeasurable drift {unmeas}")
        fail = True
    print(f"recorded={recorded}/8 fail={fail} all_intent_held={live['_all_intent_held']}")
    if fail:
        print("FAILED:CNL-0009-probe1 gaming attempts")
        return 1
    print("SUCCESS:CNL-0009-probe1 gaming attempts recorded and recomputed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
