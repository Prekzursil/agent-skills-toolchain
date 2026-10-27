#!/usr/bin/env python3
"""Probe 1: both-states per direction, detector controls, live two-count
measurement against the real tree (counts separate, never combined).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import live as L  # noqa: E402
from common import REPO, SENTINEL, UNIT_ID, fail  # noqa: E402

ART = REPO / "command-center/phase3/A2/FAILURE-MODES.json"


def main() -> int:
    scratch = Path(tempfile.mkdtemp(prefix=f"{UNIT_ID.lower()}-p1-"))
    bs = L.both_states(scratch)
    print(json.dumps({"probe": "probe1-both-states", "unit_id": UNIT_ID, **bs}, sort_keys=True))
    for key in (
        "a_fires_on_missing",
        "a_silent_on_complete",
        "a_counts_empty_as_missing",
        "b_fires_on_planted",
        "b_silent_when_none",
        "restore_complete",
    ):
        if bs.get(key) is not True:
            return fail(f"both-states {key} is not true")

    live = L.measure_live()
    print(json.dumps({"probe": "probe1-live-counts", "unit_id": UNIT_ID, **{k: v for k, v in live.items() if 'orphans' != k[-7:]},}, sort_keys=True, default=str))
    art = json.loads(ART.read_text(encoding="utf-8"))
    if SENTINEL not in ART.read_text(encoding="utf-8"):
        return fail("catalog sentinel absent")
    if str(art.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {art.get('state')}")
    lc = art.get("live_completeness") or {}
    if live["direction_a_orphan_registry_count"] != lc.get("direction_a_orphan_registry_count"):
        return fail(
            f"live A count {live['direction_a_orphan_registry_count']} != artifact {lc.get('direction_a_orphan_registry_count')}"
        )
    if live["direction_b_orphan_output_count"] != lc.get("direction_b_orphan_output_count"):
        return fail(
            f"live B count {live['direction_b_orphan_output_count']} != artifact {lc.get('direction_b_orphan_output_count')}"
        )

    # Drift between the recorded id set (old registry generation) and the live
    # id set (current registry) is reported, not asserted away.
    art_ids = [o.get("id") for o in lc.get("direction_a_orphans") or []]
    live_ids = sorted(r["id"] for r in live["direction_a_orphans"])
    shared = sorted(set(art_ids) & set(live_ids))
    drifted = sorted(set(art_ids) ^ set(live_ids))
    print(
        f"drift shared={len(shared)} drifted={len(drifted)} "
        f"live_ids={live_ids}"
    )
    print(f"SUCCESS:{UNIT_ID}-probe1 A={live['direction_a_orphan_registry_count']} B={live['direction_b_orphan_output_count']} counts reproduce; both-states fire")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
