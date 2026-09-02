"""Eviction, replacement, and contribution retention (IMP-0275 / TST-0278)."""
from __future__ import annotations

import copy
from typing import Any

RULE_ID = "R-EVICT-RETAIN"


def make_run(
    dave_last_activity_at: int = 0,
    carol_failures: int = 0,
) -> dict[str, Any]:
    now = 200
    participants = [
        {"id": "alice", "role": "chair", "last_activity_at": now, "failures": 0, "seated": True},
        {"id": "bob", "role": "advocate", "last_activity_at": now, "failures": 0, "seated": True},
        {"id": "carol", "role": "critic", "last_activity_at": now, "failures": carol_failures, "seated": True},
        {"id": "dave", "role": "scribe", "last_activity_at": dave_last_activity_at, "failures": 0, "seated": True},
    ]
    contributions = []
    for pid in ("alice", "bob", "carol", "dave"):
        contributions.append({"id": f"v-r1-{pid}", "author_id": pid, "kind": "vote", "round": 1, "vote": "yes"})
        contributions.append({"id": f"i-r1-{pid}", "author_id": pid, "kind": "idea", "round": 1, "text": f"idea-{pid}"})
        contributions.append({"id": f"v-r2-{pid}", "author_id": pid, "kind": "vote", "round": 2, "vote": "yes"})
    ballots = [c for c in contributions if c["kind"] == "vote"]
    run = {
        "now": now,
        "policy": {"inactivity_idle_for": 50, "failure_threshold": 3, "quorum_min": 3},
        "participants": participants,
        "contributions": contributions,
        "ballots": ballots,
        "seats": {
            "seat-chair": {"active_occupant_id": "alice"},
            "seat-advocate": {"active_occupant_id": "bob"},
            "seat-critic": {"active_occupant_id": "carol"},
            "seat-scribe": {"active_occupant_id": "dave"},
        },
        "round": 2,
    }
    run["quorum"] = compute_quorum(run)
    run["tally"] = compute_tally(run)
    return run


