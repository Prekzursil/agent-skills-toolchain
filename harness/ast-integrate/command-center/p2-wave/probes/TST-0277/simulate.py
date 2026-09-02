"""Deterministic council run: coverage check, recruit, scripted transcript.

Production tools/council/simulate.py is absent. This module is the
confirmation substrate for TST-0277. Personas are seeded state machines
emitting pre-authored briefs, claims, and votes — not live model calls.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from coverage import coverage_check, recruit
from fixtures import (
    BENCH,
    COVERED_RECOMMENDATION,
    DECISION,
    HOLE_SHIP_RECOMMENDATION,
    POST_RECRUIT_RECOMMENDATION,
    RUBBERSTAMP_BRIEF,
)


def _claims_of(seat: Mapping[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for claim in seat.get("claims") or ():
        out.append(
            {
                "id": str(claim["id"]),
                "text": str(claim["text"]),
                "author": str(seat["id"]),
                "role": str(seat.get("role") or ""),
            }
        )
    return out


def _render_seat(seat: Mapping[str, Any], *, rubberstamp: bool) -> str:
    if rubberstamp:
        return (
            f"- {seat['id']} ({seat.get('role')}): {RUBBERSTAMP_BRIEF}"
        )
    lines = [f"- {seat['id']} ({seat.get('role')}): {seat.get('brief')}"]
    for claim in seat.get("claims") or ():
        lines.append(f"  claim {claim['id']}: {claim['text']}")
    return "\n".join(lines)


def simulate(
    panel: Sequence[Mapping[str, Any]],
    *,
    allow_recruit: bool = True,
    recruited_mode: str = "substantive",
    bench: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run coverage, optionally recruit, and emit a transcript.

    recruited_mode:
      substantive — recruited seats emit their authored claims
      rubberstamp — recruited seats emit concurrence only (cosmetic)
    """
    if recruited_mode not in {"substantive", "rubberstamp"}:
        raise ValueError(f"unknown recruited_mode {recruited_mode!r}")

    original = [dict(s) for s in panel]
    report = coverage_check(DECISION["required_competencies"], original)
    seated_ids = [str(s["id"]) for s in original]
    rec = {
        "recruited": [],
        "filled": {},
        "unfilled": list(report["uncovered"]),
        "recruitment_triggered": False,
        "recruitment_executed": False,
    }
    if allow_recruit and report["fires"]:
        rec = recruit(report["uncovered"], bench if bench is not None else BENCH, seated_ids)

    rubber = recruited_mode == "rubberstamp"
    original_claims = []
    for seat in original:
        original_claims.extend(_claims_of(seat))

    recruited_claims: list[dict[str, str]] = []
    if rec["recruited"] and not rubber:
        for seat in rec["recruited"]:
            recruited_claims.extend(_claims_of(seat))

    original_ids = {c["id"] for c in original_claims}
    exclusive = [c for c in recruited_claims if c["id"] not in original_ids]
    cosmetic = bool(rec["recruited"]) and not exclusive

    lines = [
        "# Council transcript",
        "",
        f"## Decision {DECISION['id']}",
        DECISION["question"],
        "",
        "## Required competencies",
        ", ".join(report["required"]),
        "",
        "## Coverage",
        f"covered: {', '.join(report['covered']) or '(none)'}",
        f"uncovered: {', '.join(report['uncovered']) or '(none)'}",
        f"named_gap: {', '.join(report['named_gap']) or '(none)'}",
        f"trigger: {report['trigger'] or '(silent)'}",
        "",
        "## Round 1 original seats",
    ]
    for seat in original:
        lines.append(_render_seat(seat, rubberstamp=False))
    lines.append("")

    if rec["recruitment_executed"]:
        lines.append("## Recruitment")
        for gap, sid in rec["filled"].items():
            lines.append(f"- seated {sid} to cover {gap}")
        if rec["unfilled"]:
            lines.append(f"- unfilled: {', '.join(rec['unfilled'])}")
        lines.append("")
        lines.append("## Round 2 recruited seats")
        for seat in rec["recruited"]:
            lines.append(_render_seat(seat, rubberstamp=rubber))
        lines.append("")
    else:
        lines.append("## Recruitment")
        lines.append("not triggered" if not rec["recruitment_triggered"] else "triggered but no seat available")
        lines.append("")

    if rec["recruitment_executed"] and not rubber:
        recommendation = POST_RECRUIT_RECOMMENDATION
    elif rec["recruitment_executed"] and rubber:
        recommendation = HOLE_SHIP_RECOMMENDATION
    elif not report["fires"]:
        recommendation = COVERED_RECOMMENDATION
    else:
        recommendation = HOLE_SHIP_RECOMMENDATION

    lines.append("## Recommendation")
    lines.append(recommendation)
    lines.append("")
    transcript = "\n".join(lines)

    votes = [str(s.get("vote") or "") for s in original]
    if rec["recruited"] and not rubber:
        votes.extend(str(s.get("vote") or "") for s in rec["recruited"])

    exclusive_by_recruit = {
        c["id"]: {"author": c["author"], "text": c["text"]} for c in exclusive
    }
    return {
        "completed": True,
        "decision_id": DECISION["id"],
        "coverage": report,
        "recruitment": {
            "triggered": rec["recruitment_triggered"],
            "executed": rec["recruitment_executed"],
            "trigger": report["trigger"],
            "filled": dict(rec["filled"]),
            "unfilled": list(rec["unfilled"]),
            "seated_ids": [str(s["id"]) for s in rec["recruited"]],
            "cosmetic": cosmetic,
        },
        "original_seat_ids": seated_ids,
        "original_claims": original_claims,
        "recruited_claims": recruited_claims,
        "exclusive_claims": exclusive,
        "exclusive_by_recruit": exclusive_by_recruit,
        "votes": votes,
        "recommendation": recommendation,
        "transcript": transcript,
        "recruited_mode": recruited_mode,
        "allow_recruit": allow_recruit,
    }


def hole_run(*, recruited_mode: str = "substantive") -> dict[str, Any]:
    from fixtures import HOLE_PANEL

    return simulate(HOLE_PANEL, allow_recruit=True, recruited_mode=recruited_mode)


def covered_run() -> dict[str, Any]:
    from fixtures import COVERED_PANEL

    return simulate(COVERED_PANEL, allow_recruit=True, recruited_mode="substantive")


def synonym_run() -> dict[str, Any]:
    from fixtures import SYNONYM_PANEL

    return simulate(SYNONYM_PANEL, allow_recruit=True, recruited_mode="substantive")
