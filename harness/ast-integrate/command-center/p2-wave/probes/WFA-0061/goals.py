"""Route coverage gaps to the generation lane as typed goals, not a bare list."""
from __future__ import annotations

from typing import Any

LANE = "generation"


def _goal(
    *,
    gap_id: str,
    direction: str,
    kind: str,
    target: str,
    why: str,
) -> dict[str, Any]:
    return {
        "goal_id": f"gen.WFA-0061.{direction}.{gap_id}",
        "lane": LANE,
        "kind": kind,
        "target": target,
        "constraints": {
            "implement_from_definition": True,
            "prose_self_description_insufficient": True,
            "closed_vocabulary": True,
            "namespace": "mech.",
        },
        "source_gap": {"direction": direction, "id": gap_id},
        "spec_anchor": "WFA-0061 tests_required[2] gaps routed as typed goals",
        "why": why,
    }


def route_gaps(
    uncovered: list[str],
    empty_blueprints: list[str],
    *,
    live_library_present: bool,
) -> list[dict[str, Any]]:
    goals: list[dict[str, Any]] = []
    for mid in uncovered:
        goals.append(
            _goal(
                gap_id=mid,
                direction="uncovered_mechanism",
                kind="cover-mechanism-with-blueprint",
                target=mid,
                why=(
                    "Canonical mechanism is implemented by at least one candidate "
                    "and by zero blueprints in the measured corpus."
                ),
            )
        )
    for bid in empty_blueprints:
        goals.append(
            _goal(
                gap_id=bid,
                direction="empty_blueprint",
                kind="implement-recognised-mechanism-in-blueprint",
                target=bid,
                why=(
                    "Blueprint body yields zero closed-vocabulary mechanisms "
                    "after definition extraction."
                ),
            )
        )
    if not live_library_present:
        goals.append(
            {
                "goal_id": "gen.WFA-0061.restore-named-library",
                "lane": LANE,
                "kind": "restore-named-source-then-recompute",
                "target": "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
                "constraints": {
                    "catalog_claimed_n": 108,
                    "do_not_invent_records": True,
                    "recompute_both_directions": True,
                },
                "source_gap": {
                    "direction": "named-source-absent",
                    "id": "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
                },
                "spec_anchor": "WFA-0061 inputs[1] 108 blueprints, 20 families",
                "why": (
                    "The catalog's 108-blueprint library is not on this worktree. "
                    "Restore the file, extract via WFA-0059, and re-run both "
                    "set differences. Do not pad the fixture to 108."
                ),
            }
        )
    return goals


def typed_goal_index(goals: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for g in goals:
        if not isinstance(g, dict):
            continue
        sg = g.get("source_gap") or {}
        gid = str(sg.get("id") or "")
        if gid:
            out[gid] = g
    return out


def goals_cover_gaps(
    goals: list[dict[str, Any]],
    uncovered: list[str],
    empty_blueprints: list[str],
) -> tuple[bool, list[str]]:
    idx = typed_goal_index(goals)
    missing: list[str] = []
    for gid in list(uncovered) + list(empty_blueprints):
        g = idx.get(gid)
        if not isinstance(g, dict):
            missing.append(gid)
            continue
        if g.get("lane") != LANE:
            missing.append(gid)
            continue
        if not str(g.get("kind") or "").strip():
            missing.append(gid)
            continue
        if not str(g.get("target") or "").strip():
            missing.append(gid)
    return (not missing), missing


def looks_like_bare_id_list(goals: Any) -> bool:
    """True when routing collapsed to a list of strings (the forbidden shape)."""
    if not isinstance(goals, list) or not goals:
        return True
    return all(isinstance(g, str) for g in goals)
