"""Turn-by-turn runtime for DELIBERATIVE protocols with readable stops."""
from __future__ import annotations

from typing import Any

import stopping


def schedule(rec: dict[str, Any]) -> dict[str, Any]:
    rid = str(rec.get("id"))
    ok, why = stopping.is_readable(rec.get("stopping"))
    if not ok:
        return {
            "record_id": rid,
            "slug": rec.get("slug"),
            "executable": False,
            "missing_element": (
                "evaluator-readable stopping expression "
                "(AND/OR/NOT, ANY, ALL, weighted, or infix atom); "
                f"classifier={why}"
            ),
            "turns": None,
            "stop_sampled": None,
        }
    kind = _kind(rec)
    if kind == "round-robin":
        return _round_robin(rec)
    if kind == "fishbowl":
        return _fishbowl(rec)
    if kind == "consensus-conference":
        return _consensus(rec)
    if kind == "rotating-chair":
        return _rotating_chair(rec)
    if kind == "nominal-group-technique":
        return _ngt(rec)
    return {
        "record_id": rid,
        "slug": rec.get("slug"),
        "executable": False,
        "missing_element": f"no-turn-machine-for-kind:{kind}",
        "turns": None,
        "stop_sampled": None,
    }


def _kind(rec: dict[str, Any]) -> str:
    policy = rec.get("turn_policy")
    if isinstance(policy, dict) and isinstance(policy.get("kind"), str):
        return policy["kind"]
    if isinstance(policy, str):
        return "prose-turns"
    return str(rec.get("slug") or "unknown")


def _seats(ids: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "id": sid,
            "spoke_this_round": False,
            "has_chaired": False,
            "ballot": False,
            "weight": 1.0,
        }
        for sid in ids
    ]


def _round_robin(rec: dict[str, Any]) -> dict[str, Any]:
    seats = _seats(list(rec.get("seats") or ["A", "B", "C"]))
    max_rounds = int((rec.get("turn_policy") or {}).get("max_rounds") or 2)
    turns: list[dict[str, Any]] = []
    sampled: list[bool] = []
    rounds = 0
    while True:
        for seat in seats:
            seat["spoke_this_round"] = False
        rounds += 1
        for seat in seats:
            seat["spoke_this_round"] = True
            turns.append(
                {"round": rounds, "seat": seat["id"], "act": "speak"}
            )
        env = {"rounds": rounds, "seats": seats}
        hit = stopping.eval_expr(rec["stopping"], env)
        sampled.append(hit)
        if hit:
            break
        if rounds > max_rounds + 2:
            return _hang(rec, turns, sampled, "round-robin-failed-to-stop")
    return _ok(rec, turns, sampled, rounds)


def _fishbowl(rec: dict[str, Any]) -> dict[str, Any]:
    inner_ids = list(rec.get("inner") or ["A", "B"])
    outer_ids = list(rec.get("outer") or ["C", "D"])
    inner = _seats(inner_ids)
    outer = _seats(outer_ids)
    max_rounds = int((rec.get("turn_policy") or {}).get("max_rounds") or 2)
    turns: list[dict[str, Any]] = []
    sampled: list[bool] = []
    rounds = 0
    promotions = 0
    while True:
        rounds += 1
        for seat in inner:
            seat["spoke_this_round"] = True
            turns.append(
                {
                    "round": rounds,
                    "seat": seat["id"],
                    "ring": "inner",
                    "act": "speak",
                }
            )
        for seat in outer:
            turns.append(
                {
                    "round": rounds,
                    "seat": seat["id"],
                    "ring": "outer",
                    "act": "observe",
                }
            )
        if outer:
            promoted = outer.pop(0)
            demoted = inner.pop(0)
            inner.append(promoted)
            outer.append(demoted)
            promotions += 1
            turns.append(
                {
                    "round": rounds,
                    "seat": promoted["id"],
                    "act": "promote-to-inner",
                }
            )
        env = {
            "rounds": rounds,
            "promotions": promotions,
            "seats": inner + outer,
        }
        hit = stopping.eval_expr(rec["stopping"], env)
        sampled.append(hit)
        if hit:
            break
        if rounds > max_rounds + 2:
            return _hang(rec, turns, sampled, "fishbowl-failed-to-stop")
    return _ok(rec, turns, sampled, rounds)


