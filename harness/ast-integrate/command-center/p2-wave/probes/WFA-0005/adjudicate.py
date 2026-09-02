"""Adjudicate unused vocabulary: KEEP vs DELETE.

A value may be deleted only with a written argument. Spec-named values also
require an owner-visible note. Count == 0 is never sufficient.
"""
from __future__ import annotations

from typing import Any

from vocabulary import RULES, UNUSED_VALUES, is_spec_named

KEEP_UNEXERCISED = "KEEP-UNEXERCISED-VALID"
KEEP_SHOULD_CARRY = "KEEP-SOME-CANDIDATES-SHOULD-CARRY"
DELETE_DEAD = "DELETE-DEAD-VOCABULARY"


def may_delete(
    value: str,
    *,
    count: int,
    written_argument: str | None,
    owner_visible_note: str | None,
) -> dict[str, Any]:
    spec = is_spec_named(value)
    if count == 0 and not (written_argument and str(written_argument).strip()):
        return {
            "allowed": False,
            "reason": "zero-count-is-not-deletion-grounds",
            "spec_named": spec,
        }
    if spec and not (owner_visible_note and str(owner_visible_note).strip()):
        return {
            "allowed": False,
            "reason": "spec-named-value-requires-owner-visible-note",
            "spec_named": spec,
        }
    if not (written_argument and str(written_argument).strip()):
        return {
            "allowed": False,
            "reason": "deletion-requires-written-argument",
            "spec_named": spec,
        }
    return {"allowed": True, "reason": "written-argument-and-owner-note", "spec_named": spec}


def adjudicate_value(
    value: str,
    *,
    live_count: int | None,
    live_should_hits: int,
    planted_fired: bool,
    live_corpus_present: bool,
) -> dict[str, Any]:
    deletion = may_delete(
        value,
        count=int(live_count or 0),
        written_argument=None,
        owner_visible_note=None,
    )
    if live_corpus_present and live_should_hits > 0:
        verdict = KEEP_SHOULD_CARRY
        note = (
            f"Signal B found {live_should_hits} live free-text hit(s) that "
            f"satisfy the {value} decision rule while Signal A count is "
            f"{live_count}. The value is valid and at least one candidate "
            "should carry it."
        )
    else:
        verdict = KEEP_UNEXERCISED
        if not live_corpus_present:
            note = (
                f"{value} is spec-named. Live 284-row registry is absent, so "
                "this unit does not claim a live candidate should carry it. "
                "Zero catalog-stated count is not deletion grounds. Planted "
                f"search fired={planted_fired}."
            )
        else:
            note = (
                f"{value} remains valid unexercised vocabulary. Live Signal B "
                "hits=0 is not evidence the rule is empty; it is evidence no "
                f"does/mechanisms/notes blob on this corpus matched. Planted "
                f"search fired={planted_fired}."
            )
    return {
        "value": value,
        "verdict": verdict,
        "deleted": False,
        "deletion_allowed": deletion["allowed"],
        "deletion_blocked_because": deletion["reason"],
        "live_count": live_count,
        "live_should_hits": live_should_hits,
        "planted_fired": planted_fired,
        "decision_rule": RULES[value]["decision_rule"],
        "keep_argument": RULES[value]["keep_argument"],
        "owner_visible_note": None,
        "note": note,
    }


def adjudicate_all(
    *,
    live_counts: dict[str, int] | None,
    live_hits: dict[str, list],
    planted_hits: dict[str, list],
    live_corpus_present: bool,
) -> list[dict[str, Any]]:
    rows = []
    for value in UNUSED_VALUES:
        live_count = None if live_counts is None else int(live_counts.get(value) or 0)
        rows.append(
            adjudicate_value(
                value,
                live_count=live_count,
                live_should_hits=len(live_hits.get(value) or []),
                planted_fired=bool(planted_hits.get(value)),
                live_corpus_present=live_corpus_present,
            )
        )
    return rows
