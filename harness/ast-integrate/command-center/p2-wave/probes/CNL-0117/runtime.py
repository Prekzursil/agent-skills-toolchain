"""Injected council runtimes. The harness is not these classes."""
from __future__ import annotations

import copy

from scenario import roster_ids
from transcript import MissingScriptError, attach_tally_and_stop, event_record, find_act


class HonestRuntime:
    """Consumes one scripted act per (actor, round) in roster order.

    Does not consult recount.py. Does not return a cached transcript.
    """

    name = "honest"

    def run(self, scenario: dict) -> dict:
        events: list[dict] = []
        seq = 0
        ceiling = int(scenario["round_ceiling"])
        for rnd in range(1, ceiling + 1):
            for actor in roster_ids(scenario):
                act = find_act(scenario, actor, rnd)
                if act is None:
                    raise MissingScriptError(f"no scripted act for {(actor, rnd)}")
                events.append(
                    event_record(
                        seq=seq,
                        rnd=rnd,
                        actor=actor,
                        kind=act["kind"],
                        payload=copy.deepcopy(act["payload"]),
                    )
                )
                seq += 1
        return attach_tally_and_stop(scenario, events)


class DropRefusalRuntime(HonestRuntime):
    """Planted-bad runtime: silently omits every scripted refusal.

    Votes and positions still land. A harness that is vacuously green
    would accept this transcript.
    """

    name = "drop-refusal"

    def run(self, scenario: dict) -> dict:
        honest = super().run(scenario)
        kept = [e for e in honest["events"] if e["kind"] != "refusal"]
        return attach_tally_and_stop(scenario, kept)


class EmptyRuntime:
    """Planted-bad runtime: emits no events. Two-run identity still holds."""

    name = "empty"

    def run(self, scenario: dict) -> dict:
        return attach_tally_and_stop(scenario, [])


class CachedConstantRuntime:
    """Planted-bad runtime: ignores the live script and returns a frozen body."""

    name = "cached-constant"

    def __init__(self, frozen: dict):
        self.frozen = copy.deepcopy(frozen)

    def run(self, scenario: dict) -> dict:
        del scenario
        return copy.deepcopy(self.frozen)
