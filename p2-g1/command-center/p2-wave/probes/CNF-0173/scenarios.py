#!/usr/bin/env python3
"""Confirmer-authored council scenarios for CNF-0173.

These are new (2026-08-24 confirmer pack). They are not the CNF-0092
instant-unanimity fixture, not the TST-0258 clone-cast, and not any
IMP-0318 implementer fixture. Domain: coastal-permit / harbor / ferry.
"""
from __future__ import annotations

from typing import Any

# Names the confirmer pack must never reuse (implementer / prior-fixture ids).
FORBIDDEN_REUSE_SUBSTRINGS = (
    "cnf-0092",
    "cnf0092",
    "instant-unanimity-fixture",
    "tst-0258",
    "imp-0318",
    "planted-cast-of-clones",
)


def _p(
    seat: str,
    role: str,
    argument: str,
    votes: list[str],
    brief: str | None = None,
) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "seat": seat,
        "role": role,
        "argument": argument,
        "votes": list(votes),
    }
    if brief is not None:
        rec["brief"] = brief
    return rec


CLONE_LINE = (
    "The seawall permit is fine; approve it without further review."
)


def seawall_clone_panel() -> dict[str, Any]:
    """Round-1 unanimity, zero independent briefs, planted wrong consensus."""
    seats = (
        ("chair", "chair"),
        ("coastal-engineer", "engineer"),
        ("habitat-critic", "critic"),
        ("minutes", "scribe"),
    )
    return {
        "id": "cnf0173-seawall-clone-panel",
        "author": "confirmer.openai.gpt-5-codex",
        "domain": "coastal-permit-seawall",
        "question": (
            "Should the municipal seawall raising permit at Pier 14 be approved "
            "given last winter's overtopping measurements?"
        ),
        "first_vote_round": 1,
        "deliberation_rounds": 1,
        "planted_wrong_consensus": True,
        "correct_decision": "reject",
        "claimed_unique_ideas": None,
        "ideas": [],
        "participants": [
            _p(seat, role, CLONE_LINE, ["approve"]) for seat, role in seats
        ],
        "meta": {
            "hidden_evidence": (
                "Overtopping at Pier 14 exceeded design freeboard on 11 of 14 "
                "storm tides; the clone panel never cites this."
            )
        },
    }


def harbor_after_briefs() -> dict[str, Any]:
    """Genuine deliberation then consensus: must NOT trip instant unanimity."""
    return {
        "id": "cnf0173-harbor-after-briefs",
        "author": "confirmer.openai.gpt-5-codex",
        "domain": "harbor-lighting-retrofit",
        "question": (
            "Should the inner-harbor nav-light retrofit proceed this quarter?"
        ),
        "first_vote_round": 3,
        "deliberation_rounds": 3,
        "planted_wrong_consensus": False,
        "correct_decision": "approve-with-conditions",
        "claimed_unique_ideas": None,
        "ideas": [],
        "participants": [
            _p(
                "chair",
                "chair",
                "Hold the vote until the lux map and bird-strike brief land.",
                ["abstain", "abstain", "approve-with-conditions"],
                brief=(
                    "Chair brief: schedule risk only. No position on the "
                    "photometric design until independent lux measurements exist."
                ),
            ),
            _p(
                "photometric-engineer",
                "engineer",
                "Lux map shows 22% under-lighted berths; LED cutover is warranted.",
                ["approve", "approve-with-conditions", "approve-with-conditions"],
                brief=(
                    "Engineer brief cites the 2025 inner-harbor lux transect "
                    "(22 percent of berths below IALA min) and a parts lead-time "
                    "of 19 days."
                ),
            ),
            _p(
                "avian-critic",
                "critic",
                "Warm-white spill will raise bird-strike counts on the breakwater.",
                ["reject", "approve-with-conditions", "approve-with-conditions"],
                brief=(
                    "Critic brief cites the 2024 breakwater carcass survey "
                    "(14 strikes in 6 weeks under 4000K floodlights) and demands "
                    "2700K shielding as a condition."
                ),
            ),
        ],
    }


def role_clone_slow() -> dict[str, Any]:
    """Identical arguments; first vote only on round 3. Collapse, not speed."""
    same = (
        "All seats recite the same paragraph about ferry ticketing and vote "
        "the same way once a vote is finally called."
    )
    votes = ["", "", "keep-status-quo"]
    return {
        "id": "cnf0173-role-clone-slow",
        "author": "confirmer.openai.gpt-5-codex",
        "domain": "ferry-ticketing-copy",
        "question": "Should the ferry kiosk copy be rewritten this season?",
        "first_vote_round": 3,
        "deliberation_rounds": 3,
        "planted_wrong_consensus": False,
        "correct_decision": "keep-status-quo",
        "claimed_unique_ideas": None,
        "ideas": [],
        "participants": [
            _p("chair", "chair", same, votes, brief=same),
            _p("copywriter", "proposer", same, votes, brief=same),
            _p("editor", "critic", same, votes, brief=same),
        ],
    }


