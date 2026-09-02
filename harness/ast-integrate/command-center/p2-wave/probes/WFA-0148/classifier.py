#!/usr/bin/env python3
"""15-value disposition classifier with a total first-match tie-break.

A value this function cannot emit is a proven blind spot, not a corpus
property. `skip_values` deletes a rule so the plant probe can prove it
would catch that blind spot.
"""
from __future__ import annotations

from typing import Any, Callable

VOCABULARY: tuple[str, ...] = (
    "ADOPT-AS-IS",
    "ADOPT-WITH-WRAPPER",
    "CLEAN-ROOM-REIMPLEMENT",
    "COMPOSE",
    "DISTILL",
    "EXTEND",
    "GENERALIZE",
    "MERGE",
    "REBUILD-FROM-SPEC",
    "REJECT",
    "REPAIR",
    "RETIRE",
    "SPECIALIZE",
    "TRANSLATE",
    "UNKNOWN-NEEDS-PROBE",
)

UNUSED_DECLARED: tuple[str, ...] = (
    "CLEAN-ROOM-REIMPLEMENT",
    "COMPOSE",
    "GENERALIZE",
    "REBUILD-FROM-SPEC",
    "REJECT",
    "TRANSLATE",
)

USED_DECLARED: tuple[str, ...] = (
    "ADOPT-AS-IS",
    "UNKNOWN-NEEDS-PROBE",
    "DISTILL",
    "RETIRE",
    "ADOPT-WITH-WRAPPER",
    "REPAIR",
    "EXTEND",
    "MERGE",
    "SPECIALIZE",
)

INCOMPATIBLE_LICENSES = frozenset(
    {"UNKNOWN", "INCOMPATIBLE", "PROPRIETARY-UNLICENSED"}
)

Predicate = Callable[[dict[str, Any]], bool]


def _missing_required(rec: dict[str, Any]) -> bool:
    if not str(rec.get("id") or "").strip():
        return True
    return not str(rec.get("does") or "").strip()


def _license_key(rec: dict[str, Any]) -> str:
    return str(rec.get("license") or "").strip().upper()


RULES: tuple[tuple[str, Predicate], ...] = (
    ("UNKNOWN-NEEDS-PROBE", _missing_required),
    (
        "REJECT",
        lambda r: bool(
            r.get("harmful") or r.get("out_of_scope") or r.get("explicit_reject")
        ),
    ),
    ("RETIRE", lambda r: bool(r.get("archived") or r.get("superseded"))),
    (
        "CLEAN-ROOM-REIMPLEMENT",
        lambda r: _license_key(r) in INCOMPATIBLE_LICENSES and bool(r.get("wanted")),
    ),
    (
        "TRANSLATE",
        lambda r: bool(
            r.get("runtime")
            and r.get("control_plane")
            and r.get("runtime") != r.get("control_plane")
        ),
    ),
    (
        "REBUILD-FROM-SPEC",
        lambda r: bool(r.get("spec_available"))
        and bool(r.get("rebuild_cheaper") or r.get("source_non_transferable")),
    ),
    (
        "COMPOSE",
        lambda r: isinstance(r.get("compose_parts"), list)
        and len(r.get("compose_parts") or []) >= 2,
    ),
    ("GENERALIZE", lambda r: bool(r.get("generalize_from"))),
    ("SPECIALIZE", lambda r: bool(r.get("specialize_of"))),
    ("MERGE", lambda r: bool(r.get("merge_with"))),
    ("REPAIR", lambda r: bool(r.get("repairable_defects"))),
    ("DISTILL", lambda r: bool(r.get("distill_mechanisms"))),
    ("EXTEND", lambda r: bool(r.get("extend_with"))),
    ("ADOPT-WITH-WRAPPER", lambda r: bool(r.get("needs_wrapper"))),
    ("ADOPT-AS-IS", lambda r: True),
)

TIE_BREAK_ORDER: tuple[str, ...] = tuple(name for name, _ in RULES)

assert len(TIE_BREAK_ORDER) == 15
assert set(TIE_BREAK_ORDER) == set(VOCABULARY)
assert set(USED_DECLARED) | set(UNUSED_DECLARED) == set(VOCABULARY)
assert not (set(USED_DECLARED) & set(UNUSED_DECLARED))


def classify(
    rec: dict[str, Any],
    *,
    skip_values: frozenset[str] | set[str] = frozenset(),
) -> dict[str, Any]:
    skip = frozenset(skip_values)
    for index, (name, pred) in enumerate(RULES):
        if name in skip:
            continue
        if pred(rec):
            return {
                "classification": name,
                "rule_id": f"R{index:02d}-{name}",
                "rule_index": index,
                "reason": f"first-match tie-break at {name}",
            }
    return {
        "classification": "UNKNOWN-NEEDS-PROBE",
        "rule_id": "R-FALLBACK-UNKNOWN",
        "rule_index": -1,
        "reason": "no remaining rule fired after skips",
    }
