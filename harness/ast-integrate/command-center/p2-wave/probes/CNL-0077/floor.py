#!/usr/bin/env python3
"""Minimum-deliberation floors that outrank ANY stopping expression.

Floors are a PRECONDITION on FIRE, not a conjunct of the expression.
A satisfied stop that cannot fire yields STOP-BLOCKED-BY-FLOOR plus an
audit record naming the unmet floor(s). A floor with no ceiling is
rejected at validation because it is a hang.

Source files named by CNL-0077 (Windows harness-restore paths) are ABSENT
on this worktree. Condition names are taken from on-tree catalog quotes
of spec :10762 / failure class :11338, not from the missing markdown.
"""
from __future__ import annotations

from typing import Any

CONTINUE = "CONTINUE"
TERMINATE = "TERMINATE"

FIRE = "FIRE"
STOP_BLOCKED_BY_FLOOR = "STOP-BLOCKED-BY-FLOOR"
FLOOR_UNMET_AT_CEILING = "FLOOR-UNMET-AT-CEILING"
CEILING_WITHOUT_STOP = "CEILING-WITHOUT-STOP"
SILENT = "SILENT"
PREMATURE_STOP = "PREMATURE-STOP"
SPEC_INVALID = "SPEC-INVALID"

HARD_LOWER = {
    "min_rounds": 1,
    "min_independent_briefs": 1,
    "min_evidence_items": 1,
    "mandated_roles": 1,
}

# DESIGN-DEFAULT values. Not claimed as verbatim :10762 numerals: that
# file is absent here. TST-0264 only proves min_rounds=0 is illegal.
DESIGN_DEFAULTS = {
    "min_rounds": 2,
    "min_independent_briefs": 2,
    "min_evidence_items": 1,
    "max_rounds": 12,
    "mandated_roles": ["advocate", "critic"],
    "speaking_roles": ["advocate", "critic", "chair"],
}

FLOOR_IDS = (
    "min_rounds",
    "min_independent_briefs",
    "min_evidence_items",
    "mandated_roles_spoken",
)


def default_spec(**overrides: Any) -> dict[str, Any]:
    spec = {
        "min_rounds": DESIGN_DEFAULTS["min_rounds"],
        "min_independent_briefs": DESIGN_DEFAULTS["min_independent_briefs"],
        "min_evidence_items": DESIGN_DEFAULTS["min_evidence_items"],
        "max_rounds": DESIGN_DEFAULTS["max_rounds"],
        "mandated_roles": list(DESIGN_DEFAULTS["mandated_roles"]),
        "speaking_roles": list(DESIGN_DEFAULTS["speaking_roles"]),
        "gate_enabled": True,
    }
    spec.update(overrides)
    return spec


def count_independent_briefs(briefs: list[dict] | None) -> int:
    """Independent opening positions: distinct speakers, non-empty text,
    not byte-identical to an earlier opening brief."""
    n = 0
    seen_speakers: set[str] = set()
    seen_texts: set[str] = set()
    for brief in briefs or []:
        if not isinstance(brief, dict):
            continue
        if brief.get("phase") not in (None, "opening"):
            continue
        speaker = str(brief.get("speaker_id") or "").strip()
        text = str(brief.get("text") or "").strip()
        if not speaker or not text:
            continue
        if speaker in seen_speakers:
            continue
        if text in seen_texts:
            continue
        seen_speakers.add(speaker)
        seen_texts.add(text)
        n += 1
    return n


def count_evidence_items(items: list[dict] | None) -> int:
    n = 0
    seen: set[tuple[str, str]] = set()
    for item in items or []:
        if not isinstance(item, dict):
            continue
        claim = str(item.get("claim_id") or "").strip()
        locator = str(item.get("locator") or "").strip()
        if not claim or not locator:
            continue
        key = (claim, locator)
        if key in seen:
            continue
        seen.add(key)
        n += 1
    return n


def roles_spoken(turns: list[dict] | None) -> set[str]:
    out: set[str] = set()
    for turn in turns or []:
        if not isinstance(turn, dict):
            continue
        role = str(turn.get("role") or "").strip()
        if role:
            out.add(role)
    return out


