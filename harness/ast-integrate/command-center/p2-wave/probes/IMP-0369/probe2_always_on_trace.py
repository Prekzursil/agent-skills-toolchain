#!/usr/bin/env python3
"""Probe 2: negative control — ALWAYS-ON is visible in the load trace.

Starts from the catalog tests, not an author summary. Marking one capability
ALWAYS-ON must make its body appear in the lazy turn-zero trace. Demoting
that same record to LAZY must make the body disappear. A detector that always
lists every id, or never lists any id, fails both states.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3]))
sys.path.insert(0, str(HERE))

from tools.router import lazy as L  # noqa: E402
import scenario as S  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0369-probe2 {msg}")
    return 1


def body_ids_at_turn_zero(caps) -> list[str]:
    loader = L.GatewayLoader(caps, mode=L.MODE_LAZY)
    snap = loader.turn_zero()
    return list(snap["loaded_body_ids"]), loader.payload, snap["load_trace"]


def main() -> int:
    if not S.LAZY_PY.is_file():
        return fail("module-absent")
    S.write_index()
    good = S.capabilities()
    body_ids, payload, trace = body_ids_at_turn_zero(good)
    if S.ALWAYS_ON_ID not in body_ids:
        return fail(
            "ALWAYS-ON capability missing from lazy turn-zero load trace "
            f"ids={body_ids}"
        )
    if S.unique_marker(S.ALWAYS_ON_ID) not in payload:
        return fail("ALWAYS-ON unique marker absent from payload (trace may be lying)")
    if S.SELECT_ID in body_ids:
        return fail("LAZY sibling appeared at turn zero; trace cannot distinguish eager")
    if S.unique_marker(S.SELECT_ID) in payload:
        return fail("LAZY sibling unique marker leaked into turn-zero payload")
    always_events = [
        e
        for e in trace
        if e.get("kind") == L.KIND_BODY
        and e.get("capability_id") == S.ALWAYS_ON_ID
        and e.get("trigger") == L.TRIGGER_TURN_ZERO_ALWAYS_ON
    ]
    if len(always_events) != 1:
        return fail(f"expected one ALWAYS-ON body event, got {always_events}")

    # Bad state: demote the ALWAYS-ON record. The same instrument must go silent.
    bad = copy.deepcopy(good)
    demoted = False
    for rec in bad:
        if rec["capability_id"] == S.ALWAYS_ON_ID:
            rec["load_mode"] = "LAZY"
            demoted = True
    if not demoted:
        return fail("fixture missing ALWAYS-ON record to demote")
    bad_ids, bad_payload, _bad_trace = body_ids_at_turn_zero(bad)
    if S.ALWAYS_ON_ID in bad_ids:
        return fail(
            "demoted ALWAYS-ON still in load trace; instrument cannot detect eager load"
        )
    if S.unique_marker(S.ALWAYS_ON_ID) in bad_payload:
        return fail("demoted body still in payload")
    if bad_ids:
        return fail(f"demoted index still loaded bodies {bad_ids}")

    # Accidental-eager plant: force-load a LAZY body at turn zero via eager mode
    # on a single-record slice... actually: GatewayLoader eager on full index
    # must list SELECT_ID, proving the trace fires when a body does load.
    eager = L.GatewayLoader(good, mode=L.MODE_EAGER)
    eager.turn_zero()
    if S.SELECT_ID not in eager.body_ids():
        return fail("eager trace did not record a known body load")
    if S.unique_marker(S.SELECT_ID) not in eager.payload:
        return fail("eager payload missing planted body marker")

    summary = {
        "probe": "probe2-always-on-trace",
        "unit_id": "IMP-0369",
        "always_on_id": S.ALWAYS_ON_ID,
        "lazy_sibling_id": S.SELECT_ID,
        "good_turn_zero_body_ids": body_ids,
        "bad_demoted_body_ids": bad_ids,
        "fired_on_always_on": S.ALWAYS_ON_ID in body_ids,
        "silent_after_demote": S.ALWAYS_ON_ID not in bad_ids,
        "eager_trace_detects_body": S.SELECT_ID in eager.body_ids(),
        "always_on_event_tokens": always_events[0]["tokens"],
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"always_on={S.ALWAYS_ON_ID} in_trace={body_ids} "
        f"demoted_ids={bad_ids} eager_detects={S.SELECT_ID in eager.body_ids()}"
    )
    print("SUCCESS:IMP-0369-probe2 ALWAYS-ON visible in load trace; demote is silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
