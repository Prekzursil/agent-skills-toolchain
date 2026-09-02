"""Canonical transcript bytes, seeds, and plurality tally.

Shared by the injected runtime and the independent recount so both emit
the same *shape*. They must not share the event-ordering algorithm.
"""
from __future__ import annotations

import copy
import hashlib
import json

from scenario import roster_ids

TRANSCRIPT_SCHEMA = "cnl-0117-transcript/v1"


class MissingScriptError(RuntimeError):
    pass


def canonical_bytes(doc: dict) -> bytes:
    return (
        json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"
    ).encode("ascii")


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def digest_doc(doc: dict) -> str:
    return digest_bytes(canonical_bytes(doc))


def script_digest(scenario: dict) -> str:
    body = json.dumps(
        scenario["scripts"], sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(body.encode("ascii")).hexdigest()


def seeds_of(scenario: dict) -> dict:
    return {
        "roster_order": roster_ids(scenario),
        "round_ceiling": int(scenario["round_ceiling"]),
        "script_digest": script_digest(scenario),
        "tally_method": scenario["tally_method"],
    }


def find_act(scenario: dict, actor: str, rnd: int) -> dict | None:
    for act in scenario["scripts"].get(actor) or []:
        if act.get("round") == rnd:
            return act
    return None


def event_record(seq: int, rnd: int, actor: str, kind: str, payload: dict) -> dict:
    return {
        "seq": seq,
        "round": rnd,
        "actor": actor,
        "kind": kind,
        "payload": copy.deepcopy(payload),
    }


def plurality_tally(events: list[dict]) -> dict:
    counts: dict[str, int] = {}
    ballots: list[dict] = []
    for event in events:
        if event.get("kind") != "vote":
            continue
        payload = event.get("payload") or {}
        option = payload.get("option")
        if not isinstance(option, str) or not option:
            raise MissingScriptError(f"vote without option: {event!r}")
        weight = int(payload.get("weight", 1))
        counts[option] = counts.get(option, 0) + weight
        ballots.append({"actor": event["actor"], "option": option, "weight": weight})
    if counts:
        top = max(counts.values())
        winner = sorted(k for k, v in counts.items() if v == top)[0]
    else:
        winner = None
    return {
        "ballots": ballots,
        "counts": {k: counts[k] for k in sorted(counts)},
        "method": "plurality",
        "winner": winner,
    }


def attach_tally_and_stop(scenario: dict, events: list[dict]) -> dict:
    renumbered = []
    for i, event in enumerate(events):
        row = copy.deepcopy(event)
        row["seq"] = i
        renumbered.append(row)
    stop_round = 0
    if renumbered:
        stop_round = max(int(e["round"]) for e in renumbered)
    ceiling = int(scenario["round_ceiling"])
    reason = "round_ceiling" if stop_round >= ceiling else "script_exhausted"
    if not renumbered:
        reason = "empty-runtime"
        stop_round = 0
    return {
        "events": renumbered,
        "scenario_id": scenario["id"],
        "schema_version": TRANSCRIPT_SCHEMA,
        "seeds": seeds_of(scenario),
        "stop": {"reason": reason, "round": stop_round},
        "tally": plurality_tally(renumbered),
    }
