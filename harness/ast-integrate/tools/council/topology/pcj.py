"""Proposer / Critic / Judge (PCJ) topology with a typed staged hand-off.

Three seats, three stages, one direction: the proposer produces a
:class:`Proposal`, the critic produces a :class:`Critique` of it, and the judge
rules on a :func:`judge_view` that contains the claims and the critique points
and *nothing else*. The proposer's identity, aliases and private reasoning are
stripped before the judge sees anything, so the judge can neither favour a
proposer nor be swayed by reasoning the critic never surfaced. The census
proves the stripping on the actual view rather than trusting the builder.

A ruling must cite critique points that exist in the view. A citation to a
fabricated point id is refused (:class:`PCJError`) and, independently, fails
:func:`check_citations`; :func:`fabricated_citation_control` runs both states
so a probe can see the detector is neither inert nor inverted.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

STAGES: tuple[str, ...] = ("propose", "critique", "rule")
KIND_PROPOSAL = "pcj.proposal"
KIND_CRITIQUE = "pcj.critique"
KIND_JUDGE_VIEW = "pcj.judge_view"
KIND_RULING = "pcj.ruling"
VERDICTS: frozenset[str] = frozenset({"accept", "reject", "revise"})
POLARITIES: frozenset[str] = frozenset({"object", "question", "support"})


class PCJError(ValueError):
    """A stage hand-off or ruling violated the PCJ contract."""


@dataclass(frozen=True)
class Claim:
    claim_id: str
    text: str


@dataclass(frozen=True)
class Proposal:
    proposal_id: str
    proposer_id: str
    question: str
    claims: tuple[Claim, ...]
    reasoning: str = ""
    aliases: tuple[str, ...] = ()
    kind: str = field(default=KIND_PROPOSAL, init=False)

    def __post_init__(self) -> None:
        if not self.claims:
            raise PCJError(f"proposal {self.proposal_id} carries no claims")
        ids = [c.claim_id for c in self.claims]
        if len(set(ids)) != len(ids):
            raise PCJError(f"proposal {self.proposal_id} has duplicate claim ids {ids}")


@dataclass(frozen=True)
class CritiquePoint:
    point_id: str
    claim_id: str
    text: str
    polarity: str = "object"

    def __post_init__(self) -> None:
        if self.polarity not in POLARITIES:
            raise PCJError(
                f"critique point {self.point_id} polarity {self.polarity!r} not in {sorted(POLARITIES)}"
            )


@dataclass(frozen=True)
class Critique:
    critique_id: str
    critic_id: str
    proposal_id: str
    points: tuple[CritiquePoint, ...]
    kind: str = field(default=KIND_CRITIQUE, init=False)

    def __post_init__(self) -> None:
        ids = [p.point_id for p in self.points]
        if len(set(ids)) != len(ids):
            raise PCJError(f"critique {self.critique_id} has duplicate point ids {ids}")


@dataclass(frozen=True)
class Ruling:
    ruling_id: str
    judge_id: str
    verdict: str
    citations: tuple[str, ...]
    rationale: str = ""
    kind: str = field(default=KIND_RULING, init=False)


@dataclass(frozen=True)
class CitationCheck:
    ok: bool
    reason: str
    cited: tuple[str, ...]
    unresolved: tuple[str, ...]
    available: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "reason": self.reason,
            "cited": list(self.cited),
            "unresolved": list(self.unresolved),
            "available": list(self.available),
        }


@dataclass(frozen=True)
class Handoff:
    stage: str
    kind: str
    from_seat: str
    to_seat: str
    artifact_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "kind": self.kind,
            "from_seat": self.from_seat,
            "to_seat": self.to_seat,
            "artifact_id": self.artifact_id,
        }


@dataclass(frozen=True)
class PipelineResult:
    proposal: Proposal
    critique: Critique
    view: dict[str, Any]
    ruling: Ruling
    census: dict[str, Any]
    citation_check: CitationCheck
    handoff: tuple[Handoff, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "kinds": kinds_of(self),
            "stages": [h.stage for h in self.handoff],
            "handoff": [h.to_dict() for h in self.handoff],
            "view": self.view,
            "ruling": {
                "kind": self.ruling.kind,
                "ruling_id": self.ruling.ruling_id,
                "judge_id": self.ruling.judge_id,
                "verdict": self.ruling.verdict,
                "citations": list(self.ruling.citations),
                "rationale": self.ruling.rationale,
            },
            "census": self.census,
            "citation_check": self.citation_check.to_dict(),
        }


def judge_view(proposal: Proposal, critique: Critique) -> dict[str, Any]:
    """What the judge is allowed to see: claims and critique points only.

    No ``proposer_id``, no ``aliases``, no ``reasoning``, no ``critic_id``.
    """
    if critique.proposal_id != proposal.proposal_id:
        raise PCJError(
            f"critique {critique.critique_id} targets {critique.proposal_id}, "
            f"not proposal {proposal.proposal_id}"
        )
    claim_ids = {c.claim_id for c in proposal.claims}
    for p in critique.points:
        if p.claim_id not in claim_ids:
            raise PCJError(
                f"critique point {p.point_id} cites unknown claim {p.claim_id}"
            )
    return {
        "kind": KIND_JUDGE_VIEW,
        "proposal_id": proposal.proposal_id,
        "question": proposal.question,
        "claims": [{"claim_id": c.claim_id, "text": c.text} for c in proposal.claims],
        "critique_id": critique.critique_id,
        "points": [
            {
                "point_id": p.point_id,
                "claim_id": p.claim_id,
                "text": p.text,
                "polarity": p.polarity,
            }
            for p in critique.points
        ],
    }


def _walk(node: Any, keys: list[str], strings: list[str]) -> None:
    if isinstance(node, Mapping):
        for k, v in node.items():
            keys.append(str(k))
            _walk(v, keys, strings)
    elif isinstance(node, (list, tuple)):
        for v in node:
            _walk(v, keys, strings)
    elif isinstance(node, str):
        strings.append(node)


def _sentences(text: str) -> list[str]:
    parts = [s.strip() for s in text.replace("\n", " ").split(".")]
    return [s for s in parts if len(s) >= 12]


def view_census(view: Mapping[str, Any], proposal: Proposal) -> dict[str, Any]:
    """Measure the judge view against the proposal it was built from."""
    keys: list[str] = []
    strings: list[str] = []
    _walk(view, keys, strings)
    blob = "\n".join(strings)

    identity_tokens = [proposal.proposer_id, *proposal.aliases]
    identity_hits = [tok for tok in identity_tokens if tok and tok in blob]

    reasoning_tokens = [t for t in proposal.reasoning.split() if len(t) >= 8]
    reasoning_hits = [tok for tok in reasoning_tokens if tok in blob]
    reasoning_hits += [s for s in _sentences(proposal.reasoning) if s in blob]

    return {
        "n_claims": len(view.get("claims") or []),
        "n_points": len(view.get("points") or []),
        "point_ids": [p["point_id"] for p in view.get("points") or []],
        "field_names": keys,
        "string_values": strings,
        "identity_hits": identity_hits,
        "identity_leaked": bool(identity_hits),
        "proposer_id_field_present": "proposer_id" in keys or "aliases" in keys,
        "reasoning_field_present": "reasoning" in keys,
        "unsurfaced_reasoning_hits": reasoning_hits,
        "unsurfaced_reasoning_in_view": bool(reasoning_hits),
    }


def _point_ids(view: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(
        str(p.get("point_id"))
        for p in view.get("points") or []
        if isinstance(p, Mapping)
    )


def check_citations(ruling: Ruling, view: Mapping[str, Any]) -> CitationCheck:
    """A ruling must cite at least one critique point and only points that
    exist in the judge view."""
    available = _point_ids(view)
    cited = tuple(str(c) for c in ruling.citations)
    unresolved = tuple(c for c in cited if c not in available)
    if not cited:
        return CitationCheck(False, "empty-citations", cited, unresolved, available)
    if unresolved:
        return CitationCheck(
            False, "unresolved-citations", cited, unresolved, available
        )
    return CitationCheck(True, "all-citations-resolve", cited, unresolved, available)


def issue_ruling(
    view: Mapping[str, Any],
    *,
    ruling_id: str,
    judge_id: str,
    verdict: str,
    citations: Iterable[str],
    rationale: str = "",
) -> Ruling:
    """Build a ruling against ``view``; refuses fabricated or empty citations."""
    if verdict not in VERDICTS:
        raise PCJError(f"verdict {verdict!r} not in {sorted(VERDICTS)}")
    ruling = Ruling(
        ruling_id=str(ruling_id),
        judge_id=str(judge_id),
        verdict=verdict,
        citations=tuple(str(c) for c in citations),
        rationale=str(rationale),
    )
    check = check_citations(ruling, view)
    if not check.ok:
        raise PCJError(
            f"ruling {ruling.ruling_id} refused: {check.reason} unresolved={list(check.unresolved)}"
        )
    return ruling


def kinds_of(result: PipelineResult) -> list[str]:
    return [
        result.proposal.kind,
        result.critique.kind,
        str(result.view.get("kind")),
        result.ruling.kind,
    ]


def _expect(obj: Any, cls: type, stage: str) -> None:
    if not isinstance(obj, cls):
        raise PCJError(
            f"stage {stage!r} must hand off a {cls.__name__}, got {type(obj).__name__}"
        )


def run_pipeline(
    *,
    propose: Callable[[], Proposal],
    critique: Callable[[Proposal], Critique],
    rule: Callable[[dict[str, Any]], Ruling | Mapping[str, Any]],
) -> PipelineResult:
    """Run propose -> critique -> rule with typed hand-offs.

    The judge callable receives only the judge view. Its answer may be a
    :class:`Ruling` or a mapping with the ruling fields; either way it goes
    through :func:`issue_ruling`, so fabricated citations are refused, and a
    judge who is the proposer is refused.
    """
    proposal = propose()
    _expect(proposal, Proposal, STAGES[0])

    crit = critique(proposal)
    _expect(crit, Critique, STAGES[1])
    if crit.critic_id == proposal.proposer_id:
        raise PCJError("critic must not be the proposer")

    view = judge_view(proposal, crit)
    raw = rule(view)
    if isinstance(raw, Ruling):
        fields: dict[str, Any] = {
            "ruling_id": raw.ruling_id,
            "judge_id": raw.judge_id,
            "verdict": raw.verdict,
            "citations": raw.citations,
            "rationale": raw.rationale,
        }
    elif isinstance(raw, Mapping):
        fields = {
            "ruling_id": raw.get("ruling_id", ""),
            "judge_id": raw.get("judge_id", ""),
            "verdict": raw.get("verdict", ""),
            "citations": raw.get("citations") or (),
            "rationale": raw.get("rationale", ""),
        }
    else:
        raise PCJError(
            f"stage 'rule' must hand off a Ruling or mapping, got {type(raw).__name__}"
        )
    if not fields["ruling_id"] or not fields["judge_id"]:
        raise PCJError("ruling needs ruling_id and judge_id")
    if fields["judge_id"] in (proposal.proposer_id, crit.critic_id):
        raise PCJError("judge must be neither the proposer nor the critic")
    ruling = issue_ruling(view, **fields)

    handoff = (
        Handoff(
            STAGES[0],
            proposal.kind,
            proposal.proposer_id,
            crit.critic_id,
            proposal.proposal_id,
        ),
        Handoff(
            STAGES[1], crit.kind, crit.critic_id, ruling.judge_id, crit.critique_id
        ),
        Handoff(STAGES[2], ruling.kind, ruling.judge_id, "council", ruling.ruling_id),
    )
    return PipelineResult(
        proposal=proposal,
        critique=crit,
        view=view,
        ruling=ruling,
        census=view_census(view, proposal),
        citation_check=check_citations(ruling, view),
        handoff=handoff,
    )


def fabricated_citation_control(
    view: Mapping[str, Any],
    *,
    genuine: Iterable[str],
    fabricated: str,
    judge_id: str,
) -> dict[str, Any]:
    """Both-states check of the citation detector on one view."""
    genuine_ids = tuple(str(g) for g in genuine)
    good = Ruling("ctrl-good", judge_id, "reject", genuine_ids, "genuine citations")
    bad = Ruling(
        "ctrl-bad", judge_id, "accept", (str(fabricated),), "fabricated citation"
    )
    empty = Ruling("ctrl-empty", judge_id, "accept", (), "no citations")
    good_check = check_citations(good, view)
    bad_check = check_citations(bad, view)
    empty_check = check_citations(empty, view)
    refused = False
    try:
        issue_ruling(
            view,
            ruling_id="ctrl-issue",
            judge_id=judge_id,
            verdict="accept",
            citations=[fabricated],
        )
    except PCJError:
        refused = True
    return {
        "good_ok": good_check.ok,
        "bad_ok": bad_check.ok,
        "empty_ok": empty_check.ok,
        "good_reason": good_check.reason,
        "bad_reason": bad_check.reason,
        "empty_reason": empty_check.reason,
        "unresolved": list(bad_check.unresolved),
        "silent_on_good_state": good_check.ok is True,
        "fired_on_bad_state": bad_check.ok is False and refused,
        "issue_ruling_refused_fabricated": refused,
    }


__all__ = [
    "KIND_CRITIQUE",
    "KIND_JUDGE_VIEW",
    "KIND_PROPOSAL",
    "KIND_RULING",
    "POLARITIES",
    "STAGES",
    "VERDICTS",
    "CitationCheck",
    "Claim",
    "Critique",
    "CritiquePoint",
    "Handoff",
    "PCJError",
    "PipelineResult",
    "Proposal",
    "Ruling",
    "check_citations",
    "fabricated_citation_control",
    "issue_ruling",
    "judge_view",
    "kinds_of",
    "run_pipeline",
    "view_census",
]
