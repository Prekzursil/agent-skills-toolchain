#!/usr/bin/env python3
"""Named probe 2: invented edge with an unresolvable turn id must FAIL validation.

Both-states control: a graph whose edges cite real turns validates; the same
graph with one ghost turn_id raises UnresolvableTurnId.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.council.artifacts.argument_graph import (  # noqa: E402
    ArgumentGraph,
    Edge,
    UnresolvableTurnId,
    build_argument_graph,
    validate_graph,
)

GHOST = "t-does-not-exist"


def mini_turns() -> list[dict]:
    return [
        {
            "turn_id": "t001",
            "speaker": "alice",
            "text": "CLAIM-c001: The kernel owns the event loop.",
        },
        {
            "turn_id": "t002",
            "speaker": "bob",
            "text": "CLAIM-c002: Topologies must not bypass the kernel.",
        },
        {
            "turn_id": "t003",
            "speaker": "carol",
            "text": "CLAIM-c002 SUPPORTS CLAIM-c001: bypasses skip the log.",
        },
    ]


def main() -> int:
    turns = mini_turns()
    good = build_argument_graph(turns)
    try:
        validate_graph(good, turns)
        good_ok = True
        good_err = None
    except Exception as exc:  # noqa: BLE001 — both-states records the exception
        good_ok = False
        good_err = f"{type(exc).__name__}: {exc}"

    bad = ArgumentGraph(
        claims=dict(good.claims),
        edges=list(good.edges)
        + [
            Edge(
                source="c001",
                target="c002",
                relation="ATTACKS",
                turn_id=GHOST,
                speaker="inventor",
                evidence_span="invented",
            )
        ],
    )
    fired = False
    bad_err = None
    try:
        validate_graph(bad, turns)
    except UnresolvableTurnId as exc:
        fired = True
        bad_err = str(exc)
        if GHOST not in exc.unresolvable_turn_ids:
            print(
                f"FAILED:IMP-0313-probe2 ghost id missing from {exc.unresolvable_turn_ids}"
            )
            return 1
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED:IMP-0313-probe2 wrong exception {type(exc).__name__}: {exc}")
        return 1

    empty_turn = ArgumentGraph(
        claims=dict(good.claims),
        edges=list(good.edges)
        + [
            Edge(
                source="c001",
                target="c002",
                relation="REBUTS",
                turn_id="",
                speaker="inventor",
            )
        ],
    )
    empty_fired = False
    try:
        validate_graph(empty_turn, turns)
    except UnresolvableTurnId:
        empty_fired = True
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED:IMP-0313-probe2 empty-id wrong exception {type(exc).__name__}")
        return 1

    if not good_ok:
        print(f"FAILED:IMP-0313-probe2 good graph rejected: {good_err}")
        return 1
    if not fired:
        print("FAILED:IMP-0313-probe2 invented unresolvable turn id was accepted")
        return 1
    if not empty_fired:
        print("FAILED:IMP-0313-probe2 empty turn id was accepted")
        return 1
    if not any(e.relation == "SUPPORTS" for e in good.edges):
        print("FAILED:IMP-0313-probe2 expected SUPPORTS on the mini fixture")
        return 1

    summary = {
        "probe": "probe2-unresolvable-turn-id",
        "unit_id": "IMP-0313",
        "good_validates": good_ok,
        "ghost_turn_id": GHOST,
        "fired_on_ghost": fired,
        "fired_on_empty_turn_id": empty_fired,
        "silent_on_good": good_ok,
        "exception": bad_err,
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"good_ok={good_ok} fired_on_ghost={fired} "
        f"fired_on_empty={empty_fired} ghost={GHOST}"
    )
    print("SUCCESS:IMP-0313-probe2 unresolvable turn id fails validation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
