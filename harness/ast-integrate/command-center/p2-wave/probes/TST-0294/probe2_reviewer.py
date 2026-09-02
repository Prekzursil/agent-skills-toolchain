#!/usr/bin/env python3
"""Probe 2: independent recount of pairwise distinctness and steelman both-states.

Does not read probe1 flags. Re-walks blueprints and re-derives collisions.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import runner as R  # noqa: E402

ART = REPO / R.ARTIFACT_REL


def fail(msg: str) -> int:
    print(f"FAILED:TST-0294-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 256:
        return fail("artifact missing or tiny")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:TST-0294" not in json.dumps(doc):
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")

    records = R.selected_records()
    walked_rows = []
    for rec in records:
        walked = R.walk_cast(rec)
        inv = R.invariant_for(rec, walked)
        walked_rows.append(
            {
                "id": rec["id"],
                "stage_sequence": [list(x) for x in walked["stage_sequence"]],
                "invariant_ok": inv["ok"],
                "terminal_state": walked["terminal_state"],
                "stopping_term": walked["stopping_term"],
            }
        )
    collisions = R.pairwise_collisions(walked_rows)
    if collisions:
        return fail(f"independent collisions {collisions}")
    if any(not r["invariant_ok"] or r["terminal_state"] != "DONE" for r in walked_rows):
        bad = [r["id"] for r in walked_rows if not r["invariant_ok"]]
        return fail(f"independent invariant fail {bad}")

    steel = R.steelman_both_states()
    if steel["intact"]["invariant_ok"] is not True:
        return fail("intact steelman did not PASS")
    if steel["broken_steelman_removed"]["invariant_ok"] is not False:
        return fail("broken steelman did not FAIL — invariant is unwired")
    if steel["same_answer_both_states"]:
        return fail("both states produced the same invariant answer")
    if not steel["wired"]:
        return fail("steelman control not wired")

    art_steel = doc.get("steelman_both_states") or {}
    if art_steel.get("wired") is not True:
        return fail("artifact steelman.wired is not true")
    if art_steel.get("same_answer_both_states") is not False:
        return fail("artifact claims same answer both states")

    art_rows = list(doc.get("protocol_rows") or [])
    live_seq = {r["id"]: r["stage_sequence"] for r in walked_rows}
    for row in art_rows:
        if live_seq.get(row["id"]) != row.get("stage_sequence"):
            return fail(f"independent stage_sequence mismatch {row.get('id')}")

    print(
        json.dumps(
            {
                "independent_n": len(walked_rows),
                "independent_collisions": 0,
                "steelman_intact": True,
                "steelman_broken_fails": True,
                "wired": True,
                "probe": "probe2-reviewer",
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:TST-0294-probe2 independent recount and steelman both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
