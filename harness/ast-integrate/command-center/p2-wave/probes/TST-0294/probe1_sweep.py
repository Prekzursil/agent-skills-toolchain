#!/usr/bin/env python3
"""Probe 1: 48/48 terminal, stopping terms, invariants, pairwise distinctness.

Source probe. Re-runs the sweep live, then checks the receipt table matches.
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
    print(f"FAILED:TST-0294-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 256:
        return fail("artifact missing or tiny")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != R.UNIT:
        return fail(f"unit_id {doc.get('unit_id')}")
    if R.SENTINEL not in text:
        return fail("sentinel absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {st}")

    live = R.measure()
    if live["n"] != 48:
        return fail(f"n={live['n']} want 48")
    if live["n_done"] != 48:
        return fail(f"n_done={live['n_done']}")
    if live["failed_rows"]:
        return fail(f"failed_rows={live['failed_rows']}")
    if live["collisions"]:
        return fail(f"collisions={live['collisions']}")
    if not live["rename_copy_control"]["ok"]:
        return fail("rename-copy distinctness control did not fire")
    if not live["steelman_both_states"]["wired"]:
        return fail("steelman both-states not wired")

    art_rows = list(doc.get("protocol_rows") or [])
    if len(art_rows) != 48:
        return fail(f"artifact rows {len(art_rows)}")
    live_ids = [r["id"] for r in live["rows"]]
    art_ids = [r["id"] for r in art_rows]
    if live_ids != art_ids:
        return fail("id order mismatch vs live sweep")
    for a, b in zip(art_rows, live["rows"]):
        if a.get("terminal_state") != "DONE":
            return fail(f"{a.get('id')} terminal_state={a.get('terminal_state')}")
        if not a.get("stopping_term"):
            return fail(f"{a.get('id')} missing stopping_term")
        if a.get("stopping_term") != b["stopping_term"]:
            return fail(f"{a.get('id')} stopping_term artifact vs live")
        if a.get("invariant_ok") is not True:
            return fail(f"{a.get('id')} invariant_ok false")
        if a.get("stage_sequence") != b["stage_sequence"]:
            return fail(f"{a.get('id')} stage_sequence mismatch")
        if a.get("row_pass") is not True:
            return fail(f"{a.get('id')} row_pass false")

    oxford = next(r for r in art_rows if r["id"] == "P07")
    if "rebuttal" not in json.dumps(oxford["stage_sequence"]):
        return fail("P07 oxford stage_sequence lacks rebuttal")
    jury = next(r for r in art_rows if r["id"] == "P14")
    if "jury" not in json.dumps(jury["stage_sequence"]):
        return fail("P14 jury phase absent from stage_sequence")

    print(
        json.dumps(
            {
                "n": 48,
                "n_done": 48,
                "collisions": 0,
                "rename_copy_fires": True,
                "stopping_terms": sorted({r["stopping_term"] for r in art_rows}),
                "probe": "probe1-sweep",
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:TST-0294-probe1 48/48 terminal distinct invariants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
