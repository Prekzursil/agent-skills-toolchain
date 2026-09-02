"""Independent reliability reviewer for ARC-0026.

Adds one failure mode the author's id-granular three-bit signal misses:
partial materialization of a multi-payload capability. Does NOT certify
the 47-class enumeration complete; the cited prompt file is absent.
"""
from __future__ import annotations

ADDED_MODE = {
    "id": "FM-PARTIAL-MATERIALIZE",
    "title": "Skill half activates while the stdio MCP half never spawns",
    "author_missed": True,
    "caught_by_three_bit_signal": False,
    "seeded_classes": [
        "plugin appears installed but hooks are unloaded",
        "eager per-session MCP process multiplication",
        "router fails to select an installed skill",
    ],
    "description": (
        "A capability id can map to a skill file AND a stdio MCP server. The "
        "author signal is per-id. Selecting the id and loading the skill sets "
        "activation=ok / AVAILABLE while the MCP child was never spawned (or "
        "the reverse). FM-SILENT-EQUIV stays green because the id is indexed "
        "and selected; FM-PROCESS-MULT stays green because no extra process "
        "appeared. Split-plane activation is a third axis."
    ),
    "required_followup": (
        "Emit the three-bit signal per payload part (skill / hook / mcp), not "
        "only per capability id. Do not rebuild A4 DESIGN.json in this unit "
        "(that is ARC-0024)."
    ),
}


def review() -> dict:
    return {
        "reviewer_id": "ARC-0026-independent-reliability",
        "verdict": "PASS",
        "independent": True,
        "scope_not_agreement": True,
        "fresh_context": True,
        "enumeration_certified_against_47": False,
        "enumeration_certify_reason": (
            "The 47 seeded classes are cited as _USER-PROMPTS.md:11300-11347. "
            "That file is not on this worktree. Certifying completeness against "
            "an unread list would be overclaim. Instead the reviewer adds "
            "FM-PARTIAL-MATERIALIZE, which the author's per-id list missed."
        ),
        "added_failure_mode": ADDED_MODE,
        "method": (
            "Reviewed the author's four catalog-named modes plus the three-bit "
            "signal and the two process probes. Checked both-states codes "
            "differ, collapsed bits do not, ceiling plant fires, and today's "
            "process numbers are not the estate 2037 figure. Agreement with "
            "the linear-not-P1 verdict is not required for PASS; scope is: "
            "distinguishing observable, two-probe re-measure, one missed mode."
        ),
    }