def validate_spec(spec: dict[str, Any]) -> list[str]:
    """Return rejection reasons. Empty means the spec may run."""
    reasons: list[str] = []
    if not isinstance(spec, dict):
        return ["spec-not-object"]

    def as_int(key: str) -> int | None:
        val = spec.get(key)
        if isinstance(val, bool) or not isinstance(val, int):
            reasons.append(f"{key}-not-int")
            return None
        return val

    min_rounds = as_int("min_rounds")
    min_briefs = as_int("min_independent_briefs")
    min_evidence = as_int("min_evidence_items")
    if "max_rounds" not in spec:
        reasons.append("floor-with-no-ceiling")
        max_rounds = None
    else:
        max_rounds = as_int("max_rounds")

    if min_rounds is not None and min_rounds < HARD_LOWER["min_rounds"]:
        reasons.append("min_rounds-below-hard-lower")
    if min_briefs is not None and min_briefs < HARD_LOWER["min_independent_briefs"]:
        reasons.append("min_independent_briefs-below-hard-lower")
    if min_evidence is not None and min_evidence < HARD_LOWER["min_evidence_items"]:
        reasons.append("min_evidence_items-below-hard-lower")
    if (
        min_rounds is not None
        and max_rounds is not None
        and min_rounds > max_rounds
    ):
        reasons.append("min_rounds-exceeds-ceiling")
    if max_rounds is not None and max_rounds < HARD_LOWER["min_rounds"]:
        reasons.append("max_rounds-below-hard-lower")

    speaking = spec.get("speaking_roles")
    mandated = spec.get("mandated_roles")
    if not isinstance(speaking, list) or not speaking:
        reasons.append("speaking_roles-empty")
        speaking_set: set[str] = set()
    else:
        speaking_set = {str(x) for x in speaking if str(x).strip()}
        if len(speaking_set) != len(speaking):
            reasons.append("speaking_roles-duplicate-or-blank")
    if not isinstance(mandated, list) or len(mandated) < HARD_LOWER["mandated_roles"]:
        reasons.append("mandated_roles-below-hard-lower")
        mandated_set: set[str] = set()
    else:
        mandated_set = {str(x) for x in mandated if str(x).strip()}
        if len(mandated_set) != len(mandated):
            reasons.append("mandated_roles-duplicate-or-blank")
        missing = mandated_set - speaking_set
        if missing:
            reasons.append("mandated-role-not-in-roster")
    if min_briefs is not None and min_briefs > len(speaking_set):
        reasons.append("min_independent_briefs-unsatisfiable")
    return reasons


def floors_unmet(spec: dict[str, Any], state: dict[str, Any]) -> list[dict[str, Any]]:
    unmet: list[dict[str, Any]] = []
    rnd = int(state.get("round") or 0)
    briefs = count_independent_briefs(state.get("briefs"))
    evidence = count_evidence_items(state.get("evidence"))
    spoken = roles_spoken(state.get("turns"))
    mandated = [str(x) for x in (spec.get("mandated_roles") or [])]

    required_rounds = int(spec["min_rounds"])
    if rnd < required_rounds:
        unmet.append(
            {
                "id": "min_rounds",
                "required": required_rounds,
                "observed": rnd,
            }
        )
    required_briefs = int(spec["min_independent_briefs"])
    if briefs < required_briefs:
        unmet.append(
            {
                "id": "min_independent_briefs",
                "required": required_briefs,
                "observed": briefs,
            }
        )
    required_evidence = int(spec["min_evidence_items"])
    if evidence < required_evidence:
        unmet.append(
            {
                "id": "min_evidence_items",
                "required": required_evidence,
                "observed": evidence,
            }
        )
    missing_roles = [r for r in mandated if r not in spoken]
    if missing_roles:
        unmet.append(
            {
                "id": "mandated_roles_spoken",
                "required": list(mandated),
                "observed": sorted(spoken),
                "missing": missing_roles,
            }
        )
    return unmet