YELLOW = [
    "paint the buoy yellow",
    "paint buoy yellow",
    "painting the buoy yellow",
    "paint the buoy a yellow colour",
    "paint the buoy a yellow color",
    "make the buoy yellow with paint",
    "apply yellow paint to the buoy",
    "the buoy should be painted yellow",
    "yellow-paint the buoy",
    "coat the buoy in yellow paint",
]


def _hundred_echo_ideas() -> list[str]:
    ideas: list[str] = []
    n = 0
    while n < 100:
        base = YELLOW[n % len(YELLOW)]
        suffix = n // len(YELLOW)
        ideas.append(base if suffix == 0 else f"{base} (variant {suffix})")
        n += 1
    return ideas


def hundred_echo_ideas() -> dict[str, Any]:
    """100-idea target satisfied by trivial wording variants."""
    ideas = _hundred_echo_ideas()
    return {
        "id": "cnf0173-hundred-echo-ideas",
        "author": "confirmer.openai.gpt-5-codex",
        "domain": "aid-to-navigation-brainstorm",
        "question": "List 100 unique ideas to make the channel marker more visible.",
        "first_vote_round": 2,
        "deliberation_rounds": 2,
        "planted_wrong_consensus": False,
        "correct_decision": None,
        "claimed_unique_ideas": 100,
        "ideas": ideas,
        "participants": [
            _p(
                "brainstorm-lead",
                "proposer",
                "We have one hundred unique visibility ideas.",
                ["", "accept-count"],
                brief="Lead claims unique_ideas>=100 from the variant list.",
            ),
            _p(
                "counter",
                "critic",
                "Count them as one hundred distinct proposals.",
                ["", "accept-count"],
                brief="Critic repeats the count claim without a novelty pass.",
            ),
        ],
    }


def reviewer_ferry_snap() -> dict[str, Any]:
    """Third scenario, Anthropic-side reviewer, different domain."""
    line = "Ferry timetable change is obviously fine; unanimous yes."
    return {
        "id": "cnf0173-reviewer-ferry-snap",
        "author": "reviewer.anthropic.opus",
        "domain": "ferry-quorum-snap",
        "question": (
            "Should Saturday shoulder-hour ferries drop from 3 to 2 sailings?"
        ),
        "first_vote_round": 1,
        "deliberation_rounds": 1,
        "planted_wrong_consensus": True,
        "correct_decision": "reject",
        "claimed_unique_ideas": None,
        "ideas": [],
        "participants": [
            _p("chair", "chair", line, ["approve"]),
            _p("ops", "engineer", line, ["approve"]),
            _p("rider-advocate", "critic", line, ["approve"]),
        ],
        "meta": {
            "hidden_evidence": (
                "Saturday 11:00 sailing ran at 94% load for 8 weeks; dropping "
                "it strands the hospital-shift overlap."
            )
        },
    }


def confirmer_pack() -> list[dict[str, Any]]:
    return [
        seawall_clone_panel(),
        harbor_after_briefs(),
        role_clone_slow(),
        hundred_echo_ideas(),
        reviewer_ferry_snap(),
    ]


def clone_at_vote_round(vote_round: int, distinct_briefs: int) -> dict[str, Any]:
    """Sensitivity fixture: same clone panel, first vote at `vote_round`."""
    base = seawall_clone_panel()
    vr = max(1, int(vote_round))
    empty = [""] * (vr - 1) + ["approve"]
    briefs = [
        "Pier-14 overtopping series: 11 of 14 storm tides exceeded freeboard.",
        "Geotech memo: toe scour at station 4+20 needs a reject, not a raise.",
        "Insurance rider: underwriters will not bind if freeboard stays as-is.",
    ]
    parts = []
    for i, p in enumerate(base["participants"]):
        q = dict(p)
        q["votes"] = list(empty)
        if i < distinct_briefs:
            q["brief"] = briefs[i % len(briefs)]
        else:
            q.pop("brief", None)
        parts.append(q)
    base["id"] = f"cnf0173-sweep-r{vr}-b{distinct_briefs}"
    base["first_vote_round"] = vr
    base["deliberation_rounds"] = vr
    base["participants"] = parts
    base["author"] = "confirmer.openai.gpt-5-codex"
    return base


def assert_not_reused(scenario: dict[str, Any]) -> None:
    blob = (scenario.get("id") or "").lower()
    for needle in FORBIDDEN_REUSE_SUBSTRINGS:
        if needle in blob:
            raise ValueError(f"scenario id reuses implementer fixture token {needle}")
