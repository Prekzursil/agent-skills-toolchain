"""Deterministic collapsed and healthy councils for ADV-0135.

Shared geometry for every pair: 4 seats, round-robin, round_budget=3.
Collapsed councils share one substance_claim (RES-0084 cache-family seed).
Healthy councils use four RES-0084 DISTINCT_IDEAS mechanisms so the
substance reviewer reports 4 clusters.
"""
from __future__ import annotations

import copy
import hashlib
from typing import Any

N_PARTICIPANTS = 4
TOPOLOGY = "round-robin"
ROUND_BUDGET = 3

CACHE = (
    "Cache expensive function results in a keyed in-memory store with TTL eviction."
)
CHAIR_CACHE = CACHE

RAFT = (
    "Elect a Raft leader by randomized timeouts and replicate a log through that leader"
)
AIMD = (
    "Grow a congestion window with AIMD additive increase after a loss halves it"
)
LSM = (
    "Flush an LSM tree by compacting sorted runs from memory into deeper levels"
)
BBR = (
    "Probe bottleneck bandwidth and RTT with BBR pacing instead of loss signals"
)
HEALTHY_CLAIMS = (CACHE, RAFT, AIMD, LSM)
HEALTHY_VOTES = (
    "adopt-cache-ttl",
    "adopt-raft-leader",
    "adopt-aimd-window",
    "adopt-lsm-flush",
)
ROLES = ("advocate", "critic", "skeptic", "chair-whisperer")
SEATS = ("P1", "P2", "P3", "P4")


def _gid(*parts: str) -> str:
    blob = "|".join(parts).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def _dissent_row(
    dissent_id: str,
    seat: str,
    claim: str,
    token: str,
    evidence: str,
) -> dict[str, Any]:
    return {
        "dissent_id": dissent_id,
        "participant_id": seat,
        "claim": claim,
        "evidence": evidence,
        "verbatim_token": token,
    }


def _seat(
    *,
    seat: str,
    role: str,
    vote_label: str,
    substance: str,
    brief: str,
    generation_id: str,
    independent: bool,
    source: str,
    trajectory: list[float],
    before: str,
    after: str,
    evidence_after: list[str],
    decision_vote: str = "yes",
) -> dict[str, Any]:
    return {
        "seat": seat,
        "declared_role": role,
        "vote_label": vote_label,
        "substance_claim": substance,
        "brief": brief,
        "generation_id": generation_id,
        "independent_generation": independent,
        "retrieved_source_id": source,
        "confidence_trajectory": list(trajectory),
        "position_before_chair": before,
        "position_after_chair": after,
        "evidence_ids_after_chair": list(evidence_after),
        "decision_vote": decision_vote,
    }


def _council(
    *,
    council_id: str,
    seats: list[dict[str, Any]],
    chair_position: str,
    first_unanimous_round: int | None,
    dissents: list[dict[str, Any]],
    synthesis_text: str,
    minority_report: list[dict[str, Any]],
    votes: list[dict[str, Any]] | None = None,
    turns: list[dict[str, Any]] | None = None,
    protocols: list[str] | None = None,
) -> dict[str, Any]:
    if votes is None:
        votes = [
            {
                "seat": s["seat"],
                "vote": s.get("decision_vote") or "yes",
                "round": 3,
            }
            for s in seats
        ]
    if turns is None:
        turns = [
            {
                "seat": s["seat"],
                "round": r + 1,
                "kind": "brief" if r == 0 else "rebuttal",
                "text": s["brief"] or s["substance_claim"],
                "confidence": s["confidence_trajectory"][r]
                if r < len(s["confidence_trajectory"])
                else s["confidence_trajectory"][-1],
            }
            for s in seats
            for r in range(ROUND_BUDGET)
        ]
    return {
        "council_id": council_id,
        "n_participants": N_PARTICIPANTS,
        "topology": TOPOLOGY,
        "round_budget": ROUND_BUDGET,
        "chair_position": chair_position,
        "first_unanimous_round": first_unanimous_round,
        "participants": seats,
        "transcript": {
            "turns": turns,
            "votes": votes,
            "dissents": dissents,
        },
        "synthesis": {
            "text": synthesis_text,
            "minority_report": minority_report,
        },
        "protocols": protocols or ["P56"],
    }