def evaluate(
    spec: dict[str, Any],
    state: dict[str, Any],
    stop_expression_true: bool,
) -> dict[str, Any]:
    """One evaluation tick. Cadence is owned by CNL-0076 (absent on this
    tree); this gate attaches to whichever tick evaluates the expression
    and never fires independently mid-turn."""
    errors = validate_spec(spec)
    if errors:
        return {
            "action": TERMINATE,
            "reason": SPEC_INVALID,
            "stop_expression_true": bool(stop_expression_true),
            "would_fire_without_floor": bool(stop_expression_true),
            "floors_unmet": [],
            "validation_errors": errors,
            "round": int(state.get("round") or 0),
            "max_rounds": spec.get("max_rounds"),
            "gate_enabled": bool(spec.get("gate_enabled", True)),
        }

    gate_enabled = bool(spec.get("gate_enabled", True))
    observed_unmet = floors_unmet(spec, state)
    unmet = observed_unmet if gate_enabled else []
    rnd = int(state.get("round") or 0)
    max_rounds = int(spec["max_rounds"])
    at_ceiling = rnd >= max_rounds
    stop = bool(stop_expression_true)

    if stop and not unmet:
        reason = FIRE
        action = TERMINATE
    elif stop and unmet:
        if at_ceiling:
            reason = FLOOR_UNMET_AT_CEILING
            action = TERMINATE
        else:
            reason = STOP_BLOCKED_BY_FLOOR
            action = CONTINUE
    elif at_ceiling:
        reason = CEILING_WITHOUT_STOP
        action = TERMINATE
    else:
        reason = SILENT
        action = CONTINUE

    if (not gate_enabled) and stop and observed_unmet:
        reason = PREMATURE_STOP
        action = TERMINATE

    return {
        "action": action,
        "reason": reason,
        "stop_expression_true": stop,
        "would_fire_without_floor": stop,
        "floors_unmet": observed_unmet,
        "validation_errors": [],
        "round": rnd,
        "max_rounds": max_rounds,
        "gate_enabled": gate_enabled,
        "event": reason,
    }


def simulate(
    spec: dict[str, Any],
    timeline: list[dict[str, Any]],
    *,
    hang_guard: int | None = None,
) -> dict[str, Any]:
    """Drive a bounded timeline. Terminates at first TERMINATE, or raises
    if the kernel returns CONTINUE past hang_guard (default max_rounds+1).
    """
    errors = validate_spec(spec)
    if errors:
        return {
            "terminated": True,
            "reason": SPEC_INVALID,
            "ticks": [],
            "validation_errors": errors,
            "iterations": 0,
            "hung": False,
        }
    max_rounds = int(spec["max_rounds"])
    guard = hang_guard if hang_guard is not None else max_rounds + 1
    ticks: list[dict[str, Any]] = []
    last: dict[str, Any] | None = None
    hung = False
    for i, snap in enumerate(timeline, 1):
        if i > guard:
            hung = True
            break
        state = snap.get("state") or {}
        stop = bool(snap.get("stop_expression_true"))
        last = evaluate(spec, state, stop)
        last = dict(last)
        last["iteration"] = i
        ticks.append(last)
        if last["action"] == TERMINATE:
            break
    else:
        if last is not None and last["action"] == CONTINUE:
            hung = True
    if last is None:
        hung = True
        last = {
            "action": CONTINUE,
            "reason": SILENT,
            "floors_unmet": [],
            "validation_errors": [],
        }
    return {
        "terminated": last["action"] == TERMINATE and not hung,
        "reason": last["reason"],
        "ticks": ticks,
        "validation_errors": [],
        "iterations": len(ticks),
        "hung": hung,
        "final": last,
    }


def never_meet_timeline(rounds: int, stop_true: bool = True) -> list[dict[str, Any]]:
    """Round-by-round snapshots that never satisfy briefs/evidence/roles."""
    out = []
    for rnd in range(1, rounds + 1):
        out.append(
            {
                "stop_expression_true": stop_true,
                "state": {
                    "round": rnd,
                    "briefs": [],
                    "evidence": [],
                    "turns": [],
                },
            }
        )
    return out
