#!/usr/bin/env python3
"""Point-of-use role mandate kernel for TST-0279.

Production `tools/council/roles/mandate.py` (IMP-0280) and
`tools/council/simulate.py` (TST-0257) are absent on this worktree. This
kernel is the runtime the unit actually executes: every speak/vote/veto/
tool/source/incompatible-role check happens at the call site, not in a
prompt string.

A role that exists only as prompt text has no Mandate record and is
reported UNENFORCED.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Optional


# Actions the catalog names at :10925 (permissions, tool/source access,
# speaking, vote, veto) plus judge/propose/critique/synthesize so the
# proposer+judge dual-hat is a real seating check, not a comment.
ACTIONS: tuple[str, ...] = (
    "speak",
    "propose",
    "critique",
    "synthesize",
    "vote",
    "veto",
    "judge",
    "use_tool:draft",
    "use_tool:exec",
    "read_source:brief",
    "read_source:hidden",
)

# Same-seat pairs the catalog uses as the incompatible-role example
# (proposer judging its own proposal; critic voting its own objection).
INCOMPATIBLE_PAIRS: FrozenSet[FrozenSet[str]] = frozenset(
    {
        frozenset({"proposer", "judge"}),
        frozenset({"critic", "judge"}),
        frozenset({"proposer", "synthesizer"}),
        frozenset({"guardian", "proposer"}),
    }
)

PROMPT_ONLY_ROLE = "prompt_scribe"


@dataclass(frozen=True)
class Mandate:
    """Typed rights. Absence of a flag is a denial, not an unspecified maybe."""

    role_id: str
    speak: bool
    vote: bool
    veto: bool
    propose: bool
    critique: bool
    synthesize: bool
    judge: bool
    tools: FrozenSet[str]
    sources: FrozenSet[str]


def _m(
    role_id: str,
    *,
    speak: bool,
    vote: bool,
    veto: bool,
    propose: bool,
    critique: bool,
    synthesize: bool,
    judge: bool,
    tools: tuple[str, ...] = (),
    sources: tuple[str, ...] = ("brief",),
) -> Mandate:
    return Mandate(
        role_id=role_id,
        speak=speak,
        vote=vote,
        veto=veto,
        propose=propose,
        critique=critique,
        synthesize=synthesize,
        judge=judge,
        tools=frozenset(tools),
        sources=frozenset(sources),
    )


# Catalog-grounded template set: proposer/critic/synthesizer triad
# (CNL-0027), judge/juror (CNL-0029), observer, chair, guardian/veto
# (CNL-0024). Each cell is an explicit grant or an explicit denial.
REGISTRY: dict[str, Mandate] = {
    "proposer": _m(
        "proposer",
        speak=True,
        vote=True,
        veto=False,
        propose=True,
        critique=False,
        synthesize=False,
        judge=False,
        tools=("draft",),
        sources=("brief",),
    ),
    "critic": _m(
        "critic",
        speak=True,
        vote=True,
        veto=False,
        propose=False,
        critique=True,
        synthesize=False,
        judge=False,
        tools=(),
        sources=("brief",),
    ),
    "synthesizer": _m(
        "synthesizer",
        speak=True,
        vote=False,
        veto=False,
        propose=False,
        critique=False,
        synthesize=True,
        judge=False,
        tools=(),
        sources=("brief", "transcript"),
    ),
    "judge": _m(
        "judge",
        speak=True,
        vote=True,
        veto=False,
        propose=False,
        critique=False,
        synthesize=False,
        judge=True,
        tools=(),
        sources=("brief", "hidden"),
    ),
    "juror": _m(
        "juror",
        speak=True,
        vote=True,
        veto=False,
        propose=False,
        critique=False,
        synthesize=False,
        judge=False,
        tools=(),
        sources=("brief",),
    ),
    "observer": _m(
        "observer",
        speak=True,
        vote=False,
        veto=False,
        propose=False,
        critique=False,
        synthesize=False,
        judge=False,
        tools=(),
        sources=("brief",),
    ),
    "chair": _m(
        "chair",
        speak=True,
        vote=False,
        veto=False,
        propose=False,
        critique=False,
        synthesize=False,
        judge=False,
        tools=(),
        sources=("brief", "hidden"),
    ),
    "guardian": _m(
        "guardian",
        speak=True,
        vote=False,
        veto=True,
        propose=False,
        critique=False,
        synthesize=False,
        judge=False,
        tools=(),
        sources=("brief",),
    ),
}

TYPED_ROLES: tuple[str, ...] = tuple(sorted(REGISTRY))


def action_permitted(mandate: Mandate, action: str) -> bool:
    if action == "speak":
        return mandate.speak
    if action == "propose":
        return mandate.propose
    if action == "critique":
        return mandate.critique
    if action == "synthesize":
        return mandate.synthesize
    if action == "vote":
        return mandate.vote
    if action == "veto":
        return mandate.veto
    if action == "judge":
        return mandate.judge
    if action.startswith("use_tool:"):
        return action.split(":", 1)[1] in mandate.tools
    if action.startswith("read_source:"):
        return action.split(":", 1)[1] in mandate.sources
    raise ValueError(f"unknown action {action!r}")


@dataclass
class Attempt:
    seat_id: str
    role_id: str
    action: str
    expected: str  # PERMITTED | REFUSED | UNENFORCED
    observed: str
    reason: str
    veto_blocked: bool = False


@dataclass
class Seat:
    seat_id: str
    roles: FrozenSet[str]


class CouncilRuntime:
    """Single event path: seating validation then per-action gate."""

    def __init__(self, *, enforce: bool = True, mute_checks: FrozenSet[str] = frozenset()):
        self.enforce = enforce
        self.mute_checks = mute_checks
        self.seats: dict[str, Seat] = {}
        self.log: list[Attempt] = []
        self.pending_motion: Optional[str] = "motion-1"
        self.motion_status: str = "OPEN"
        self.refusals: list[Attempt] = []

    def seat(self, seat_id: str, *role_ids: str) -> dict:
        roles = frozenset(role_ids)
        if "incompatible" not in self.mute_checks:
            err = self._incompatible(roles)
            if err:
                rec = {
                    "ok": False,
                    "observed": "REFUSED",
                    "reason": err,
                    "seat_id": seat_id,
                    "roles": sorted(roles),
                }
                return rec
        self.seats[seat_id] = Seat(seat_id=seat_id, roles=roles)
        return {
            "ok": True,
            "observed": "PERMITTED",
            "reason": "seated",
            "seat_id": seat_id,
            "roles": sorted(roles),
        }

    def _incompatible(self, roles: FrozenSet[str]) -> Optional[str]:
        typed = {r for r in roles if r in REGISTRY}
        for pair in INCOMPATIBLE_PAIRS:
            if pair <= typed:
                a, b = sorted(pair)
                return f"incompatible-roles:{a}+{b}"
        return None

    def attempt(self, seat_id: str, action: str) -> Attempt:
        if action not in ACTIONS:
            raise ValueError(f"unknown action {action!r}")
        seat = self.seats.get(seat_id)
        if seat is None:
            att = Attempt(
                seat_id=seat_id,
                role_id="?",
                action=action,
                expected="REFUSED",
                observed="REFUSED",
                reason="no-such-seat",
            )
            self.log.append(att)
            self.refusals.append(att)
            return att

        # Prompt-only: no Mandate in REGISTRY for any of the seat's labels.
        typed = [r for r in sorted(seat.roles) if r in REGISTRY]
        if not typed:
            role_id = next(iter(sorted(seat.roles))) if seat.roles else PROMPT_ONLY_ROLE
            att = Attempt(
                seat_id=seat_id,
                role_id=role_id,
                action=action,
                expected="UNENFORCED",
                observed="UNENFORCED",
                reason="prompt-only-role-no-mandate-record",
            )
            self.log.append(att)
            return att

        # Dual-hat: union of grants. A denial on every typed role is a refusal.
        # (Seating already refused known incompatible pairs.)
        role_id = "+".join(typed)
        grants = [action_permitted(REGISTRY[r], action) for r in typed]
        allowed = any(grants)
        expected = "PERMITTED" if allowed else "REFUSED"

        if (not self.enforce) or (action.split(":", 1)[0] in self.mute_checks) or (
            action in self.mute_checks
        ):
            # Stripping the check still performs the action. Otherwise the
            # mute control could not prove a usurper veto actually landed.
            veto_blocked = False
            if action == "veto" and self.motion_status == "OPEN":
                self.motion_status = "BLOCKED"
                veto_blocked = True
            att = Attempt(
                seat_id=seat_id,
                role_id=role_id,
                action=action,
                expected=expected,
                observed="PERMITTED",
                reason="enforcement-stripped",
                veto_blocked=veto_blocked,
            )
            self.log.append(att)
            return att

        if not allowed:
            att = Attempt(
                seat_id=seat_id,
                role_id=role_id,
                action=action,
                expected="REFUSED",
                observed="REFUSED",
                reason=f"mandate-denies:{role_id}:{action}",
            )
            self.log.append(att)
            self.refusals.append(att)
            return att

        veto_blocked = False
        if action == "veto":
            if self.pending_motion is None or self.motion_status != "OPEN":
                att = Attempt(
                    seat_id=seat_id,
                    role_id=role_id,
                    action=action,
                    expected="PERMITTED",
                    observed="REFUSED",
                    reason="no-open-motion",
                )
                self.log.append(att)
                self.refusals.append(att)
                return att
            self.motion_status = "BLOCKED"
            veto_blocked = True

        att = Attempt(
            seat_id=seat_id,
            role_id=role_id,
            action=action,
            expected="PERMITTED",
            observed="PERMITTED",
            reason=f"mandate-grants:{role_id}:{action}",
            veto_blocked=veto_blocked,
        )
        self.log.append(att)
        return att


def expected_for(role_id: str, action: str) -> str:
    if role_id not in REGISTRY:
        return "UNENFORCED"
    return "PERMITTED" if action_permitted(REGISTRY[role_id], action) else "REFUSED"


def run_full_matrix(*, enforce: bool = True, mute_checks: FrozenSet[str] = frozenset()) -> dict:
    """Every typed role attempts every action. Prompt-only row is reported, not greened."""
    rt = CouncilRuntime(enforce=enforce, mute_checks=mute_checks)
    cells: list[dict] = []
    mismatches: list[dict] = []

    for role in TYPED_ROLES:
        sid = f"seat-{role}"
        seated = rt.seat(sid, role)
        if not seated["ok"]:
            raise RuntimeError(f"typed role {role} refused at seating: {seated}")
        for action in ACTIONS:
            att = rt.attempt(sid, action)
            # Reset motion so later veto cells stay independent.
            if action == "veto":
                rt.pending_motion = "motion-1"
                rt.motion_status = "OPEN"
            exp = expected_for(role, action)
            if enforce and not mute_checks:
                cell_ok = att.observed == exp
            else:
                # Stripped runtime: every typed attempt must go through (PERMITTED).
                cell_ok = att.observed == "PERMITTED"
            row = {
                "role": role,
                "action": action,
                "expected": exp,
                "observed": att.observed,
                "reason": att.reason,
                "cell_ok": cell_ok,
            }
            cells.append(row)
            if not row["cell_ok"]:
                mismatches.append(row)

    # Prompt-only role: seating succeeds (it is a label), every action UNENFORCED.
    ps = rt.seat("seat-prompt", PROMPT_ONLY_ROLE)
    prompt_cells: list[dict] = []
    for action in ACTIONS:
        att = rt.attempt("seat-prompt", action)
        row = {
            "role": PROMPT_ONLY_ROLE,
            "action": action,
            "expected": "UNENFORCED",
            "observed": att.observed,
            "reason": att.reason,
            "cell_ok": att.observed == "UNENFORCED",
        }
        prompt_cells.append(row)
        if not row["cell_ok"]:
            mismatches.append(row)

    forbidden_refused = sum(
        1
        for c in cells
        if c["expected"] == "REFUSED" and c["observed"] == "REFUSED"
    )
    forbidden_total = sum(1 for c in cells if c["expected"] == "REFUSED")
    permitted_ok = sum(
        1
        for c in cells
        if c["expected"] == "PERMITTED" and c["observed"] == "PERMITTED"
    )
    permitted_total = sum(1 for c in cells if c["expected"] == "PERMITTED")

    return {
        "enforce": enforce,
        "mute_checks": sorted(mute_checks),
        "typed_roles": list(TYPED_ROLES),
        "actions": list(ACTIONS),
        "cell_count": len(cells),
        "cells": cells,
        "prompt_only_role": PROMPT_ONLY_ROLE,
        "prompt_only_seated": ps["ok"],
        "prompt_cells": prompt_cells,
        "forbidden_total": forbidden_total,
        "forbidden_refused": forbidden_refused,
        "permitted_total": permitted_total,
        "permitted_ok": permitted_ok,
        "mismatches": mismatches,
        "forbidden_leaked": sum(
            1
            for c in cells
            if c["expected"] == "REFUSED" and c["observed"] == "PERMITTED"
        ),
        "matrix_ok": (not mismatches) if (enforce and not mute_checks) else False,
    }


def veto_trial() -> dict:
    """Holder veto actually blocks; non-holder veto is refused and does not block."""
    holder = CouncilRuntime()
    holder.seat("g", "guardian")
    holder.seat("o", "observer")
    holder.pending_motion = "motion-hold"
    holder.motion_status = "OPEN"
    g = holder.attempt("g", "veto")
    holder_status = holder.motion_status

    usurper = CouncilRuntime()
    usurper.seat("g", "guardian")
    usurper.seat("o", "observer")
    usurper.pending_motion = "motion-usurp"
    usurper.motion_status = "OPEN"
    o = usurper.attempt("o", "veto")
    usurper_status = usurper.motion_status

    return {
        "holder_observed": g.observed,
        "holder_blocked": g.veto_blocked and holder_status == "BLOCKED",
        "holder_motion_status": holder_status,
        "nonholder_observed": o.observed,
        "nonholder_blocked": o.veto_blocked,
        "nonholder_motion_status": usurper_status,
        "ok": (
            g.observed == "PERMITTED"
            and g.veto_blocked
            and holder_status == "BLOCKED"
            and o.observed == "REFUSED"
            and not o.veto_blocked
            and usurper_status == "OPEN"
        ),
    }


def incompatible_trial() -> dict:
    bad = CouncilRuntime().seat("x", "proposer", "judge")
    good = CouncilRuntime().seat("y", "proposer", "critic")
    return {
        "bad_observed": bad["observed"],
        "bad_reason": bad["reason"],
        "good_observed": good["observed"],
        "ok": bad["observed"] == "REFUSED"
        and "incompatible-roles:judge+proposer" in bad["reason"]
        and good["observed"] == "PERMITTED",
    }
