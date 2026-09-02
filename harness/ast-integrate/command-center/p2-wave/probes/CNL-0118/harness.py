#!/usr/bin/env python3
"""Deterministic scripted-participant council for CNL-0118.

Production tools/council is absent on this worktree. This harness is the
design-unit executable: structured actions are checked at the point of use
against the role matrix; a mid-vote death seats a replacement that inherits
the role and not the predecessor's ballot; the run always reaches a named
terminal state. A logical tick clock is the timeout domain (no wall-clock
in the event log).
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
STRUCTURED_ACTIONS = frozenset(
    {"SPEAK", "PROPOSE", "CRITIQUE", "VOTE", "VETO", "ABSTAIN"}
)


def load_json(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def canonical_bytes(obj: Any) -> bytes:
    return (
        json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    ).encode("utf-8")


def evaluate_action(role: dict, action: str) -> tuple[str, str]:
    """Point-of-use mandate check. Payload text is not consulted."""
    if action not in STRUCTURED_ACTIONS:
        return "REJECT", "unknown-action"
    forbidden = list(role.get("forbidden") or [])
    if action in forbidden:
        return "REJECT", "forbidden"
    if action == "VOTE" and not role.get("may_vote", False):
        return "REJECT", "no-vote-right"
    if action == "VETO" and not role.get("may_veto", False):
        return "REJECT", "no-veto-right"
    allowed = set(role.get("permissions") or [])
    allowed |= set(role.get("rights") or [])
    allowed |= set(role.get("obligations") or [])
    if action == "VOTE" and role.get("may_vote"):
        allowed.add("VOTE")
    if action == "ABSTAIN" and role.get("may_vote"):
        allowed.add("ABSTAIN")
    if action == "VETO" and role.get("may_veto"):
        allowed.add("VETO")
    if action in allowed:
        return "ALLOW", "in-mandate"
    return "REJECT", "not-in-mandate"


class Clock:
    def __init__(self) -> None:
        self.tick = 0

    def step(self) -> int:
        self.tick += 1
        return self.tick


def _seat_map(script: dict) -> dict[str, dict]:
    return {s["seat_id"]: dict(s) for s in script["seats"]}


def run(
    *,
    enforce: bool = True,
    hang_instead_of_replace: bool = False,
    roles: dict | None = None,
    script: dict | None = None,
) -> dict:
    roles = roles if roles is not None else load_json("roles.json")
    script = script if script is not None else load_json("script.json")
    seats = _seat_map(script)
    replacement = dict(script["replacement"])
    timeout = int(script["declared_timeout_ticks"])
    clock = Clock()
    events: list[dict] = []
    ballots: dict[str, str] = {}
    terminal = "RUNNING"

    def emit(kind: str, **fields: Any) -> dict:
        row = {"tick": clock.step(), "kind": kind, **fields}
        events.append(row)
        return row

    def role_of(seat_id: str) -> dict:
        return roles[seats[seat_id]["role"]]

    def attempt(seat_id: str, action: str, payload: dict | None = None) -> str:
        if not enforce:
            verdict, reason = "ALLOW", "enforcement-stripped"
        else:
            verdict, reason = evaluate_action(role_of(seat_id), action)
        emit(
            "TURN",
            seat_id=seat_id,
            role=seats[seat_id]["role"],
            action=action,
            verdict=verdict,
            reason=reason,
            payload=payload or {},
        )
        return verdict

    for turn in script["turns"]:
        attempt(turn["seat_id"], turn["action"], turn.get("payload") or {})

    vote_round = script["vote_round"]
    replaced = False
    for seat_id in vote_round["order"]:
        seat = seats[seat_id]
        if seat.get("die_mid_vote"):
            emit(
                "SEAT_DEAD",
                seat_id=seat_id,
                role=seat["role"],
                phase="vote_round",
                intended_ballot=seat.get("intended_ballot"),
                ballot_committed=False,
            )
            if hang_instead_of_replace:
                # Wall-clock stall longer than declared_hang_timeout_s.
                # The probe wraps this call and must reach REPLACEMENT_TIMEOUT
                # rather than waiting out the sleep.
                time.sleep(0.8)
                terminal = "HUNG_MUTANT_RETURNED"
                emit("TERMINAL", terminal_state=terminal)
                break
            pred = replacement["predecessor"]
            if pred != seat_id:
                terminal = "REPLACEMENT_MISCONFIGURED"
                emit("TERMINAL", terminal_state=terminal)
                break
            new_id = replacement["seat_id"]
            new_role = replacement["role"]
            seats[new_id] = {
                "seat_id": new_id,
                "role": new_role,
                "replaces": seat_id,
                "inherited_ballot": False,
                "inherited_position": False,
            }
            emit(
                "SEAT_REPLACED",
                predecessor=seat_id,
                seat_id=new_id,
                role=new_role,
                inherited_ballot=False,
                inherited_position=False,
                predecessor_intended_ballot=seat.get("intended_ballot"),
            )
            verdict = attempt(new_id, "VOTE", {"ballot": replacement["ballot"]})
            if verdict == "ALLOW":
                ballots[new_id] = replacement["ballot"]
                emit(
                    "BALLOT_COMMITTED",
                    seat_id=new_id,
                    ballot=replacement["ballot"],
                    inherited=False,
                )
            replaced = True
            continue
        ballot = vote_round["ballots"][seat_id]
        verdict = attempt(seat_id, "VOTE", {"ballot": ballot})
        if verdict == "ALLOW":
            ballots[seat_id] = ballot
            emit(
                "BALLOT_COMMITTED",
                seat_id=seat_id,
                ballot=ballot,
                inherited=False,
            )

    if terminal == "RUNNING":
        if clock.tick > timeout:
            terminal = "REPLACEMENT_TIMEOUT"
        elif not replaced:
            terminal = "COMPLETED_NO_REPLACEMENT"
        else:
            terminal = "COMPLETED_AFTER_REPLACEMENT"
        emit("TALLY", ballots=dict(ballots), n=len(ballots))
        emit("TERMINAL", terminal_state=terminal)

    rejections = [e for e in events if e.get("kind") == "TURN" and e.get("verdict") == "REJECT"]
    violator = "carol"
    compliant = "bob"
    mention = "erin"
    dying = "dave"
    repl = replacement["seat_id"]
    v_rej = [e for e in rejections if e["seat_id"] == violator]
    c_rej = [e for e in rejections if e["seat_id"] == compliant]
    m_rej = [e for e in rejections if e["seat_id"] == mention]
    repl_ballot = ballots.get(repl)
    dying_intended = seats[dying].get("intended_ballot")
    inherited = bool(
        repl in ballots and dying_intended is not None and repl_ballot == dying_intended
    )
    return {
        "enforce": enforce,
        "events": events,
        "ballots": dict(ballots),
        "terminal_state": terminal,
        "ticks": clock.tick,
        "timeout_ticks": timeout,
        "within_declared_timeout": clock.tick <= timeout and terminal != "REPLACEMENT_TIMEOUT",
        "hung": False,
        "violator_caught": len(v_rej) > 0,
        "compliant_flagged": len(c_rej) > 0,
        "mention_flagged": len(m_rej) > 0,
        "violator_rejection_count": len(v_rej),
        "compliant_rejection_count": len(c_rej),
        "mention_rejection_count": len(m_rej),
        "ballots_committed": len(ballots),
        "dying_seat_ballot_present": dying in ballots,
        "replacement_inherited_predecessor_ballot": inherited,
        "replacement_ballot": repl_ballot,
        "dying_intended_ballot": dying_intended,
    }


def two_run_identical() -> tuple[bool, bytes, bytes]:
    a = canonical_bytes(run()["events"])
    b = canonical_bytes(run()["events"])
    return a == b, a, b


def expected_turn_verdicts(roles: dict | None = None, script: dict | None = None) -> list[dict]:
    """Fixture-only tabulation of pre-vote turns (no runtime summary)."""
    roles = roles if roles is not None else load_json("roles.json")
    script = script if script is not None else load_json("script.json")
    seats = _seat_map(script)
    rows = []
    for turn in script["turns"]:
        role = roles[seats[turn["seat_id"]]["role"]]
        verdict, reason = evaluate_action(role, turn["action"])
        rows.append(
            {
                "seat_id": turn["seat_id"],
                "action": turn["action"],
                "verdict": verdict,
                "reason": reason,
            }
        )
    return rows
