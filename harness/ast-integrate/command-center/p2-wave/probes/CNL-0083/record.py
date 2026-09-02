#!/usr/bin/env python3
"""Proof-of-impossibility record: five mandatory fields + visit ledger.

The boolean metric proof_of_impossibility is true only when:
  1. claim, search_space, methods, resource_limit, refuting_observation
     are all present and non-empty
  2. search_space is a finite closed set with explicit members
  3. the visit ledger covers every member (independent recount)
  4. the predicate holds for NO member (the claimed absence is true)
  5. the named refuting observation is in-principle observable in that
     same space (so the record is falsifiable, not circular)

An unsuccessful search (partial coverage) cannot set the metric true.
"""
from __future__ import annotations

from typing import Any

MANDATORY = (
    "claim",
    "search_space",
    "methods",
    "resource_limit",
    "refuting_observation",
)


def _nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return True


def apply_predicate(predicate: dict[str, Any], member: Any) -> bool:
    kind = predicate.get("kind")
    if kind == "int_square_eq":
        rhs = predicate["rhs"]
        return int(member) * int(member) == int(rhs)
    raise ValueError(f"unknown predicate kind {kind!r}")


def validate(record: dict[str, Any], visits: list[dict[str, Any]]) -> dict[str, Any]:
    missing = [f for f in MANDATORY if not _nonempty(record.get(f))]
    if missing:
        return {
            "metric": False,
            "fires": False,
            "reason": "missing-mandatory:" + ",".join(missing),
            "coverage": 0,
            "cardinality": 0,
        }

    space = record["search_space"]
    if not isinstance(space, dict) or space.get("kind") != "finite-closed-set":
        return {
            "metric": False,
            "fires": False,
            "reason": "search-space-not-finite-closed-set",
            "coverage": 0,
            "cardinality": 0,
        }
    members = space.get("members")
    if not isinstance(members, list) or not members:
        return {
            "metric": False,
            "fires": False,
            "reason": "empty-search-space",
            "coverage": 0,
            "cardinality": 0,
        }
    if len(set(members)) != len(members):
        return {
            "metric": False,
            "fires": False,
            "reason": "duplicate-members",
            "coverage": 0,
            "cardinality": len(members),
        }

    methods = record["methods"]
    if not isinstance(methods, list) or not methods:
        return {
            "metric": False,
            "fires": False,
            "reason": "methods-empty",
            "coverage": 0,
            "cardinality": len(members),
        }
    for m in methods:
        if not isinstance(m, dict) or not _nonempty(m.get("name")) or not _nonempty(m.get("output")):
            return {
                "metric": False,
                "fires": False,
                "reason": "method-missing-name-or-output",
                "coverage": 0,
                "cardinality": len(members),
            }

    limit = record["resource_limit"]
    if not isinstance(limit, dict) or not _nonempty(limit.get("status")):
        return {
            "metric": False,
            "fires": False,
            "reason": "resource-limit-unspecified",
            "coverage": 0,
            "cardinality": len(members),
        }

    ro = record["refuting_observation"]
    if not isinstance(ro, dict) or not _nonempty(ro.get("description")):
        return {
            "metric": False,
            "fires": False,
            "reason": "refuting-observation-missing",
            "coverage": 0,
            "cardinality": len(members),
        }
    if ro.get("circular") is True or ro.get("observable_in_search_space") is not True:
        return {
            "metric": False,
            "fires": False,
            "reason": "refuting-observation-unobservable-or-circular",
            "coverage": 0,
            "cardinality": len(members),
        }

    if not isinstance(visits, list):
        return {
            "metric": False,
            "fires": False,
            "reason": "visit-ledger-absent",
            "coverage": 0,
            "cardinality": len(members),
        }
    visited = []
    for row in visits:
        if not isinstance(row, dict) or "member" not in row:
            return {
                "metric": False,
                "fires": False,
                "reason": "visit-row-malformed",
                "coverage": 0,
                "cardinality": len(members),
            }
        visited.append(row["member"])
    visited_set = set(visited)
    member_set = set(members)
    coverage = len(visited_set & member_set)
    extra = visited_set - member_set
    if extra:
        return {
            "metric": False,
            "fires": False,
            "reason": "visit-outside-declared-space",
            "coverage": coverage,
            "cardinality": len(member_set),
            "extra": sorted(extra, key=str),
        }
    if coverage < len(member_set):
        unseen = sorted(member_set - visited_set, key=str)
        return {
            "metric": False,
            "fires": False,
            "reason": "unsuccessful-search-incomplete-coverage",
            "coverage": coverage,
            "cardinality": len(member_set),
            "unseen": unseen,
        }

    predicate = record.get("predicate")
    if not isinstance(predicate, dict) or "kind" not in predicate:
        return {
            "metric": False,
            "fires": False,
            "reason": "predicate-unbound",
            "coverage": coverage,
            "cardinality": len(member_set),
        }
    hits = [x for x in members if apply_predicate(predicate, x)]
    if hits:
        return {
            "metric": False,
            "fires": False,
            "reason": "counterexample-present",
            "coverage": coverage,
            "cardinality": len(member_set),
            "hits": hits,
        }
    if limit.get("space_exhausted_before_limit") is not True:
        return {
            "metric": False,
            "fires": False,
            "reason": "space-not-marked-exhausted",
            "coverage": coverage,
            "cardinality": len(member_set),
        }
    return {
        "metric": True,
        "fires": True,
        "reason": "exhaustive-enumeration-no-counterexample",
        "coverage": coverage,
        "cardinality": len(member_set),
    }


def independent_recount(members: list[Any], visits: list[dict[str, Any]], rhs: int) -> dict[str, Any]:
    """Reviewer path: re-tabulate coverage and squares from the ledger, not the author's reason string."""
    visited = [row["member"] for row in visits]
    coverage = len(set(visited) & set(members))
    squares = {int(x): int(x) * int(x) for x in members}
    hits = [x for x, sq in squares.items() if sq == int(rhs)]
    complete = coverage == len(set(members)) and len(set(members)) == len(members)
    return {
        "coverage": coverage,
        "cardinality": len(members),
        "complete": complete,
        "squares": squares,
        "hits": hits,
        "impossibility_holds_on_enumerated_members": len(hits) == 0,
        "proof": complete and len(hits) == 0,
    }