def _consensus(rec: dict[str, Any]) -> dict[str, Any]:
    seats = _seats(list(rec.get("seats") or ["A", "B", "C"]))
    min_rounds = int((rec.get("turn_policy") or {}).get("min_rounds") or 2)
    turns: list[dict[str, Any]] = []
    sampled: list[bool] = []
    unresolved = 1
    rounds = 0
    while True:
        rounds += 1
        for seat in seats:
            turns.append(
                {"round": rounds, "seat": seat["id"], "act": "propose"}
            )
        if rounds == 1:
            turns.append(
                {"round": rounds, "seat": seats[1]["id"], "act": "object"}
            )
            unresolved = 1
        else:
            turns.append(
                {
                    "round": rounds,
                    "seat": seats[1]["id"],
                    "act": "withdraw-objection",
                }
            )
            unresolved = 0
        env = {
            "rounds": rounds,
            "unresolved_objections": unresolved,
            "seats": seats,
        }
        hit = stopping.eval_expr(rec["stopping"], env)
        sampled.append(hit)
        if hit:
            break
        if rounds > min_rounds + 4:
            return _hang(rec, turns, sampled, "consensus-failed-to-stop")
    return _ok(rec, turns, sampled, rounds)


def _rotating_chair(rec: dict[str, Any]) -> dict[str, Any]:
    seats = _seats(list(rec.get("seats") or ["A", "B", "C"]))
    n = len(seats)
    turns: list[dict[str, Any]] = []
    sampled: list[bool] = []
    rounds = 0
    while True:
        chair = seats[rounds % n]
        rounds += 1
        chair["has_chaired"] = True
        turns.append(
            {"round": rounds, "seat": chair["id"], "act": "open-as-chair"}
        )
        for seat in seats:
            if seat is chair:
                continue
            seat["spoke_this_round"] = True
            turns.append(
                {"round": rounds, "seat": seat["id"], "act": "speak"}
            )
        env = {"rounds": rounds, "seats": seats}
        hit = stopping.eval_expr(rec["stopping"], env)
        sampled.append(hit)
        if hit:
            break
        if rounds > n + 2:
            return _hang(rec, turns, sampled, "rotating-chair-failed-to-stop")
    return _ok(rec, turns, sampled, rounds)


def _ngt(rec: dict[str, Any]) -> dict[str, Any]:
    seats = _seats(list(rec.get("seats") or ["A", "B", "C"]))
    phases = list(
        (rec.get("turn_policy") or {}).get("phases")
        or ["silent_generate", "round_robin_share", "clarify", "rank"]
    )
    turns: list[dict[str, Any]] = []
    sampled: list[bool] = []
    ballots = 0
    phase = ""
    for idx, phase in enumerate(phases, start=1):
        if phase == "silent_generate":
            for seat in seats:
                turns.append(
                    {"round": idx, "phase": phase, "seat": seat["id"], "act": "write"}
                )
        elif phase == "round_robin_share":
            for seat in seats:
                turns.append(
                    {"round": idx, "phase": phase, "seat": seat["id"], "act": "share"}
                )
        elif phase == "clarify":
            for seat in seats:
                turns.append(
                    {
                        "round": idx,
                        "phase": phase,
                        "seat": seat["id"],
                        "act": "clarify",
                    }
                )
        elif phase == "rank":
            for seat in seats:
                seat["ballot"] = True
                ballots += 1
                turns.append(
                    {
                        "round": idx,
                        "phase": phase,
                        "seat": seat["id"],
                        "act": "ballot",
                    }
                )
        env = {
            "rounds": idx,
            "phase": phase,
            "ballots_cast": ballots,
            "seats": seats,
        }
        hit = stopping.eval_expr(rec["stopping"], env)
        sampled.append(hit)
        if hit:
            return _ok(rec, turns, sampled, idx)
    return _hang(rec, turns, sampled, "ngt-failed-to-stop")


def _ok(
    rec: dict[str, Any],
    turns: list[dict[str, Any]],
    sampled: list[bool],
    stop_round: int,
) -> dict[str, Any]:
    return {
        "record_id": rec.get("id"),
        "slug": rec.get("slug"),
        "executable": True,
        "missing_element": None,
        "turns": turns,
        "turn_count": len(turns),
        "stop_sampled": sampled,
        "stopped_after_round": stop_round,
        "stop_was_false_before_end": False in sampled[:-1] if len(sampled) > 1 else False,
        "stop_true_at_end": bool(sampled and sampled[-1]),
    }


def _hang(
    rec: dict[str, Any],
    turns: list[dict[str, Any]],
    sampled: list[bool],
    why: str,
) -> dict[str, Any]:
    return {
        "record_id": rec.get("id"),
        "slug": rec.get("slug"),
        "executable": False,
        "missing_element": why,
        "turns": turns,
        "stop_sampled": sampled,
    }
