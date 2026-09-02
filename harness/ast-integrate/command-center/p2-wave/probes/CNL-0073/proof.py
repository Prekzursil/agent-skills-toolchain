#!/usr/bin/env python3
"""Closed-world exhaustive-refutation detector for proof_of_impossibility.

The stopping expression proof_of_impossibility == true is discharged only by
an exhaustive enumeration of a finite closed universe on which the existence
predicate is false for every member. An unsuccessful search (visited is a
proper subset of the universe) is classified UNSUCCESSFUL_SEARCH and never
discharges the flag, including the case where unread members happen to also
lack a witness. Gave-up (attempt-limit) is a distinct terminal.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
WITNESS_TOKEN = "WITNESS"

# Distinct terminals: gave-up and proved-impossible must not share a path.
TERM_PROOF = "EXHAUSTIVE_REFUTATION"
TERM_SEARCH = "UNSUCCESSFUL_SEARCH"
TERM_GAVE_UP = "GAVE_UP"
TERM_FOUND = "COUNTEREXAMPLE_FOUND"
TERM_OPEN = "OPEN_WORLD"
TERM_MALFORMED = "MALFORMED"

EXPECTED = {
    "exhaustive": (True, TERM_PROOF),
    "incomplete-luck": (False, TERM_SEARCH),
    "incomplete-missed": (False, TERM_SEARCH),
    "gave-up": (False, TERM_GAVE_UP),
}


def member_has_witness(members_dir: Path, name: str) -> bool:
    path = members_dir / name
    if not path.is_file():
        raise FileNotFoundError(name)
    return WITNESS_TOKEN in path.read_text(encoding="utf-8")


def walk_unvisited(universe_members: list[str], visited: list[str]) -> list[str]:
    """Mechanism 1: sequential membership walk (order-preserving)."""
    unvisited: list[str] = []
    for member in universe_members:
        found = False
        for seen in visited:
            if seen == member:
                found = True
                break
        if not found:
            unvisited.append(member)
    return unvisited


def set_unvisited(universe_members: list[str], visited: list[str]) -> set[str]:
    """Mechanism 2: set difference (independent of walk order)."""
    return set(universe_members) - set(visited)


def load_fixture(name: str) -> dict:
    root = FIXTURES / name
    meta = json.loads((root / "universe.json").read_text(encoding="utf-8"))
    log = json.loads((root / "search-log.json").read_text(encoding="utf-8"))
    members_dir = root / "members"
    universe = list(meta["universe_members"])
    visited = list(log["visited"])
    return {
        "id": name,
        "root": root,
        "members_dir": members_dir,
        "universe_closed": bool(meta.get("universe_closed")),
        "universe_members": universe,
        "visited": visited,
        "attempt_limit_reached": bool(log.get("attempt_limit_reached")),
        "claimed_proof_of_impossibility": bool(
            meta.get("claimed_proof_of_impossibility")
        ),
        "settling_experiment": str(meta.get("settling_experiment") or ""),
        "terminal_kind_claimed": str(meta.get("terminal_kind") or ""),
    }


def _malformed(fix: dict, why: str) -> dict:
    return {
        "fixture": fix["id"],
        "qualifies": False,
        "classification": TERM_MALFORMED,
        "why": why,
        "claimed_proof_of_impossibility": fix["claimed_proof_of_impossibility"],
        "claimed_ignored": True,
        "universe_closed": fix["universe_closed"],
        "universe_size": len(fix["universe_members"]),
        "visited_size": len(fix["visited"]),
        "unvisited": list(fix["universe_members"]),
        "unvisited_count": len(fix["universe_members"]),
        "walk_unvisited": list(fix["universe_members"]),
        "set_unvisited": sorted(fix["universe_members"]),
        "mechanisms_agree": True,
        "existence_on_visited": {},
        "witness_on_visited": False,
        "omniscient_witness_in_unvisited": False,
        "settling_experiment": fix["settling_experiment"],
        "attempt_limit_reached": fix["attempt_limit_reached"],
    }


def qualify(fix: dict) -> dict:
    """Compute whether proof_of_impossibility may be true.

    claimed_proof_of_impossibility is recorded then ignored. Qualification is
    computed from universe, visits, and the WITNESS predicate on bytes.
    """
    universe = fix["universe_members"]
    visited = fix["visited"]
    if not universe:
        return _malformed(fix, "empty-universe")
    if not fix["settling_experiment"].strip():
        return _malformed(fix, "settling-experiment-missing")
    extra = [v for v in visited if v not in universe]
    if extra:
        return _malformed(fix, f"visited-outside-universe:{extra}")
    for name in universe:
        if not (fix["members_dir"] / name).is_file():
            return _malformed(fix, f"missing-member-file:{name}")

    # RULE-EXHAUSTIVENESS: unvisited must be empty
    walk = walk_unvisited(universe, visited)
    diff = set_unvisited(universe, visited)
    agree = set(walk) == diff
    if not agree:
        return _malformed(fix, f"mechanism-disagreement walk={walk} set={sorted(diff)}")

    existence_on_visited = {
        name: member_has_witness(fix["members_dir"], name) for name in visited
    }
    witness_on_visited = any(existence_on_visited.values())
    omniscient = any(
        member_has_witness(fix["members_dir"], name) for name in walk
    )

    if not fix["universe_closed"]:
        classification = TERM_OPEN
        qualifies = False
        why = "open-world-universe"
    elif walk:
        # RULE-NO-LAUNDER: unsuccessful search never discharges proof_of_impossibility
        # Distinct path from proof: incompleteness is classified before any
        # existence roll-up, so a lucky-true remainder cannot launder a proof.
        if fix["attempt_limit_reached"]:
            classification = TERM_GAVE_UP
            why = "attempt-limit-and-unvisited"
        else:
            classification = TERM_SEARCH
            why = "searched-but-not-exhaustive"
        qualifies = False
    elif witness_on_visited:
        classification = TERM_FOUND
        qualifies = False
        why = "witness-present-in-closed-universe"
    else:
        classification = TERM_PROOF
        qualifies = True
        why = "closed-world-exhaustive-negative"

    return {
        "fixture": fix["id"],
        "qualifies": qualifies,
        "classification": classification,
        "why": why,
        "claimed_proof_of_impossibility": fix["claimed_proof_of_impossibility"],
        "claimed_ignored": True,
        "universe_closed": fix["universe_closed"],
        "universe_size": len(universe),
        "visited_size": len(visited),
        "unvisited": walk,
        "unvisited_count": len(walk),
        "walk_unvisited": walk,
        "set_unvisited": sorted(diff),
        "mechanisms_agree": True,
        "existence_on_visited": existence_on_visited,
        "witness_on_visited": witness_on_visited,
        "omniscient_witness_in_unvisited": omniscient,
        "settling_experiment": fix["settling_experiment"],
        "attempt_limit_reached": fix["attempt_limit_reached"],
    }


def run_named(name: str) -> dict:
    return qualify(load_fixture(name))


def run_all() -> dict[str, dict]:
    return {name: run_named(name) for name in EXPECTED}


def both_states() -> dict:
    incomplete = run_named("incomplete-luck")
    exhaustive = run_named("exhaustive")
    missed = run_named("incomplete-missed")
    gave = run_named("gave-up")
    # Incomplete-luck unread members also lack WITNESS: conclusion may be
    # true, proof still rejected. That is the anti-laundering control.
    luck_unread_clean = (
        (not incomplete["qualifies"])
        and incomplete["classification"] == TERM_SEARCH
        and incomplete["unvisited_count"] > 0
        and incomplete["omniscient_witness_in_unvisited"] is False
        and incomplete["witness_on_visited"] is False
    )
    ok = (
        luck_unread_clean
        and exhaustive["qualifies"] is True
        and exhaustive["classification"] == TERM_PROOF
        and exhaustive["unvisited_count"] == 0
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
        "luck_unread_clean": luck_unread_clean,
        "negative_control": {
            "rejects": "searched-but-not-exhaustive recorded as proof_of_impossibility",
            "fixture": "incomplete-luck",
            "what_the_check_does": (
                "On incomplete-luck the detector returns qualifies=false and "
                "classification=UNSUCCESSFUL_SEARCH even though unread members "
                "also lack WITNESS, so a true-by-luck remainder cannot discharge "
                "proof_of_impossibility."
            ),
            "verbatim": (
                f"qualifies={incomplete['qualifies']} "
                f"classification={incomplete['classification']} "
                f"unvisited={incomplete['unvisited']} "
                f"omniscient_witness_in_unvisited="
                f"{incomplete['omniscient_witness_in_unvisited']}"
            ),
        },
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["--both-states"] or args == ["--all"]:
        doc = both_states()
        print(json.dumps(doc, sort_keys=True, default=str))
        nc = doc["negative_control"]["verbatim"]
        print(f"NEGATIVE_CONTROL {nc}")
        if not doc["both_directions_ok"]:
            print("FAILED:CNL-0073-proof both-states")
            return 1
        print(
            "SUCCESS:CNL-0073-proof both-states "
            "incomplete=UNSUCCESSFUL_SEARCH exhaustive=EXHAUSTIVE_REFUTATION"
        )
        return 0
    if len(args) == 1 and args[0] in EXPECTED:
        row = run_named(args[0])
        print(json.dumps(row, sort_keys=True, default=str))
        want_q, want_c = EXPECTED[args[0]]
        if row["qualifies"] != want_q or row["classification"] != want_c:
            print(f"FAILED:CNL-0073-proof {args[0]} got {row['classification']}")
            return 1
        tag = "PROOF_DISCHARGED" if row["qualifies"] else "PROOF_REJECTED"
        print(f"{tag} {args[0]} {row['classification']}")
        return 0
    print("FAILED:CNL-0073-proof usage proof.py --both-states | <fixture>")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