def _collapsed_seats(
    *,
    vote_labels: list[str],
    roles: list[str],
    briefs: list[str],
    generation_ids: list[str],
    independent: list[bool],
    sources: list[str],
    trajectories: list[list[float]],
    substances: list[str] | None = None,
) -> list[dict[str, Any]]:
    claims = substances or [CACHE] * 4
    out: list[dict[str, Any]] = []
    for i, seat in enumerate(SEATS):
        claim = claims[i]
        out.append(
            _seat(
                seat=seat,
                role=roles[i],
                vote_label=vote_labels[i],
                substance=claim,
                brief=briefs[i],
                generation_id=generation_ids[i],
                independent=independent[i],
                source=sources[i],
                trajectory=trajectories[i],
                before=claim,
                after=claim,
                evidence_after=[],
                decision_vote="yes",
            )
        )
    return out


def _healthy_seats(
    *,
    vote_labels: list[str] | None = None,
    roles: list[str] | None = None,
    sources: list[str] | None = None,
    trajectories: list[list[float]] | None = None,
    extra_nonce: str = "healthy",
) -> list[dict[str, Any]]:
    labels = list(vote_labels or HEALTHY_VOTES)
    rls = list(roles or ROLES)
    src = list(sources or [f"SRC-{c[:8]}" for c in HEALTHY_CLAIMS])
    traj = trajectories or [
        [0.55, 0.58, 0.60],
        [0.40, 0.42, 0.41],
        [0.72, 0.70, 0.69],
        [0.33, 0.35, 0.36],
    ]
    seats: list[dict[str, Any]] = []
    for i, seat in enumerate(SEATS):
        claim = HEALTHY_CLAIMS[i]
        seats.append(
            _seat(
                seat=seat,
                role=rls[i],
                vote_label=labels[i],
                substance=claim,
                brief=f"Independent first-pass brief for {claim}",
                generation_id=_gid(extra_nonce, seat, claim),
                independent=True,
                source=src[i],
                trajectory=traj[i],
                before=claim,
                after=claim,
                evidence_after=[],
                decision_vote=labels[i],
            )
        )
    return seats


def _healthy_dissent() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    row = _dissent_row(
        "D-RAFT",
        "P2",
        RAFT,
        "RAFT-LEADER-TOKEN",
        "turn:P2:r1",
    )
    return [row], [copy.deepcopy(row)]


def attack1_trivial_disagreement() -> dict[str, Any]:
    """Same substance; vote labels differ on trivia so CNL-0059 stays HEALTHY."""
    labels = [
        "approve-oxford-comma",
        "approve-semicolon",
        "approve-british-spelling",
        "approve-footnote-marker",
    ]
    seats = _collapsed_seats(
        vote_labels=labels,
        roles=list(ROLES),
        briefs=[f"Brief {i} restates the cache-TTL store." for i in range(4)],
        generation_ids=[_gid("a1", s) for s in SEATS],
        independent=[True] * 4,
        sources=["SRC-CACHE"] * 4,
        trajectories=[
            [0.32, 0.70, 0.88],
            [0.71, 0.74, 0.87],
            [0.44, 0.68, 0.90],
            [0.58, 0.72, 0.89],
        ],
    )
    return _council(
        council_id="ADV-0135-A1-trivial-disagreement",
        seats=seats,
        chair_position=CHAIR_CACHE,
        first_unanimous_round=None,
        dissents=[],
        synthesis_text="Council adopts the keyed in-memory TTL cache.",
        minority_report=[],
    )


def healthy1() -> dict[str, Any]:
    seats = _healthy_seats(extra_nonce="h1")
    dissents, report = _healthy_dissent()
    return _council(
        council_id="ADV-0135-H1-genuine-disagreement",
        seats=seats,
        chair_position=CACHE,
        first_unanimous_round=None,
        dissents=dissents,
        synthesis_text="No consensus: cache, Raft, AIMD and LSM remain live options.",
        minority_report=report,
    )


def attack2_void_dissent() -> dict[str, Any]:
    """Verbatim-preserved dissent that does not address the decision."""
    void_claim = (
        "The appendix should use an Oxford comma in the changelog heading."
    )
    token = "OXFORD-COMMA-VOID"
    row = _dissent_row("D-VOID", "P4", void_claim, token, "turn:P4:r2")
    seats = _collapsed_seats(
        vote_labels=["adopt-cache-ttl"] * 4,
        roles=list(ROLES),
        briefs=["Independently generated cache-TTL brief."] * 4,
        generation_ids=[_gid("a2", s) for s in SEATS],
        independent=[True] * 4,
        sources=["SRC-CACHE"] * 4,
        trajectories=[
            [0.31, 0.64, 0.85],
            [0.69, 0.72, 0.86],
            [0.47, 0.65, 0.84],
            [0.56, 0.70, 0.83],
        ],
    )
    # Labels are unanimous on the decision; first unanimous round is 3 after
    # briefs, so CNL-0059 (round-1 empty-brief) stays silent. Collapse is
    # carried by the void dissent slipping CNL-0097/0120/0070.
    return _council(
        council_id="ADV-0135-A2-void-dissent",
        seats=seats,
        chair_position=CHAIR_CACHE,
        first_unanimous_round=3,
        dissents=[row],
        synthesis_text=(
            "Adopt the keyed in-memory TTL cache. Recorded dissent "
            f"{token} on appendix punctuation is preserved."
        ),
        minority_report=[copy.deepcopy(row)],
    )


