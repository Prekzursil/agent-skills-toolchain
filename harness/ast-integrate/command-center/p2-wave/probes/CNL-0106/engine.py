#!/usr/bin/env python3
"""Executable council-preset engine for CNL-0106.

A bound oracle FAIL overrides majority (including unanimous YES). An unbound
FAIL cannot veto. When the disputed artifact is the test itself, the oracle is
demoted from gate to exhibit until an evidence-clerk confirms load-bearing.
"""
from __future__ import annotations

from typing import Any

NOT_YES = "NOT-YES"
ORACLE_CHALLENGE = "ORACLE-CHALLENGE"
ORACLE_INCONCLUSIVE = "ORACLE-INCONCLUSIVE"
YES = "YES"
NO = "NO"

SIBLING_SOURCE = (
    "catalog-cited reconstruction on this worktree; "
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json Path.is_file() is false"
)


def majority(ballots: list[str]) -> str:
    yes = sum(1 for b in ballots if b == YES)
    no = sum(1 for b in ballots if b == NO)
    if yes > no:
        return YES
    if no > yes:
        return NO
    return NOT_YES


def adjudicate(
    *,
    ballots: list[str],
    oracle_status: str,
    oracle_command: str,
    binding_commands: list[str],
    subject_kind: str,
    challenged: bool = False,
    clerk_verdict: str | None = None,
) -> dict[str, Any]:
    """Recorded outcome, not the raw vote.

    The vote is always preserved as an exhibit. It becomes the outcome only
    when the oracle is not a live gate, or when the gate PASSes.
    """
    vote = majority(ballots)
    bound = oracle_command in binding_commands
    subject_is_test = subject_kind == "test"
    demote = subject_is_test or challenged

    if demote:
        if clerk_verdict == "CONFIRMED-LOAD-BEARING":
            if bound and oracle_status == "FAIL":
                return {
                    "outcome": NOT_YES,
                    "vote": vote,
                    "oracle_role": "gate-after-clerk",
                    "bound": bound,
                    "reason": (
                        "clerk confirmed the disputed test as load-bearing; "
                        "bound FAIL overrides majority"
                    ),
                }
            if bound and oracle_status == "PASS":
                return {
                    "outcome": vote,
                    "vote": vote,
                    "oracle_role": "gate-after-clerk",
                    "bound": bound,
                    "reason": "clerk confirmed; oracle PASS; vote stands",
                }
            return {
                "outcome": vote,
                "vote": vote,
                "oracle_role": "exhibit",
                "bound": bound,
                "reason": "clerk confirmed but oracle not a bound FAIL",
            }
        if clerk_verdict == "REJECTED-AS-ORACLE":
            return {
                "outcome": vote,
                "vote": vote,
                "oracle_role": "void-rejected",
                "bound": bound,
                "reason": (
                    "clerk rejected the test as oracle (flake, wrong subject, "
                    "or tautology); vote stands"
                ),
            }
        return {
            "outcome": ORACLE_CHALLENGE,
            "vote": vote,
            "oracle_role": "exhibit",
            "bound": bound,
            "reason": (
                "subject_kind=test or oracle_challenge filed: FAIL does not "
                "override until evidence-clerk (P50) confirms load-bearing"
            ),
        }

    if not bound:
        return {
            "outcome": vote,
            "vote": vote,
            "oracle_role": "void-unbound",
            "bound": False,
            "reason": (
                "unbound command cannot veto or confirm; CNL-0068 converse "
                "(irrelevant failing test must not veto a sound decision)"
            ),
        }

    if oracle_status == "FAIL":
        return {
            "outcome": NOT_YES,
            "vote": vote,
            "oracle_role": "gate",
            "bound": True,
            "reason": "bound FAIL overrides majority including unanimous YES",
        }
    if oracle_status == "PASS":
        return {
            "outcome": vote,
            "vote": vote,
            "oracle_role": "gate",
            "bound": True,
            "reason": "bound PASS; vote stands",
        }
    return {
        "outcome": ORACLE_INCONCLUSIVE,
        "vote": vote,
        "oracle_role": "gate",
        "bound": True,
        "reason": "bound oracle ERROR/NOT-RUN cannot record YES",
    }


def _role_ids(preset: dict) -> frozenset[str]:
    return frozenset(str(r["id"]) for r in preset.get("roles") or [])


def _protocol_ids(preset: dict) -> frozenset[str]:
    return frozenset(str(p["id"]) for p in preset.get("protocol_schedule") or [])


