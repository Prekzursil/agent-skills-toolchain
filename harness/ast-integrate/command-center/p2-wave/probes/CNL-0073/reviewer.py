"""Independent set-algebra recount of the both-states control.

Does not call proof.qualify or proof.walk_unvisited. Loads the same fixtures
and decides exhaustiveness by set difference, then applies the WITNESS
predicate on disk bytes.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import proof as P  # noqa: E402

TERM_PROOF = P.TERM_PROOF
TERM_SEARCH = P.TERM_SEARCH
TERM_GAVE_UP = P.TERM_GAVE_UP
TERM_FOUND = P.TERM_FOUND
TERM_OPEN = P.TERM_OPEN
TERM_MALFORMED = P.TERM_MALFORMED


def independent_qualify(name: str) -> dict:
    fix = P.load_fixture(name)
    universe = list(fix["universe_members"])
    visited = list(fix["visited"])
    if not universe or not str(fix["settling_experiment"] or "").strip():
        return {
            "fixture": name,
            "qualifies": False,
            "classification": TERM_MALFORMED,
            "unvisited": universe,
            "mechanism": "set-difference",
        }
    extra = [v for v in visited if v not in universe]
    if extra:
        return {
            "fixture": name,
            "qualifies": False,
            "classification": TERM_MALFORMED,
            "unvisited": extra,
            "mechanism": "set-difference",
        }
    unvisited = sorted(set(universe) - set(visited))
    witness_visited = any(
        P.member_has_witness(fix["members_dir"], n) for n in visited
    )
    omniscient = any(
        P.member_has_witness(fix["members_dir"], n) for n in unvisited
    )
    if not fix["universe_closed"]:
        cls, ok = TERM_OPEN, False
    elif unvisited:
        if fix["attempt_limit_reached"]:
            cls, ok = TERM_GAVE_UP, False
        else:
            cls, ok = TERM_SEARCH, False
    elif witness_visited:
        cls, ok = TERM_FOUND, False
    else:
        cls, ok = TERM_PROOF, True
    return {
        "fixture": name,
        "qualifies": ok,
        "classification": cls,
        "unvisited": unvisited,
        "unvisited_count": len(unvisited),
        "witness_on_visited": witness_visited,
        "omniscient_witness_in_unvisited": omniscient,
        "mechanism": "set-difference",
    }


def independent_both_states() -> dict:
    incomplete = independent_qualify("incomplete-luck")
    exhaustive = independent_qualify("exhaustive")
    missed = independent_qualify("incomplete-missed")
    gave = independent_qualify("gave-up")
    ok = (
        incomplete["qualifies"] is False
        and incomplete["classification"] == TERM_SEARCH
        and exhaustive["qualifies"] is True
        and exhaustive["classification"] == TERM_PROOF
        and missed["qualifies"] is False
        and missed["classification"] == TERM_SEARCH
        and missed["omniscient_witness_in_unvisited"] is True
        and gave["qualifies"] is False
        and gave["classification"] == TERM_GAVE_UP
        and gave["classification"] != exhaustive["classification"]
    )
    return {
        "incomplete_luck": incomplete,
        "exhaustive": exhaustive,
        "incomplete_missed": missed,
        "gave_up": gave,
        "both_directions_ok": ok,
        "mechanism": "set-difference",
        "re_ran_both_states": True,
    }


def author_agrees() -> tuple[bool, str]:
    author = P.both_states()
    indep = independent_both_states()
    pairs = [
        ("incomplete_luck", "incomplete_luck"),
        ("exhaustive", "exhaustive"),
        ("incomplete_missed", "incomplete_missed"),
        ("gave_up", "gave_up"),
    ]
    for a_key, i_key in pairs:
        a = author[a_key]
        i = indep[i_key]
        if a["qualifies"] != i["qualifies"] or a["classification"] != i["classification"]:
            return False, f"disagree:{a_key} author={a['classification']} indep={i['classification']}"
        if set(a["unvisited"]) != set(i["unvisited"]):
            return False, f"unvisited-disagree:{a_key}"
    if not author["both_directions_ok"] or not indep["both_directions_ok"]:
        return False, "both-states-not-ok"
    return True, "author-walk-and-reviewer-set-difference-agree"