def healthy2() -> dict[str, Any]:
    seats = _healthy_seats(extra_nonce="h2")
    dissents, report = _healthy_dissent()
    return _council(
        council_id="ADV-0135-H2-substantive-dissent-preserved",
        seats=seats,
        chair_position=CACHE,
        first_unanimous_round=None,
        dissents=dissents,
        synthesis_text="Raft-leader alternative is preserved as D-RAFT.",
        minority_report=report,
    )


def attack3_role_diverse_same_argument() -> dict[str, Any]:
    """Four role prompts, one argument. Declared-role check stays HEALTHY."""
    seats = _collapsed_seats(
        vote_labels=[
            "approve-as-advocate",
            "approve-as-critic",
            "approve-as-skeptic",
            "approve-as-chair-whisperer",
        ],
        roles=list(ROLES),
        briefs=[CACHE] * 4,
        generation_ids=[_gid("a3", s) for s in SEATS],
        independent=[True] * 4,
        sources=["SRC-CACHE"] * 4,
        trajectories=[
            [0.34, 0.71, 0.90],
            [0.73, 0.75, 0.89],
            [0.41, 0.69, 0.91],
            [0.60, 0.73, 0.88],
        ],
    )
    return _council(
        council_id="ADV-0135-A3-role-diverse-same-argument",
        seats=seats,
        chair_position=CHAIR_CACHE,
        first_unanimous_round=None,
        dissents=[],
        synthesis_text="Every role restated the cache-TTL argument.",
        minority_report=[],
    )


def healthy3() -> dict[str, Any]:
    seats = _healthy_seats(extra_nonce="h3")
    dissents, report = _healthy_dissent()
    return _council(
        council_id="ADV-0135-H3-role-and-argument-diverse",
        seats=seats,
        chair_position=CACHE,
        first_unanimous_round=None,
        dissents=dissents,
        synthesis_text="Roles produced four distinct mechanisms.",
        minority_report=report,
    )


def attack4_shared_source() -> dict[str, Any]:
    """Independently GENERATED briefs that all retrieve one source."""
    seats = _collapsed_seats(
        vote_labels=[
            "approve-from-brief-1",
            "approve-from-brief-2",
            "approve-from-brief-3",
            "approve-from-brief-4",
        ],
        roles=list(ROLES),
        briefs=[
            "Independently generated brief 1 citing SRC-PAPER-ONE.",
            "Independently generated brief 2 citing SRC-PAPER-ONE.",
            "Independently generated brief 3 citing SRC-PAPER-ONE.",
            "Independently generated brief 4 citing SRC-PAPER-ONE.",
        ],
        generation_ids=[_gid("a4", s, "unique") for s in SEATS],
        independent=[True] * 4,
        sources=["SRC-PAPER-ONE"] * 4,
        trajectories=[
            [0.29, 0.63, 0.82],
            [0.68, 0.71, 0.83],
            [0.46, 0.64, 0.80],
            [0.57, 0.67, 0.81],
        ],
    )
    return _council(
        council_id="ADV-0135-A4-shared-source-independent-gen",
        seats=seats,
        chair_position=CHAIR_CACHE,
        first_unanimous_round=None,
        dissents=[],
        synthesis_text="Four independent generations, one retrieved paper.",
        minority_report=[],
    )


def healthy4() -> dict[str, Any]:
    seats = _healthy_seats(
        extra_nonce="h4",
        sources=["SRC-CACHE", "SRC-RAFT", "SRC-AIMD", "SRC-LSM"],
    )
    dissents, report = _healthy_dissent()
    return _council(
        council_id="ADV-0135-H4-independent-sources",
        seats=seats,
        chair_position=CACHE,
        first_unanimous_round=None,
        dissents=dissents,
        synthesis_text="Four sources, four mechanisms.",
        minority_report=report,
    )


