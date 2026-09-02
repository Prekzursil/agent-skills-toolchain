#!/usr/bin/env python3
"""Probe 1: both-states per alert predicate + artifact records the matrix.

Replay each recorded silent-failure trace and assert FIRE; replay each
healthy trace and assert SILENT. Then check FAILURE-MODES.json stored
the same per-mode results.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402
import traces as T  # noqa: E402

ART = REPO / "command-center/phase3/A5/FAILURE-MODES.json"


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0033-probe1 {msg}")
    return 1


def main() -> int:
    T.ensure_on_disk()
    matrix = E.both_states_all(T.PAIRS)
    print(json.dumps({"per_mode": matrix["per_mode"], "all_pass": matrix["all_pass"]}))
    if not matrix["all_pass"]:
        return fail(f"both-states failed {matrix['failed']}")

    if not ART.is_file():
        return fail("FAILURE-MODES.json missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:ARC-0033" not in text:
        return fail("sentinel absent")

    recorded = doc.get("both_states") or {}
    rec_rows = {
        r["mode_id"]: r
        for r in (recorded.get("per_mode") or [])
        if isinstance(r, dict) and r.get("mode_id")
    }
    for live in matrix["per_mode"]:
        rec = rec_rows.get(live["mode_id"])
        print(f"{live['mode_id']} fired={live['fired_on_silent_failure_trace']} silent={live['silent_on_healthy_trace']}")
        if rec is None:
            return fail(f"artifact missing both-states row {live['mode_id']}")
        if rec.get("fired_on_silent_failure_trace") != live["fired_on_silent_failure_trace"]:
            return fail(f"artifact fire drift {live['mode_id']}")
        if rec.get("silent_on_healthy_trace") != live["silent_on_healthy_trace"]:
            return fail(f"artifact silent drift {live['mode_id']}")
        if rec.get("pass") is not True:
            return fail(f"artifact pass false {live['mode_id']}")

    author = [m.get("id") for m in (doc.get("author_failure_modes") or [])]
    for mid in E.AUTHOR_MODE_IDS:
        if mid not in author:
            return fail(f"author mode missing {mid}")
    print("SUCCESS:ARC-0033-probe1 both-states per alert predicate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
