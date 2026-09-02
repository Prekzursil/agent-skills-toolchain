"""Deterministic council synthesis stage under test for CNF-0088.

Production tools/council is absent on this worktree. This module is the
confirmation substrate: unanimous-or-record-dissent, with a verbatim minority
channel. Modes other than 'preserve' exist only so detectors can fire on
planted defects (drop / paraphrase / generic / fabricate).
"""
from __future__ import annotations

from typing import Any

from fixtures import (
    CONDITIONAL_RECOMMENDATION,
    DISSENTER,
    DISSENTER_ID,
    GENERIC_MENTION,
    INJECTED_POSITION,
    MAJORITY_BRIEFS,
    MAJORITY_RECOMMENDATION,
    PARAPHRASE_INTO_AGREEMENT,
)

MODES = ("preserve", "drop", "paraphrase", "generic", "fabricate")


def _majority_section(briefs: list[dict[str, str]]) -> list[str]:
    lines = ["# Council synthesis", "", "## Majority briefs"]
    for brief in briefs:
        lines.append(f"- {brief['id']} ({brief['role']}): {brief['brief']}")
    lines.append("")
    return lines


def synthesize(
    *,
    include_dissenter: bool,
    mode: str = "preserve",
) -> dict[str, Any]:
    """Run one synthesis. `mode` is ignored for the no-dissenter happy path
    except `fabricate`, which plants a false minority report."""
    if mode not in MODES:
        raise ValueError(f"unknown synthesis mode {mode!r}")

    briefs = [dict(b) for b in MAJORITY_BRIEFS]
    minority = dict(DISSENTER) if include_dissenter else None
    lines = _majority_section(briefs)
    minority_report: dict[str, Any] | None = None
    recommendation = MAJORITY_RECOMMENDATION

    if include_dissenter and mode == "preserve":
        assert minority is not None
        lines.append("## Minority report")
        lines.append(f"Attributed to {minority['id']} ({minority['role']}):")
        lines.append(minority["position"])
        lines.append("")
        recommendation = CONDITIONAL_RECOMMENDATION
        minority_report = {
            "participant_id": minority["id"],
            "role": minority["role"],
            "attributed_to": minority["id"],
            "verbatim_position": minority["position"],
            "present": True,
        }
    elif include_dissenter and mode == "drop":
        recommendation = MAJORITY_RECOMMENDATION
    elif include_dissenter and mode == "paraphrase":
        assert minority is not None
        lines.append("## Minority report")
        lines.append(f"Attributed to {minority['id']} ({minority['role']}):")
        lines.append(PARAPHRASE_INTO_AGREEMENT)
        lines.append("")
        recommendation = MAJORITY_RECOMMENDATION
        minority_report = {
            "participant_id": minority["id"],
            "role": minority["role"],
            "attributed_to": minority["id"],
            "verbatim_position": PARAPHRASE_INTO_AGREEMENT,
            "present": True,
            "paraphrased": True,
        }
    elif include_dissenter and mode == "generic":
        lines.append("## Notes")
        lines.append(GENERIC_MENTION)
        lines.append("")
        recommendation = MAJORITY_RECOMMENDATION
    elif (not include_dissenter) and mode == "fabricate":
        lines.append("## Minority report")
        lines.append(f"Attributed to {DISSENTER_ID} (Skeptic):")
        lines.append(INJECTED_POSITION)
        lines.append("")
        recommendation = CONDITIONAL_RECOMMENDATION
        minority_report = {
            "participant_id": DISSENTER_ID,
            "role": "Skeptic",
            "attributed_to": DISSENTER_ID,
            "verbatim_position": INJECTED_POSITION,
            "present": True,
            "fabricated": True,
        }

    lines.append("## Recommendation")
    lines.append(recommendation)
    text = "\n".join(lines) + "\n"

    votes = [b["vote"] for b in briefs]
    if include_dissenter:
        votes.append(DISSENTER["vote"])
    unanimous = len(set(votes)) == 1

    return {
        "completed": True,
        "mode": mode,
        "include_dissenter": include_dissenter,
        "unanimous": unanimous,
        "votes": votes,
        "recommendation": recommendation,
        "synthesis_text": text,
        "minority_report": minority_report,
        "injected_position": INJECTED_POSITION if include_dissenter else None,
        "dissenter_id": DISSENTER_ID if include_dissenter else None,
    }


def with_dissenter(mode: str = "preserve") -> dict[str, Any]:
    return synthesize(include_dissenter=True, mode=mode)


def without_dissenter(mode: str = "preserve") -> dict[str, Any]:
    return synthesize(include_dissenter=False, mode=mode)
