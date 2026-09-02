#!/usr/bin/env python3
"""Probe 2: iterative recount + generation-candidate both-states + drift.

Mechanically different from probe1: iterative stack walk of the schema
(not recursion) and argparse-help / contracted-artifact drift (a different
data field than the schema slot list). Headline string count must match
probe1 and COST.json or this unit is BLOCKED.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402
import drift as D  # noqa: E402
import stale as S  # noqa: E402

REPO = C.REPO
COST = REPO / "command-center/phase3/A8/COST.json"
REG = C.REGISTRY_PATH


def main() -> int:
    schema = C.load_schema()
    it_wf = C.string_slots_iterative(schema, C.WF_DEF)
    it_pr = C.string_slots_iterative(schema, C.PRESET_DEF)
    rec_wf = C.string_slots_recursive(schema, C.WF_DEF)
    rec_pr = C.string_slots_recursive(schema, C.PRESET_DEF)
    if it_wf != rec_wf or it_pr != rec_pr:
        print("FAILED:ARC-0053-probe2 iterative vs recursive disagree")
        print(f" it_wf={it_wf} rec_wf={rec_wf}")
        print(f" it_pr={it_pr} rec_pr={rec_pr}")
        return 1
    strings = C.product_strings(len(it_wf), len(it_pr))
    print(
        f"iterative slots_wf={len(it_wf)} slots_preset={len(it_pr)} "
        f"strings={strings} help_topics={C.help_topics()} examples={C.examples()}"
    )
    registry = C.load_registry()
    wfs = C.live_entries(registry, C.WF_DEF)
    presets = C.live_entries(registry, C.PRESET_DEF)
    sample = wfs[0] if wfs else {"id": "missing", "kind": C.WF_DEF}
    states = S.both_states(sample)
    print(
        f"stale silent_on_match={states['silent_on_match']} "
        f"fires_on_page_edit={states['fires_on_page_edit']} "
        f"fires_on_registry_change={states['fires_on_registry_change']}"
    )
    if not (
        states["silent_on_match"]
        and states["fires_on_page_edit"]
        and states["fires_on_registry_change"]
    ):
        print("FAILED:ARC-0053-probe2 generation-candidate both-states")
        return 1
    d = D.measure()
    print(
        f"drift sample={d['sample_size']} divergences={d['divergences']} "
        f"rate={d['rate']:.6f} git={d['historical_git_rate']}"
    )
    if d["sample_size"] < 1:
        print("FAILED:ARC-0053-probe2 empty drift sample")
        return 1
    if not COST.is_file():
        print("FAILED:ARC-0053-probe2 COST.json missing")
        return 1
    doc = json.loads(COST.read_text(encoding="utf-8"))
    if doc["headline"]["user_facing_strings"] != strings:
        print(
            "FAILED:ARC-0053-probe2 readings disagree "
            f"iterative={strings} cost={doc['headline']['user_facing_strings']}"
        )
        return 1
    if doc["two_probe_readings"]["agree"] is not True:
        print("FAILED:ARC-0053-probe2 COST two_probe_readings.agree is not true")
        return 1
    if doc["two_probe_readings"]["probe2_user_facing_strings"] != strings:
        print("FAILED:ARC-0053-probe2 stored probe2 reading mismatch")
        return 1
    if abs(float(doc["drift"]["rate"]) - d["rate"]) > 1e-12:
        print("FAILED:ARC-0053-probe2 drift rate mismatch vs COST.json")
        return 1
    if not presets:
        print("FAILED:ARC-0053-probe2 no live council_preset")
        return 1
    print("SUCCESS:ARC-0053-probe2 iterative recount, drift, and stale both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