def attack5_shaped_confidence() -> dict[str, Any]:
    """Identical substance; confidence spread then collapse looks like debate."""
    traj = [
        [0.32, 0.61, 0.90],
        [0.71, 0.74, 0.89],
        [0.44, 0.66, 0.91],
        [0.58, 0.70, 0.88],
    ]
    seats = _collapsed_seats(
        vote_labels=[
            "approve-low-start",
            "approve-high-start",
            "approve-mid-start",
            "approve-midhigh-start",
        ],
        roles=list(ROLES),
        briefs=["Cache-TTL restatement with staged confidence."] * 4,
        generation_ids=[_gid("a5", s) for s in SEATS],
        independent=[True] * 4,
        sources=["SRC-CACHE"] * 4,
        trajectories=traj,
    )
    return _council(
        council_id="ADV-0135-A5-shaped-confidence",
        seats=seats,
        chair_position=CHAIR_CACHE,
        first_unanimous_round=None,
        dissents=[],
        synthesis_text="Confidence converged after staged spread; position never moved.",
        minority_report=[],
    )


def healthy5() -> dict[str, Any]:
    seats = _healthy_seats(
        extra_nonce="h5",
        trajectories=[
            [0.30, 0.32, 0.31],
            [0.80, 0.79, 0.81],
            [0.55, 0.54, 0.56],
            [0.22, 0.25, 0.24],
        ],
    )
    dissents, report = _healthy_dissent()
    return _council(
        council_id="ADV-0135-H5-genuine-confidence-spread",
        seats=seats,
        chair_position=CACHE,
        first_unanimous_round=None,
        dissents=dissents,
        synthesis_text="Confidence stayed spread because positions stayed distinct.",
        minority_report=report,
    )


def caught_instant_unanimity() -> dict[str, Any]:
    """Control-of-the-control: round-1 identical labels, no briefs."""
    seats = _collapsed_seats(
        vote_labels=["adopt-cache-ttl"] * 4,
        roles=["member"] * 4,
        briefs=["", "", "", ""],
        generation_ids=["GID-SHARED"] * 4,
        independent=[False] * 4,
        sources=["SRC-CACHE"] * 4,
        trajectories=[[0.95, 0.95, 0.95]] * 4,
    )
    votes = [
        {"seat": s, "vote": "adopt-cache-ttl", "round": 1} for s in SEATS
    ]
    return _council(
        council_id="ADV-0135-COC-instant-unanimity",
        seats=seats,
        chair_position=CHAIR_CACHE,
        first_unanimous_round=1,
        dissents=[],
        synthesis_text="Instant unanimous adopt.",
        minority_report=[],
        votes=votes,
    )


def caught_dropped_dissent() -> dict[str, Any]:
    """Second CoC: a real dissent is omitted from the minority report."""
    seats = _healthy_seats(extra_nonce="coc-drop")
    dissents, _report = _healthy_dissent()
    return _council(
        council_id="ADV-0135-COC-dropped-dissent",
        seats=seats,
        chair_position=CACHE,
        first_unanimous_round=None,
        dissents=dissents,
        synthesis_text="Synthesis omits the Raft dissent.",
        minority_report=[],
    )


ATTACKS: list[tuple[str, str, str, str, Any, Any]] = [
    (
        "A1",
        "manufactured trivial disagreement",
        "CNL-0059",
        "HEALTHY unless vote labels are unanimous in round 1 with empty briefs; "
        "distinct trivia labels keep the unanimity counter below threshold while "
        "substance_claim is a single idea.",
        attack1_trivial_disagreement,
        healthy1,
    ),
    (
        "A2",
        "verbatim-preserved semantically void dissent",
        "CNL-0097",
        "HEALTHY when the dissent verbatim_token is present in the synthesis "
        "blob; a punctuation dissent satisfies presence while the decision "
        "stays a single viewpoint.",
        attack2_void_dissent,
        healthy2,
    ),
    (
        "A3",
        "role-diverse prompts, one argument",
        "IMP-0320-DECLARED-ROLES",
        "HEALTHY when unique declared_role count >= 3; four role labels with "
        "identical substance_claim slip a check that measures declared roles "
        "rather than output similarity.",
        attack3_role_diverse_same_argument,
        healthy3,
    ),
    (
        "A4",
        "independently generated briefs sharing one retrieved source",
        "CNL-0086",
        "HEALTHY when generation_ids are unique and independent_generation is "
        "true; a shared retrieved_source_id is outside the measurement.",
        attack4_shared_source,
        healthy4,
    ),
    (
        "A5",
        "confidence trajectory shaped as convergence-after-debate",
        "CNL-0086-DEBATE-SHAPE",
        "HEALTHY when round-0 confidence pstdev >= 0.08; staged spread then "
        "collapse is accepted as debate even though substance never moved.",
        attack5_shaped_confidence,
        healthy5,
    ),
]


def all_attacks() -> list[dict[str, Any]]:
    return [fn() for *_, fn, _nc in ATTACKS]


def all_healthy() -> list[dict[str, Any]]:
    return [fn() for *_, fn in ATTACKS]
