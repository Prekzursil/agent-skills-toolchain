"""Elastic mid-run recruitment with a consensus-isolation partition (IMP-0274)."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

REASON_FORBIDDEN_KEY = "forbidden-consensus-key"
REASON_OUTPUT_ECHO = "output-echoes-consensus"


class ElasticError(Exception):
    pass


def _seated_tags(run: dict[str, Any]) -> set[str]:
    tags: set[str] = set()
    for seat in run.get("seats") or []:
        if isinstance(seat, dict):
            tags.update(str(t) for t in (seat.get("expertise") or []))
    return tags


def _missing(run: dict[str, Any]) -> list[str]:
    required = [str(t) for t in (run.get("required_coverage") or [])]
    topics = [str(t) for t in (run.get("mid_run_topics") or [])]
    have = _seated_tags(run)
    missing: list[str] = []
    for tag in required + topics:
        if tag not in have and tag not in missing:
            missing.append(tag)
    return missing


@dataclass
class ScaleDecision:
    action: str
    reason: str
    recruit_count: int
    missing_tags: list[str] = field(default_factory=list)
    unfilled_tags: list[str] = field(default_factory=list)
    current_seats: int = 0
    max_seats: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,
            "recruit_count": self.recruit_count,
            "missing_tags": list(self.missing_tags),
            "unfilled_tags": list(self.unfilled_tags),
            "current_seats": self.current_seats,
            "max_seats": self.max_seats,
        }


@dataclass
class RecruitResult:
    run: dict[str, Any]
    recruited: list[dict[str, Any]]
    decision: ScaleDecision | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"recruited": list(self.recruited), "seat_count": len(self.run.get("seats") or [])}


def scale_decision(run: dict[str, Any]) -> ScaleDecision:
    current = len(run.get("seats") or [])
    max_seats = int(run.get("max_seats") or current)
    min_seats = int(run.get("min_seats") or 0)
    if max_seats < min_seats:
        raise ElasticError(f"max_seats {max_seats} < min_seats {min_seats}")
    missing = _missing(run)
    remaining = max(0, max_seats - current)
    if not missing:
        return ScaleDecision(
            action="hold",
            reason="no_gap",
            recruit_count=0,
            missing_tags=[],
            unfilled_tags=[],
            current_seats=current,
            max_seats=max_seats,
        )
    if remaining <= 0:
        return ScaleDecision(
            action="hold",
            reason="at_max_with_gap",
            recruit_count=0,
            missing_tags=list(missing),
            unfilled_tags=list(missing),
            current_seats=current,
            max_seats=max_seats,
        )
    n = min(len(missing), remaining)
    return ScaleDecision(
        action="recruit",
        reason="coverage_or_expertise_gap",
        recruit_count=n,
        missing_tags=list(missing),
        unfilled_tags=[],
        current_seats=current,
        max_seats=max_seats,
    )


def _candidate_for(run: dict[str, Any], tag: str) -> dict[str, Any] | None:
    for cand in run.get("candidates") or []:
        if tag in (cand.get("expertise") or []):
            return dict(cand)
    return None


def _partition_context(run: dict[str, Any], *, leak_consensus: bool) -> dict[str, Any]:
    ctx: dict[str, Any] = {
        "question": run.get("question"),
        "shared_evidence": list(run.get("shared_evidence") or []),
        "catch_up_facts": list(run.get("catch_up_facts") or []),
    }
    if leak_consensus:
        ctx["running_consensus"] = run.get("running_consensus")
        ctx["transcript"] = list(run.get("transcript") or [])
    return ctx


def draft_first_position(ctx: dict[str, Any]) -> str:
    if ctx.get("running_consensus"):
        return str(ctx.get("running_consensus"))
    facts = list(ctx.get("catch_up_facts") or []) + list(ctx.get("shared_evidence") or [])
    q = str(ctx.get("question") or "")
    body = " ".join(str(x) for x in facts[:3])
    return f"Independent first look at {q}: {body}"


def recruit(run: dict[str, Any], leak_consensus: bool = False) -> RecruitResult:
    working = deepcopy(run)
    decision = scale_decision(working)
    recruited: list[dict[str, Any]] = []
    if decision.action != "recruit":
        # Capacity/unfilled path still records the decision (probe 1 case 6).
        if decision.reason == "at_max_with_gap":
            decision = ScaleDecision(
                action="unfilled",
                reason=decision.reason,
                recruit_count=0,
                missing_tags=list(decision.missing_tags),
                unfilled_tags=list(decision.unfilled_tags or decision.missing_tags),
                current_seats=decision.current_seats,
                max_seats=decision.max_seats,
            )
        return RecruitResult(run=working, recruited=[], decision=decision)
    covering = [c for c in (working.get("candidates") or [])]
    if decision.action == "recruit" and not covering:
        unfilled = ScaleDecision(
            action="unfilled",
            reason="gap_with_no_covering_candidate",
            recruit_count=0,
            missing_tags=list(decision.missing_tags),
            unfilled_tags=list(decision.missing_tags),
            current_seats=decision.current_seats,
            max_seats=decision.max_seats,
        )
        return RecruitResult(run=working, recruited=[], decision=unfilled)
    for tag in decision.missing_tags[: decision.recruit_count]:
        cand = _candidate_for(working, tag)
        if cand is None:
            continue
        ctx = _partition_context(working, leak_consensus=leak_consensus)
        row = dict(cand)
        row["original"] = False
        row["context"] = ctx
        if leak_consensus:
            row["first_output"] = str(working.get("running_consensus") or "")
        else:
            row["first_output"] = draft_first_position(ctx)
        working.setdefault("seats", []).append(
            {
                "seat_id": row["seat_id"],
                "role": row.get("role"),
                "expertise": list(row.get("expertise") or []),
                "original": False,
            }
        )
        recruited.append(row)
    return RecruitResult(run=working, recruited=recruited, decision=decision)


def first_original_context(run: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    for seat in run.get("seats") or []:
        if isinstance(seat, dict) and seat.get("original") is True:
            ctx = {
                "question": run.get("question"),
                "shared_evidence": list(run.get("shared_evidence") or []),
                "catch_up_facts": list(run.get("catch_up_facts") or []),
                "running_consensus": run.get("running_consensus"),
                "transcript": list(run.get("transcript") or []),
            }
            return str(seat.get("seat_id") or "s1"), ctx
    raise ElasticError("no original seat")


@dataclass
class ContextDiff:
    partition_match: bool
    consensus_leaked_to_recruit: bool
    question_equal: bool
    shared_evidence_equal: bool
    original_seat_id: str = ""
    recruit_seat_id: str = ""
    forbidden_on_recruit: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "partition_match": self.partition_match,
            "consensus_leaked_to_recruit": self.consensus_leaked_to_recruit,
            "question_equal": self.question_equal,
            "shared_evidence_equal": self.shared_evidence_equal,
            "original_seat_id": self.original_seat_id,
            "recruit_seat_id": self.recruit_seat_id,
            "forbidden_on_recruit": list(self.forbidden_on_recruit),
        }


def context_diff(
    orig_ctx: dict[str, Any],
    rec_ctx: dict[str, Any],
    *,
    original_seat_id: str = "",
    recruit_seat_id: str = "",
) -> ContextDiff:
    q_eq = orig_ctx.get("question") == rec_ctx.get("question")
    ev_eq = list(orig_ctx.get("shared_evidence") or []) == list(rec_ctx.get("shared_evidence") or [])
    catch_eq = list(orig_ctx.get("catch_up_facts") or []) == list(rec_ctx.get("catch_up_facts") or [])
    leaked = "running_consensus" in rec_ctx or bool(rec_ctx.get("transcript"))
    forbidden = [k for k in ("running_consensus", "transcript") if k in rec_ctx]
    return ContextDiff(
        partition_match=bool(q_eq and ev_eq and catch_eq) and not leaked,
        consensus_leaked_to_recruit=leaked,
        question_equal=bool(q_eq),
        shared_evidence_equal=bool(ev_eq),
        original_seat_id=original_seat_id,
        recruit_seat_id=recruit_seat_id,
        forbidden_on_recruit=forbidden,
    )


@dataclass
class Independence:
    fired: bool
    status: str
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"fired": self.fired, "status": self.status, "reasons": list(self.reasons)}


def independence_check(ctx: dict[str, Any], output: str, consensus: str) -> Independence:
    reasons: list[str] = []
    if "running_consensus" in ctx or ctx.get("transcript"):
        reasons.append(REASON_FORBIDDEN_KEY)
    if consensus and consensus.lower() in (output or "").lower():
        reasons.append(REASON_OUTPUT_ECHO)
    fired = bool(reasons)
    return Independence(fired=fired, status="FIRE" if fired else "SILENT", reasons=reasons)


def feed_consensus_transcript(ctx: dict[str, Any], consensus: str, transcript: list[Any] | None = None) -> dict[str, Any]:
    out = dict(ctx)
    out["running_consensus"] = consensus
    out["transcript"] = list(transcript or [{"position": consensus}])
    return out
