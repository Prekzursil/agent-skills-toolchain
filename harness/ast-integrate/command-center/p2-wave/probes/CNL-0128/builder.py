#!/usr/bin/env python3
"""Guided structured builder: NL or typed goal-id -> CouncilSpec.

Unrecognized owner language is a named gap (path /natural_language),
never a silent guess. All three surfaces (CLI, SDK, structured builder)
call this same core so they cannot expose different truths.
"""
from __future__ import annotations

from typing import Any

import goals as GO
import spec as S


def match_goal(text: str) -> dict[str, Any] | None:
    if not isinstance(text, str):
        return None
    raw = text.strip()
    if not raw:
        return None
    upper = raw.upper()
    if upper in GO.BY_ID:
        return GO.BY_ID[upper]
    if raw.isdigit() and f"G{raw}" in GO.BY_ID:
        return GO.BY_ID[f"G{raw}"]
    lowered = raw.lower()
    hits = [g for g in GO.GOALS if g["phrase"] in lowered]
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        hits.sort(key=lambda g: len(g["phrase"]), reverse=True)
        return hits[0]
    for g in GO.GOALS:
        if lowered == g["phrase"]:
            return g
    return None


def build_from_goal(text: str, *, surface: str = "builder") -> dict[str, Any]:
    """Always returns {ok, spec?, errors?, gap?} — never raises."""
    try:
        return _build_from_goal(text, surface=surface)
    except Exception as exc:
        return {
            "ok": False,
            "errors": [
                S.error(
                    "/natural_language",
                    "internal-caught",
                    f"{type(exc).__name__}: {exc}",
                )
            ],
            "gap": "internal-caught",
        }


def _build_from_goal(text: str, *, surface: str) -> dict[str, Any]:
    goal = match_goal(text)
    if goal is None:
        err = S.error(
            "/natural_language",
            "unrecognized-goal",
            "named gap: owner language does not match any of the five catalog goals",
        )
        return {
            "ok": False,
            "errors": [err],
            "gap": "unrecognized-goal",
            "named_gap": True,
        }
    spec = S.envelope(goal, surface=surface)
    errs = S.validate(spec)
    if errs:
        return {"ok": False, "spec": spec, "errors": errs, "gap": None}
    return {
        "ok": True,
        "spec": spec,
        "errors": [],
        "gap": None,
        "restatement": S.restatement(spec),
        "goal_id": goal["id"],
    }


def build_from_answers(answers: dict[str, Any], *, surface: str = "builder") -> dict[str, Any]:
    """Typed structured-builder answers. Question 1: which of the five goals?"""
    try:
        if not isinstance(answers, dict):
            return {
                "ok": False,
                "errors": [S.error("/answers", "type", "answers must be an object")],
            }
        gid = answers.get("goal_id") or answers.get("goal")
        if not isinstance(gid, str):
            return {
                "ok": False,
                "errors": [
                    S.error(
                        "/answers/goal_id",
                        "required",
                        "typed builder requires goal_id in {G1..G5}",
                    )
                ],
                "gap": "missing-goal-id",
            }
        return build_from_goal(gid, surface=surface)
    except Exception as exc:
        return {
            "ok": False,
            "errors": [
                S.error("/answers", "internal-caught", f"{type(exc).__name__}: {exc}")
            ],
        }


def round_trip(text: str, *, surface: str = "builder") -> dict[str, Any]:
    built = build_from_goal(text, surface=surface)
    if not built.get("ok"):
        return {**built, "round_trip": False}
    spec = built["spec"]
    goal = GO.BY_ID[spec["goal_id"]]
    restated = S.restatement(spec)
    tokens = [t.lower() for t in goal["required_tokens"]]
    blob = (restated + " " + spec["natural_language"] + " " + spec["stopping_expr"]).lower()
    # Restatement is derived from fields; required tokens must appear in
    # restatement OR in the encoded fields that the restatement names.
    missing = []
    rest_l = restated.lower()
    expr_l = str(spec["stopping_expr"]).lower()
    outputs = spec.get("outputs") or {}
    extra = " ".join(str(v) for v in outputs.values()).lower()
    hay = rest_l + " " + expr_l + " " + extra
    # G2 "agree" is encoded as unanimity; accept that synonym in haystack.
    synonyms = {
        "agree": ("agree", "unanimity", "unanim"),
        "two": ("two", "2"),
        "90": ("90", "0.90", "0.9"),
        "test": ("test", "quality_gate"),
        "settles": ("settles", "pass", "quality_gate"),
        "rounds": ("rounds", "max_rounds", "counterexample_rounds"),
        "ideas": ("ideas", "unique_ideas"),
        "unique": ("unique", "unique_ideas"),
        "100": ("100",),
        "12": ("12",),
        "consensus": ("consensus",),
        "minority": ("minority",),
        "counterexample": ("counterexample",),
    }
    for tok in tokens:
        alts = synonyms.get(tok, (tok,))
        if not any(a in hay for a in alts):
            missing.append(tok)
    ok = not missing and spec["stopping_expr"] == goal["stopping_expr"]
    if goal["minority_report"] == "mandatory" and outputs.get("minority_report") != "mandatory":
        ok = False
        missing.append("minority_report=mandatory")
    return {
        **built,
        "round_trip": ok,
        "restatement": restated,
        "missing_tokens": missing,
        "named_gap": (not ok),
    }
