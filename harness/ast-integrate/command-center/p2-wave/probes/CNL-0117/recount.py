"""Independent recount: flatten scripts, then sort.

This is a different control-flow from HonestRuntime (round-outer, roster-inner
nested loops). A disagreement in event count or order blocks the unit.
"""
from __future__ import annotations

from scenario import roster_ids
from transcript import attach_tally_and_stop, event_record


def expected_transcript(scenario: dict) -> dict:
    index = {aid: i for i, aid in enumerate(roster_ids(scenario))}
    rows: list[tuple[int, int, int, str, dict]] = []
    for actor, acts in scenario["scripts"].items():
        for script_i, act in enumerate(acts):
            rows.append((int(act["round"]), index[actor], script_i, actor, act))
    rows.sort(key=lambda r: (r[0], r[1], r[2]))
    events = [
        event_record(
            seq=i,
            rnd=rnd,
            actor=actor,
            kind=act["kind"],
            payload=act["payload"],
        )
        for i, (rnd, _ridx, _sidx, actor, act) in enumerate(rows)
    ]
    return attach_tally_and_stop(scenario, events)


def act_keys(transcript: dict) -> list[tuple[int, str, str]]:
    return [
        (int(e["round"]), str(e["actor"]), str(e["kind"]))
        for e in transcript.get("events") or []
    ]