def profile(preset: dict) -> dict[str, Any]:
    oracle = preset.get("oracle") or {}
    stopping = preset.get("stopping") or {}
    voting = preset.get("voting") or {}
    return {
        "roles": sorted(_role_ids(preset)),
        "protocols": sorted(_protocol_ids(preset)),
        "voting_rule": str(voting.get("rule") or ""),
        "stopping_expression": str(stopping.get("expression") or ""),
        "max_rounds": int(stopping.get("max_rounds") or 0),
        "fail_overrides_majority": bool(oracle.get("fail_overrides_majority")),
        "anonymity": bool(preset.get("anonymity")),
        "rebuttal": bool(preset.get("rebuttal")),
    }


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def distance(pa: dict[str, Any], pb: dict[str, Any]) -> float:
    d_roles = 1.0 - jaccard(frozenset(pa["roles"]), frozenset(pb["roles"]))
    d_prot = 1.0 - jaccard(frozenset(pa["protocols"]), frozenset(pb["protocols"]))
    d_vote = 0.0 if pa["voting_rule"] == pb["voting_rule"] else 1.0
    d_stop = 0.0 if pa["stopping_expression"] == pb["stopping_expression"] else 1.0
    d_oracle = (
        0.0
        if pa["fail_overrides_majority"] == pb["fail_overrides_majority"]
        else 1.0
    )
    d_anon = 0.0 if pa["anonymity"] == pb["anonymity"] else 1.0
    d_reb = 0.0 if pa["rebuttal"] == pb["rebuttal"] else 1.0
    return d_roles + d_prot + d_vote + d_stop + d_oracle + d_anon + d_reb


def nearest_sibling(
    preset: dict, siblings: list[dict]
) -> dict[str, Any]:
    pp = profile(preset)
    ranked: list[tuple[float, str, dict]] = []
    for sib in siblings:
        if sib.get("id") == preset.get("id"):
            continue
        d = distance(pp, profile(sib))
        ranked.append((d, str(sib.get("id") or ""), sib))
    if not ranked:
        raise ValueError("no siblings to compare")
    ranked.sort(key=lambda t: (t[0], t[1]))
    best_d, best_id, best = ranked[0]
    diffs = _field_diffs(pp, profile(best))
    return {
        "id": best_id,
        "distance": best_d,
        "ranked": [{"id": i, "distance": d} for d, i, _ in ranked],
        "measurable_diffs": diffs,
        "source": SIBLING_SOURCE,
        "named_explicitly": True,
        "sibling_profile": profile(best),
        "preset_profile": pp,
    }


def _field_diffs(pa: dict[str, Any], pb: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for key in (
        "roles",
        "protocols",
        "voting_rule",
        "stopping_expression",
        "max_rounds",
        "fail_overrides_majority",
        "anonymity",
        "rebuttal",
    ):
        if pa.get(key) != pb.get(key):
            out.append({"field": key, "preset": pa.get(key), "sibling": pb.get(key)})
    return out


def instantiate(preset: dict, task: dict) -> dict[str, Any]:
    """Apply preset + fixture task → roster, schedule, voting, stopping."""
    subject = str(task.get("subject_kind") or "code")
    seats: list[dict[str, Any]] = []
    for role in preset.get("roles") or []:
        when = str(role.get("seated_when") or "always")
        seated = when == "always" or when == subject or (
            when == "oracle-challenge" and subject == "test"
        )
        if not seated:
            continue
        seats.append(
            {
                "role_id": role["id"],
                "title": role["title"],
                "voting": bool(role.get("voting")),
                "bind_oracle": bool(role.get("bind_oracle")),
            }
        )

    if subject == "test":
        schedule = [
            {"id": "bind-oracle", "purpose": "declare load-bearing commands before talk"},
            {"id": "P46", "purpose": "independent review of the disputed test as artifact"},
            {
                "id": "P50",
                "purpose": "evidence-clerk examines flake vs wrong-subject vs tautology",
            },
            {"id": "tribunal-vote", "purpose": "majority of voting seats, recorded as exhibit"},
            {
                "id": "oracle-challenge-gate",
                "purpose": "FAIL does not override until clerk confirms load-bearing",
            },
            {"id": "record", "purpose": "persist transcript, vote, clerk verdict, outcome"},
        ]
        stopping = {
            **dict(preset.get("stopping") or {}),
            "on_oracle_fail": ORACLE_CHALLENGE,
            "expression": (
                "subject=test → oracle_fail does not halt as NOT-YES; "
                "P50 clerk must confirm or reject; unresolved → ORACLE-CHALLENGE"
            ),
        }
    else:
        schedule = [
            {"id": "bind-oracle", "purpose": "declare load-bearing commands before talk"},
            {"id": "P46", "purpose": "architecture/code review board deliberation"},
            {"id": "tribunal-vote", "purpose": "majority of voting seats, recorded as exhibit"},
            {
                "id": "oracle-gate",
                "purpose": "bound FAIL overrides majority; unbound FAIL is void",
            },
            {"id": "record", "purpose": "persist transcript, vote, oracle, outcome"},
        ]
        stopping = dict(preset.get("stopping") or {})

    binding = dict(task.get("oracle_binding") or {})
    return {
        "task_id": task.get("id"),
        "subject_kind": subject,
        "roster": seats,
        "voting_seats": [s["role_id"] for s in seats if s["voting"]],
        "protocol_schedule": schedule,
        "voting": dict(preset.get("voting") or {}),
        "stopping": stopping,
        "oracle": dict(preset.get("oracle") or {}),
        "oracle_binding": binding,
    }
