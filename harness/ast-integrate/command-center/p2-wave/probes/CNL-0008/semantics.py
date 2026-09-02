#!/usr/bin/env python3
"""CNL-0008 executable budget-block: 12 dials and exhaustion vs stopping.

Declared rule
-------------
HARD-STOP ceilings (effort, time, tokens, turns): exhaustion terminates as
BUDGET_EXHAUSTED. Remaining speakers agreeing does not rewrite that as CONSENSUS.

DEGRADE capabilities / seats / ladders (tool_calls, sources, experiments,
speaking_quotas, maximum_inactivity, rebuttal_depth, escalation): exhaustion
freezes that capability or marks that seat. The stopping roster does not shrink.
Unrun work is not coverage-complete. A depth cap is not an answer. Escalation-cap
plus deadlock is not consensus.

GATE floor (minimum_engagement): unmet floor forbids CONSENSUS. It does not
HARD-STOP a still-running council. When a ceiling also binds, the terminal
reason is ENGAGEMENT_UNMET (or BUDGET_EXHAUSTED with secondary ENGAGEMENT_UNMET).

The silent corruption is always the same shape: exhaustion, a floor miss, a
depth cap, or an escalation cap is allowed to look like agreement.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Literal

Reason = Literal[
    "CONSENSUS",
    "BUDGET_EXHAUSTED",
    "ENGAGEMENT_UNMET",
    "ESCALATION_EXHAUSTED",
    "CONTINUE",
]

DIAL_IDS = (
    "effort",
    "time",
    "tokens",
    "tool_calls",
    "sources",
    "experiments",
    "turns",
    "speaking_quotas",
    "minimum_engagement",
    "maximum_inactivity",
    "rebuttal_depth",
    "escalation",
)

HARD_STOP = frozenset({"effort", "time", "tokens", "turns"})
DEGRADE = frozenset(
    {
        "tool_calls",
        "sources",
        "experiments",
        "speaking_quotas",
        "maximum_inactivity",
        "rebuttal_depth",
        "escalation",
    }
)
GATE = frozenset({"minimum_engagement"})
CEILINGS = HARD_STOP | DEGRADE
RESOURCE_KEYS = (
    "effort",
    "time",
    "tokens",
    "tool_calls",
    "sources",
    "experiments",
    "turns",
)


@dataclass(frozen=True)
class Policy:
    hard_stop: frozenset[str]
    shrink_roster_on_mute: bool
    shrink_roster_on_inactive: bool
    unrun_counts_as_complete: bool
    depth_cap_counts_as_answered: bool
    escalation_deadlock_is_consensus: bool
    engagement_among_speakers_only: bool
    agreement_overrides_hard_stop: bool


DECLARED = Policy(
    hard_stop=HARD_STOP,
    shrink_roster_on_mute=False,
    shrink_roster_on_inactive=False,
    unrun_counts_as_complete=False,
    depth_cap_counts_as_answered=False,
    escalation_deadlock_is_consensus=False,
    engagement_among_speakers_only=False,
    agreement_overrides_hard_stop=False,
)


def corrupt_policy(dial: str) -> Policy:
    """Wrong choice for this dial — the one that silently corrupts stopping."""
    if dial in HARD_STOP:
        return replace(DECLARED, agreement_overrides_hard_stop=True)
    if dial == "speaking_quotas":
        return replace(DECLARED, shrink_roster_on_mute=True)
    if dial == "maximum_inactivity":
        return replace(DECLARED, shrink_roster_on_inactive=True)
    if dial in {"tool_calls", "sources", "experiments"}:
        return replace(DECLARED, unrun_counts_as_complete=True)
    if dial == "rebuttal_depth":
        return replace(DECLARED, depth_cap_counts_as_answered=True)
    if dial == "escalation":
        return replace(DECLARED, escalation_deadlock_is_consensus=True)
    if dial == "minimum_engagement":
        return replace(DECLARED, engagement_among_speakers_only=True)
    raise KeyError(dial)


@dataclass
class Seat:
    seat_id: str
    position: str = "UNDECLARED"
    speaking_used: int = 0
    engagement_units: int = 0
    inactive_ticks: int = 0
    status: str = "ACTIVE"


@dataclass
class Obligation:
    claim_id: str
    obligated_seat: str
    depth: int
    answered: bool = False
    depth_capped: bool = False


@dataclass
class CouncilState:
    seats: list[Seat]
    used: dict[str, int]
    caps: dict[str, int]
    min_engagement: int = 1
    speaking_cap: int = 3
    max_inactivity: int = 3
    max_rebuttal_depth: int = 2
    max_escalation: int = 2
    escalation_used: int = 0
    deadlocked: bool = False
    unrun_tools: int = 0
    unrun_sources: int = 0
    unrun_experiments: int = 0
    obligations: list[Obligation] = field(default_factory=list)


@dataclass
class Verdict:
    reason: Reason
    terminal: bool
    degraded: list[str]
    stopping_set: list[str]
    agreement: bool
    markers: list[str]
    refused_actions: list[str]
    secondary: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "reason": self.reason,
            "terminal": self.terminal,
            "degraded": list(self.degraded),
            "stopping_set": list(self.stopping_set),
            "agreement": self.agreement,
            "markers": list(self.markers),
            "refused_actions": list(self.refused_actions),
            "secondary": self.secondary,
        }


def resource_exhausted(state: CouncilState, dial: str) -> bool:
    if dial == "speaking_quotas":
        return any(s.speaking_used >= state.speaking_cap for s in state.seats)
    if dial == "maximum_inactivity":
        return any(s.inactive_ticks >= state.max_inactivity for s in state.seats)
    if dial == "minimum_engagement":
        return any(s.engagement_units < state.min_engagement for s in state.seats)
    if dial == "rebuttal_depth":
        return any(
            o.depth_capped or o.depth >= state.max_rebuttal_depth for o in state.obligations
        )
    if dial == "escalation":
        return state.escalation_used >= state.max_escalation
    return int(state.used.get(dial, 0)) >= int(state.caps.get(dial, 10**9))


def apply_seat_status(state: CouncilState) -> None:
    for seat in state.seats:
        if seat.speaking_used >= state.speaking_cap:
            seat.status = "MUTED"
        elif seat.inactive_ticks >= state.max_inactivity:
            seat.status = "INACTIVE"
        else:
            seat.status = "ACTIVE"


def stopping_ids(state: CouncilState, policy: Policy) -> list[str]:
    out: list[str] = []
    for seat in state.seats:
        if policy.shrink_roster_on_mute and seat.status == "MUTED":
            continue
        if policy.shrink_roster_on_inactive and seat.status == "INACTIVE":
            continue
        if policy.engagement_among_speakers_only and seat.engagement_units <= 0:
            continue
        out.append(seat.seat_id)
    return out


def seats_for(state: CouncilState, ids: list[str]) -> list[Seat]:
    by = {s.seat_id: s for s in state.seats}
    return [by[i] for i in ids]


def seats_agree(seats: list[Seat]) -> bool:
    if not seats:
        return False
    positions = [s.position for s in seats]
    if any(p in {"UNDECLARED", "ABSTAIN"} for p in positions):
        return False
    return len(set(positions)) == 1


def has_open_obligation(state: CouncilState, policy: Policy) -> bool:
    for obl in state.obligations:
        if obl.answered:
            continue
        capped = obl.depth_capped or obl.depth >= state.max_rebuttal_depth
        if capped and policy.depth_cap_counts_as_answered:
            continue
        return True
    return False


def coverage_complete(state: CouncilState, policy: Policy) -> bool:
    unrun = state.unrun_tools + state.unrun_sources + state.unrun_experiments
    if unrun <= 0:
        return True
    return bool(policy.unrun_counts_as_complete)


def engagement_unmet(state: CouncilState, ids: list[str]) -> bool:
    by = {s.seat_id: s for s in state.seats}
    return any(by[i].engagement_units < state.min_engagement for i in ids)


def evaluate(state: CouncilState, policy: Policy = DECLARED) -> Verdict:
    apply_seat_status(state)
    degraded: list[str] = []
    refused: list[str] = []
    markers: list[str] = []

    for dial in DIAL_IDS:
        if not resource_exhausted(state, dial):
            continue
        if dial in policy.hard_stop:
            markers.append(f"HARD_STOP:{dial}")
        elif dial in GATE:
            markers.append(f"GATE:{dial}")
        else:
            degraded.append(dial)
            markers.append(f"DEGRADED:{dial}")

    if resource_exhausted(state, "tool_calls"):
        refused.append("tool_call")
    if resource_exhausted(state, "sources"):
        refused.append("source_fetch")
    if resource_exhausted(state, "experiments"):
        refused.append("experiment")
    if any(s.status == "MUTED" for s in state.seats):
        refused.append("speak:MUTED")

    ids = stopping_ids(state, policy)
    members = seats_for(state, ids)
    agree = seats_agree(members)
    floor_miss = engagement_unmet(state, ids) if ids else True
    open_obl = has_open_obligation(state, policy)
    covered = coverage_complete(state, policy)
    hard_bound = any(
        resource_exhausted(state, dial) and dial in policy.hard_stop for dial in HARD_STOP
    )
    esc_bound = resource_exhausted(state, "escalation")
    deadlock = bool(state.deadlocked) or (not agree)

    if hard_bound:
        if policy.agreement_overrides_hard_stop and agree and not floor_miss:
            return Verdict(
                reason="CONSENSUS",
                terminal=True,
                degraded=degraded,
                stopping_set=ids,
                agreement=True,
                markers=markers + ["CORRUPT:agreement_overrides_hard_stop"],
                refused_actions=refused,
            )
        secondary = "ENGAGEMENT_UNMET" if floor_miss else None
        return Verdict(
            reason="BUDGET_EXHAUSTED",
            terminal=True,
            degraded=degraded,
            stopping_set=ids,
            agreement=agree,
            markers=markers + ["BUDGET_EXHAUSTED"],
            refused_actions=refused,
            secondary=secondary,
        )

    if floor_miss:
        ceiling_bound = any(resource_exhausted(state, dial) for dial in CEILINGS)
        if ceiling_bound or agree:
            return Verdict(
                reason="ENGAGEMENT_UNMET",
                terminal=True,
                degraded=degraded,
                stopping_set=ids,
                agreement=agree,
                markers=markers + ["ENGAGEMENT_UNMET"],
                refused_actions=refused,
            )
        return Verdict(
            reason="CONTINUE",
            terminal=False,
            degraded=degraded,
            stopping_set=ids,
            agreement=agree,
            markers=markers,
            refused_actions=refused,
        )

    if deadlock and esc_bound:
        if policy.escalation_deadlock_is_consensus:
            return Verdict(
                reason="CONSENSUS",
                terminal=True,
                degraded=degraded,
                stopping_set=ids,
                agreement=agree,
                markers=markers + ["CORRUPT:escalation_deadlock_as_consensus"],
                refused_actions=refused,
            )
        return Verdict(
            reason="ESCALATION_EXHAUSTED",
            terminal=True,
            degraded=degraded,
            stopping_set=ids,
            agreement=agree,
            markers=markers + ["ESCALATION_EXHAUSTED"],
            refused_actions=refused,
        )

    if open_obl:
        return Verdict(
            reason="CONTINUE",
            terminal=False,
            degraded=degraded,
            stopping_set=ids,
            agreement=agree,
            markers=markers + ["OBLIGATION_OPEN"],
            refused_actions=refused,
        )

    extra: list[str] = []
    unrun = state.unrun_tools + state.unrun_sources + state.unrun_experiments
    if unrun > 0 and policy.unrun_counts_as_complete:
        extra.append("CORRUPT:unrun_as_complete")
    if (
        any(
            (o.depth_capped or o.depth >= state.max_rebuttal_depth) and not o.answered
            for o in state.obligations
        )
        and policy.depth_cap_counts_as_answered
    ):
        extra.append("CORRUPT:depth_cap_as_answered")

    if agree and not open_obl and not floor_miss:
        cov = [] if covered else ["COVERAGE_INCOMPLETE"]
        return Verdict(
            reason="CONSENSUS",
            terminal=True,
            degraded=degraded,
            stopping_set=ids,
            agreement=True,
            markers=markers + ["CONSENSUS"] + cov + extra,
            refused_actions=refused,
        )

    return Verdict(
        reason="CONTINUE",
        terminal=False,
        degraded=degraded,
        stopping_set=ids,
        agreement=agree,
        markers=markers + extra,
        refused_actions=refused,
    )


def try_consume(state: CouncilState, dial: str, n: int = 1) -> dict[str, Any]:
    """Spend a resource. HARD-STOP refuses and stays terminal; DEGRADE refuses the increment."""
    apply_seat_status(state)
    before = evaluate(state, DECLARED)
    if dial in HARD_STOP and resource_exhausted(state, dial):
        return {"accepted": False, "reason": "BUDGET_EXHAUSTED", "verdict": before.as_dict()}
    if dial in {"tool_calls", "sources", "experiments"} and resource_exhausted(state, dial):
        return {"accepted": False, "reason": f"DEGRADED:{dial}", "verdict": before.as_dict()}
    if dial == "speaking_quotas":
        muted = [
            s.seat_id
            for s in state.seats
            if s.status == "MUTED" or s.speaking_used >= state.speaking_cap
        ]
        if muted:
            return {
                "accepted": False,
                "reason": "DEGRADED:speaking_quotas",
                "muted": muted,
                "verdict": before.as_dict(),
            }
    state.used[dial] = int(state.used.get(dial, 0)) + n
    after = evaluate(state, DECLARED)
    return {"accepted": True, "reason": after.reason, "verdict": after.as_dict()}


def masquerade_fires(
    claimed: Reason, state: CouncilState, policy: Policy = DECLARED
) -> bool:
    """True iff claimed CONSENSUS while the given policy forbids it."""
    got = evaluate(state, policy)
    return claimed == "CONSENSUS" and got.reason != "CONSENSUS"


def default_caps() -> dict[str, int]:
    return {k: 10 for k in RESOURCE_KEYS}


def seats_all_agree() -> list[Seat]:
    return [
        Seat("alice", position="A", speaking_used=1, engagement_units=2, inactive_ticks=0),
        Seat("bob", position="A", speaking_used=1, engagement_units=2, inactive_ticks=0),
        Seat("cara", position="A", speaking_used=1, engagement_units=2, inactive_ticks=0),
    ]


def seats_split() -> list[Seat]:
    return [
        Seat("alice", position="A", speaking_used=1, engagement_units=2, inactive_ticks=0),
        Seat("bob", position="B", speaking_used=1, engagement_units=2, inactive_ticks=0),
        Seat("cara", position="A", speaking_used=1, engagement_units=2, inactive_ticks=0),
    ]


def fixture_for(dial: str) -> CouncilState:
    """Planted exhaustion of `dial`. Remaining speakers agree — the masquerade bait."""
    used = {k: 0 for k in RESOURCE_KEYS}
    if dial in HARD_STOP:
        used[dial] = 10
        return CouncilState(seats=seats_all_agree(), used=used, caps=default_caps())
    if dial in {"tool_calls", "sources", "experiments"}:
        used[dial] = 10
        st = CouncilState(seats=seats_all_agree(), used=used, caps=default_caps())
        if dial == "tool_calls":
            st.unrun_tools = 2
        elif dial == "sources":
            st.unrun_sources = 2
        else:
            st.unrun_experiments = 2
        return st
    if dial == "speaking_quotas":
        seats = seats_all_agree()
        seats[1].position = "B"
        seats[1].speaking_used = 3
        return CouncilState(seats=seats, used=used, caps=default_caps(), speaking_cap=3)
    if dial == "minimum_engagement":
        # Unengaged cara still 'agrees' on paper. Declared: GATE forbids CONSENSUS.
        # Corrupt (count only speakers): cara drops out of the denominator → fake CONSENSUS.
        seats = seats_all_agree()
        seats[2].engagement_units = 0
        return CouncilState(seats=seats, used=used, caps=default_caps(), min_engagement=1)
    if dial == "maximum_inactivity":
        seats = seats_all_agree()
        seats[1].position = "B"
        seats[1].inactive_ticks = 5
        return CouncilState(seats=seats, used=used, caps=default_caps(), max_inactivity=3)
    if dial == "rebuttal_depth":
        # Everyone's last position is A, but bob still owes a capped rebuttal.
        # Declared: obligation open → CONTINUE. Corrupt: cap counts as answered → CONSENSUS.
        seats = seats_all_agree()
        obl = Obligation(
            claim_id="c1",
            obligated_seat="bob",
            depth=2,
            answered=False,
            depth_capped=True,
        )
        return CouncilState(
            seats=seats,
            used=used,
            caps=default_caps(),
            max_rebuttal_depth=2,
            obligations=[obl],
        )
    if dial == "escalation":
        return CouncilState(
            seats=seats_split(),
            used=used,
            caps=default_caps(),
            deadlocked=True,
            escalation_used=2,
            max_escalation=2,
        )
    raise KeyError(dial)


def known_good_consensus() -> CouncilState:
    return CouncilState(
        seats=seats_all_agree(),
        used={k: 1 for k in RESOURCE_KEYS},
        caps=default_caps(),
    )


def midrun_engagement_unmet() -> CouncilState:
    """Floor unmet, no ceiling bound — declared must CONTINUE, not HARD-STOP."""
    seats = seats_all_agree()
    seats[2].engagement_units = 0
    seats[2].position = "UNDECLARED"
    return CouncilState(
        seats=seats,
        used={k: 1 for k in RESOURCE_KEYS},
        caps=default_caps(),
        min_engagement=1,
    )


DIAL_SPEC: dict[str, dict[str, Any]] = {
    "effort": {
        "kind": "ceiling",
        "exhaustion": "HARD_STOP",
        "declared_reason_on_fixture": "BUDGET_EXHAUSTED",
        "wrong_choice": "DEGRADE (hurry remaining work / keep going cheaply)",
        "silent_corruption": (
            "agreement_overrides_hard_stop: leftover speakers still agree, so the "
            "stop is labelled CONSENSUS after effort is already spent."
        ),
    },
    "time": {
        "kind": "ceiling",
        "exhaustion": "HARD_STOP",
        "declared_reason_on_fixture": "BUDGET_EXHAUSTED",
        "wrong_choice": "DEGRADE (hurry-up vote as the clock hits zero)",
        "silent_corruption": (
            "Time-pressure majority is recorded as CONSENSUS. Wall-clock is not "
            "recoverable; the stopping rule then cannot distinguish agreement from expiry."
        ),
    },
    "tokens": {
        "kind": "ceiling",
        "exhaustion": "HARD_STOP",
        "declared_reason_on_fixture": "BUDGET_EXHAUSTED",
        "wrong_choice": "DEGRADE (emit truncated turns and still vote)",
        "silent_corruption": (
            "Truncated arguments enter the vote unlabelled. A partial reads as a "
            "complete CONSENSUS."
        ),
    },
    "tool_calls": {
        "kind": "capability",
        "exhaustion": "DEGRADE",
        "declared_reason_on_fixture": "CONSENSUS",
        "declared_markers": ["DEGRADED:tool_calls", "COVERAGE_INCOMPLETE"],
        "wrong_choice": "HARD_STOP the council, OR silent DEGRADE that treats unrun tools as done",
        "silent_corruption": (
            "unrun_counts_as_complete: coverage-gated stopping fires because missing "
            "tool results are treated as empty-success."
        ),
    },
    "sources": {
        "kind": "capability",
        "exhaustion": "DEGRADE",
        "declared_reason_on_fixture": "CONSENSUS",
        "declared_markers": ["DEGRADED:sources", "COVERAGE_INCOMPLETE"],
        "wrong_choice": "HARD_STOP, OR treat unfetched sources as coverage-complete",
        "silent_corruption": (
            "Omitted citations fill the gap; a coverage target in the stopping "
            "expression fires on a search that did not happen."
        ),
    },
    "experiments": {
        "kind": "capability",
        "exhaustion": "DEGRADE",
        "declared_reason_on_fixture": "CONSENSUS",
        "declared_markers": ["DEGRADED:experiments", "COVERAGE_INCOMPLETE"],
        "wrong_choice": "HARD_STOP, OR treat unrun experiments as null results",
        "silent_corruption": (
            "Absence of an experiment is scored as 'no effect'. Coverage-complete "
            "CONSENSUS then masquerades as an empirical result."
        ),
    },
    "turns": {
        "kind": "ceiling",
        "exhaustion": "HARD_STOP",
        "declared_reason_on_fixture": "BUDGET_EXHAUSTED",
        "wrong_choice": "DEGRADE (one more round until someone agrees)",
        "silent_corruption": (
            "Turn cap becomes decorative. The last majority at the cap is stamped "
            "CONSENSUS — consensus-by-attrition."
        ),
    },
    "speaking_quotas": {
        "kind": "per-seat ceiling",
        "exhaustion": "DEGRADE",
        "declared_reason_on_fixture": "CONTINUE",
        "wrong_choice": "HARD_STOP the whole council, OR drop MUTED seats from the stopping set",
        "silent_corruption": (
            "shrink_roster_on_mute: a quota-silenced dissenter leaves the roster; "
            "remaining seats are unanimous. Silence-from-quota is treated as consent."
        ),
    },
    "minimum_engagement": {
        "kind": "floor",
        "exhaustion": "GATE",
        "declared_reason_on_fixture": "ENGAGEMENT_UNMET",
        "wrong_choice": "DEGRADE (CONSENSUS among those who spoke) or mid-run HARD_STOP",
        "silent_corruption": (
            "engagement_among_speakers_only: unengaged seats fall out of the "
            "denominator. Thin participation yields CONSENSUS."
        ),
    },
    "maximum_inactivity": {
        "kind": "per-seat ceiling",
        "exhaustion": "DEGRADE",
        "declared_reason_on_fixture": "CONTINUE",
        "wrong_choice": "HARD_STOP the council, OR drop INACTIVE seats from the stopping set",
        "silent_corruption": (
            "shrink_roster_on_inactive: an AFK dissenter is removed from quorum; "
            "ALL-agree fires on the remainder."
        ),
    },
    "rebuttal_depth": {
        "kind": "ladder",
        "exhaustion": "DEGRADE",
        "declared_reason_on_fixture": "CONTINUE",
        "wrong_choice": "HARD_STOP the council, OR treat DEPTH_CAPPED as answered/unopposed",
        "silent_corruption": (
            "depth_cap_counts_as_answered: unrebutted-because-capped claims count as "
            "unopposed, so a no-objection stopping expression fires."
        ),
    },
    "escalation": {
        "kind": "ladder",
        "exhaustion": "DEGRADE",
        "declared_reason_on_fixture": "ESCALATION_EXHAUSTED",
        "wrong_choice": "HARD_STOP at first escalation, OR record stuck-tier as CONSENSUS",
        "silent_corruption": (
            "escalation_deadlock_is_consensus: 'we cannot climb' is filed as "
            "'resolved at this tier'."
        ),
    },
}


def run_all_declared() -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for dial in DIAL_IDS:
        st = fixture_for(dial)
        verdict = evaluate(st, DECLARED)
        spec = DIAL_SPEC[dial]
        rows[dial] = {
            "exhaustion": spec["exhaustion"],
            "reason": verdict.reason,
            "want_reason": spec["declared_reason_on_fixture"],
            "match": verdict.reason == spec["declared_reason_on_fixture"],
            "markers": verdict.markers,
            "stopping_set": verdict.stopping_set,
            "stopping_set_size": len(verdict.stopping_set),
            "roster_size": len(st.seats),
            "agreement": verdict.agreement,
            "terminal": verdict.terminal,
            "refused_actions": verdict.refused_actions,
            "secondary": verdict.secondary,
        }
    return rows


def run_wrong_choice(dial: str) -> dict[str, Any]:
    declared = evaluate(fixture_for(dial), DECLARED)
    corrupt = evaluate(fixture_for(dial), corrupt_policy(dial))
    return {
        "dial": dial,
        "declared_reason": declared.reason,
        "corrupt_reason": corrupt.reason,
        "declared_set": declared.stopping_set,
        "corrupt_set": corrupt.stopping_set,
        "corrupt_markers": corrupt.markers,
        "silently_became_consensus": (
            declared.reason != "CONSENSUS" and corrupt.reason == "CONSENSUS"
        ),
        "roster_shrunk": len(corrupt.stopping_set) < len(declared.stopping_set),
        "unrun_labelled_complete": "CORRUPT:unrun_as_complete" in corrupt.markers,
        "depth_cap_as_answered": "CORRUPT:depth_cap_as_answered" in corrupt.markers,
    }


def function_line(name: str) -> int:
    """1-based line of `def name` / `class name` in this file — live, not remembered."""
    with open(__file__, encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            if line.startswith(f"def {name}(") or line.startswith(f"class {name}"):
                return i
    raise RuntimeError(f"anchor not found: {name}")