def evaluate_triggers(person: dict[str, Any], now: int, policy: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    idle_for = int(policy.get("inactivity_idle_for") or 50)
    fail_n = int(policy.get("failure_threshold") or 3)
    if int(person.get("failures") or 0) >= fail_n:
        reasons.append("repeated_failure")
    elif now - int(person.get("last_activity_at") or 0) >= idle_for:
        reasons.append("inactivity")
    return {"due": bool(reasons), "reasons": reasons}


def find_eviction_candidates(run: dict[str, Any]) -> list[dict[str, Any]]:
    now = int(run["now"])
    policy = run["policy"]
    out = []
    for p in run["participants"]:
        if not p.get("seated"):
            continue
        trig = evaluate_triggers(p, now, policy)
        if trig["due"]:
            out.append({"id": p["id"], "reasons": trig["reasons"]})
    return out


def compute_quorum(run: dict[str, Any]) -> dict[str, Any]:
    seated = [p for p in run["participants"] if p.get("seated")]
    evicted = [p for p in run["participants"] if not p.get("seated")]
    n = len(seated)
    minimum = int((run.get("policy") or {}).get("quorum_min") or 3)
    ok = n >= minimum
    return {
        "seated_count": n,
        "seated_ids": [p["id"] for p in seated],
        "evicted_ids": [p["id"] for p in evicted],
        "ok": ok,
        "void": not ok,
        "minimum": minimum,
    }


def evict(run: dict[str, Any], pid: str, replacement: dict[str, Any] | None = None) -> dict[str, Any]:
    out = copy.deepcopy(run)
    for p in out["participants"]:
        if p["id"] == pid:
            p["seated"] = False
    if replacement:
        rid = replacement["id"]
        out["participants"].append(
            {
                "id": rid,
                "role": replacement.get("role") or "replacement",
                "last_activity_at": out["now"],
                "failures": 0,
                "seated": True,
            }
        )
        for seat, rec in out.get("seats", {}).items():
            if rec.get("active_occupant_id") == pid:
                rec["active_occupant_id"] = rid
    out["quorum"] = compute_quorum(out)
    out["tally"] = compute_tally(out)
    return out


def record_failure(run: dict[str, Any], pid: str, now: int) -> dict[str, Any]:
    out = copy.deepcopy(run)
    out["now"] = now
    for p in out["participants"]:
        if p["id"] == pid:
            p["failures"] = int(p.get("failures") or 0) + 1
            p["last_activity_at"] = now
    return out


def contribution_census(run: dict[str, Any]) -> dict[str, Any]:
    by_author: dict[str, list[str]] = {}
    seen: set[str] = set()
    for c in run.get("contributions") or []:
        aid = str(c.get("author_id") or "")
        cid = str(c.get("id") or "")
        by_author.setdefault(aid, []).append(cid)
        seen.add(cid)
    return {"by_author": by_author, "orphan_ids": [], "ids": sorted(seen)}


def compute_tally(run: dict[str, Any]) -> dict[str, Any]:
    seated = {p["id"] for p in run.get("participants") or [] if p.get("seated")}
    evicted = {p["id"] for p in run.get("participants") or [] if not p.get("seated")}
    closed_yes = [
        c
        for c in run.get("contributions") or []
        if c.get("kind") == "vote" and int(c.get("round") or 0) == 1
    ]
    open_votes = [
        c
        for c in run.get("contributions") or []
        if c.get("kind") == "vote" and int(c.get("round") or 0) == 2
    ]
    included = [c for c in open_votes if c.get("author_id") in seated]
    excluded = [c for c in open_votes if c.get("author_id") in evicted]
    return {
        "rule_id": RULE_ID,
        "closed_rounds": {
            "1": {
                "counts": {"yes": sum(1 for c in closed_yes if c.get("vote") == "yes")},
                "includes_evicted": sorted(evicted),
            }
        },
        "open_round": {
            "counts": {"yes": sum(1 for c in included if c.get("vote") == "yes")},
            "included": included,
            "excluded_evicted": excluded,
        },
    }


def census_retention_check(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    if "by_author" not in before:
        before = contribution_census(before)
    if "by_author" not in after:
        after = contribution_census(after)
    missing: list[str] = []
    remapped: list[str] = []
    after_owner: dict[str, str] = {}
    for author, ids in (after.get("by_author") or {}).items():
        for cid in ids:
            after_owner[cid] = author
    for author, ids in (before.get("by_author") or {}).items():
        have = set((after.get("by_author") or {}).get(author) or [])
        for cid in ids:
            if cid in have:
                continue
            if cid in after_owner and after_owner[cid] != author:
                remapped.append(cid)
            else:
                missing.append(cid)
    return {
        "ok": not missing and not remapped,
        "missing": missing,
        "remapped": remapped,
        "before": before,
        "after": after,
        "rule": RULE_ID,
    }


def vote_ledger(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "ballots": list(state.get("ballots") or []),
        "active_occupants": {
            seat: rec.get("active_occupant_id") for seat, rec in (state.get("seats") or {}).items()
        },
    }


def ballot_count(state: dict[str, Any], occupant_id: str, round_n: int | list[int] | None = None) -> int:
    wanted: set[int] | None
    if round_n is None:
        wanted = None
    elif isinstance(round_n, (list, tuple, set)):
        wanted = {int(x) for x in round_n}
    else:
        wanted = {int(round_n)}
    n = 0
    for b in state.get("ballots") or []:
        if b.get("author_id") != occupant_id:
            continue
        if wanted is not None and int(b.get("round") or 0) not in wanted:
            continue
        n += 1
    return n


def replace_occupant(
    state: dict[str, Any],
    seat: str,
    replacement: dict[str, Any],
    *,
    reason: str,
    inherit_votes: bool = False,
) -> dict[str, Any]:
    out = copy.deepcopy(state)
    departed = (out.get("seats") or {}).get(seat, {}).get("active_occupant_id")
    rid = replacement.get("persona_id") or replacement.get("id")
    out.setdefault("seats", {}).setdefault(seat, {})["active_occupant_id"] = rid
    out.setdefault("replacements", []).append(
        {"seat": seat, "departed": departed, "replacement": rid, "reason": reason}
    )
    if inherit_votes and departed:
        inherited = []
        for b in list(out.get("ballots") or []):
            if b.get("author_id") == departed:
                cloned = dict(b)
                cloned["author_id"] = rid
                cloned["inherited"] = True
                inherited.append(cloned)
        out.setdefault("ballots", []).extend(inherited)
    return out
