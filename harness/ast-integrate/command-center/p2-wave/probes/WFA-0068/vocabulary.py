"""Closed 15-value disposition vocabulary and falsifiable matchers.

The spec list at _USER-PROMPTS.md:10723 (via WFA-0005) is authoritative.
Zero corpus count is not deletion. Required-input refusal is UNKNOWN-NEEDS-PROBE
and is applied before any positive rule.
"""
from __future__ import annotations

from typing import Any, Callable

# Spec order is not tie-break order. Tie-break is TIE_BREAK below.
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

CONTROL_PLANE = frozenset({"claude-code", "claude-workflows"})
FOREIGN_RUNTIMES = frozenset({"n8n", "langgraph", "temporal", "crewai", "airflow"})
PERMISSIVE = frozenset({"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC"})
CLEAN_ROOM_LICENSES = frozenset({"UNLICENSED", "INCOMPATIBLE", "UNKNOWN"})

# Missing any of these (None, "", or three-state EMPTY) refuses to UNKNOWN.
REQUIRED_INPUTS: tuple[str, ...] = (
    "id",
    "family",
    "license",
    "maintenance",
    "provenance",
    "runtime",
    "mechanisms",
)

FAMILIES: tuple[str, ...] = (
    "A-saved-workflow",
    "B-repo-workflow",
    "C-repo-tool",
    "D-harness-runtime",
    "E-agent",
    "F-plugin",
    "G-skill",
    "H-executed-corpus",
    "I-command",
)


def _empty(value: Any) -> bool:
    if value is None:
        return True
    if value == "":
        return True
    if value == "EMPTY":
        return True
    if value == []:
        return True
    return False


def missing_required(record: dict) -> str | None:
    """Name of the first required input that is silently empty. None if complete."""
    if record.get("extraction_complete") is not True:
        return "extraction_complete"
    for field in REQUIRED_INPUTS:
        if _empty(record.get(field)):
            return field
    return None


def match_unknown_probe(record: dict) -> bool:
    return record.get("probe_needed") is True


def match_reject(record: dict) -> bool:
    return record.get("fitness") == "unfit" or record.get("safety") == "hostile"


def match_retire(record: dict) -> bool:
    return record.get("lifecycle") == "retired" or record.get("source_state") == "deleted"


def match_translate(record: dict) -> bool:
    return record.get("runtime") in FOREIGN_RUNTIMES


def match_clean_room(record: dict) -> bool:
    return record.get("license") in CLEAN_ROOM_LICENSES and record.get("reimplementable") is True


def match_rebuild(record: dict) -> bool:
    return record.get("source_state") == "unusable" and record.get("spec_present") is True


def match_compose(record: dict) -> bool:
    parts = record.get("compose_of")
    return isinstance(parts, list) and len(parts) >= 2


def match_merge(record: dict) -> bool:
    dup = record.get("duplicate_of")
    return isinstance(dup, str) and bool(dup.strip())


def match_generalize(record: dict) -> bool:
    return record.get("specificity") == "too-narrow"


def match_specialize(record: dict) -> bool:
    return record.get("specificity") == "too-broad"


def match_extend(record: dict) -> bool:
    gaps = record.get("gaps") or []
    defects = record.get("defects") or []
    return bool(gaps) and not defects and record.get("core_intact") is True


def match_repair(record: dict) -> bool:
    defects = record.get("defects") or []
    return bool(defects) and record.get("salvageable") is True


def match_distill(record: dict) -> bool:
    return record.get("take_whole") is False and record.get("mechanism_worth_keeping") is True


def match_wrapper(record: dict) -> bool:
    return record.get("needs_wrapper") is True and record.get("runtime") not in FOREIGN_RUNTIMES


def match_adopt(record: dict) -> bool:
    return (
        record.get("runtime") in CONTROL_PLANE
        and record.get("smoke_passes") is True
        and record.get("needs_wrapper") is not True
        and not (record.get("defects") or [])
        and not (record.get("gaps") or [])
        and record.get("license") in PERMISSIVE
        and record.get("take_whole") is not False
        and record.get("probe_needed") is not True
    )


Matcher = Callable[[dict], bool]

# Total order: unique ranks 0..14. Lower rank wins when two rules fire.
RULES: tuple[dict[str, Any], ...] = (
    {
        "value": "UNKNOWN-NEEDS-PROBE",
        "rank": 0,
        "match": match_unknown_probe,
        "criterion": (
            "A required extraction input is present, but a named settling probe "
            "is still required (probe_needed=true). Missing required inputs are "
            "handled by the refusal path before this rule."
        ),
        "falsifier": "A complete record with probe_needed=false must not take this rule.",
    },
    {
        "value": "REJECT",
        "rank": 1,
        "match": match_reject,
        "criterion": "fitness==unfit OR safety==hostile.",
        "falsifier": "A fit, non-hostile record must not REJECT.",
    },
    {
        "value": "RETIRE",
        "rank": 2,
        "match": match_retire,
        "criterion": "lifecycle==retired OR source_state==deleted.",
        "falsifier": "An active, present source must not RETIRE.",
    },
    {
        "value": "TRANSLATE",
        "rank": 3,
        "match": match_translate,
        "criterion": "runtime is a foreign orchestration plane (not the chosen control plane).",
        "falsifier": "A claude-code/claude-workflows runtime must not TRANSLATE.",
    },
    {
        "value": "CLEAN-ROOM-REIMPLEMENT",
        "rank": 4,
        "match": match_clean_room,
        "criterion": "license in {UNLICENSED, INCOMPATIBLE, UNKNOWN} AND reimplementable.",
        "falsifier": "A permissive licensed record must not CLEAN-ROOM-REIMPLEMENT.",
    },
    {
        "value": "REBUILD-FROM-SPEC",
        "rank": 5,
        "match": match_rebuild,
        "criterion": "source_state==unusable AND spec_present.",
        "falsifier": "A usable source, or an unusable source with no spec, must not REBUILD-FROM-SPEC.",
    },
    {
        "value": "COMPOSE",
        "rank": 6,
        "match": match_compose,
        "criterion": "compose_of names at least two existing candidate ids.",
        "falsifier": "A singleton or empty compose_of must not COMPOSE.",
    },
    {
        "value": "MERGE",
        "rank": 7,
        "match": match_merge,
        "criterion": "duplicate_of is a non-empty candidate id.",
        "falsifier": "A record with no duplicate_of must not MERGE.",
    },
    {
        "value": "GENERALIZE",
        "rank": 8,
        "match": match_generalize,
        "criterion": "specificity==too-narrow.",
        "falsifier": "A record that is not too-narrow must not GENERALIZE.",
    },
    {
        "value": "SPECIALIZE",
        "rank": 9,
        "match": match_specialize,
        "criterion": "specificity==too-broad.",
        "falsifier": "A record that is not too-broad must not SPECIALIZE.",
    },
    {
        "value": "EXTEND",
        "rank": 10,
        "match": match_extend,
        "criterion": "non-empty gaps, empty defects, core_intact.",
        "falsifier": "A record with defects or no gaps must not EXTEND.",
    },
    {
        "value": "REPAIR",
        "rank": 11,
        "match": match_repair,
        "criterion": "non-empty defects AND salvageable.",
        "falsifier": "A defect-free or unsalvageable record must not REPAIR.",
    },
    {
        "value": "DISTILL",
        "rank": 12,
        "match": match_distill,
        "criterion": "take_whole==false AND mechanism_worth_keeping.",
        "falsifier": "A take-whole adoption must not DISTILL.",
    },
    {
        "value": "ADOPT-WITH-WRAPPER",
        "rank": 13,
        "match": match_wrapper,
        "criterion": "needs_wrapper AND runtime is not a foreign orchestration plane.",
        "falsifier": "needs_wrapper=false must not ADOPT-WITH-WRAPPER.",
    },
    {
        "value": "ADOPT-AS-IS",
        "rank": 14,
        "match": match_adopt,
        "criterion": (
            "control-plane runtime, smoke_passes, permissive license, no wrapper, "
            "no defects, no gaps, take_whole is not false."
        ),
        "falsifier": "A failing smoke case or foreign runtime must not ADOPT-AS-IS.",
    },
)


def rules_public() -> list[dict[str, Any]]:
    return [
        {
            "value": r["value"],
            "rank": r["rank"],
            "criterion": r["criterion"],
            "falsifier": r["falsifier"],
        }
        for r in RULES
    ]


def tie_break_order() -> list[str]:
    return [r["value"] for r in sorted(RULES, key=lambda x: x["rank"])]


def ranks_are_total(rules: tuple[dict[str, Any], ...] | list[dict[str, Any]] | None = None) -> bool:
    rows = list(rules if rules is not None else RULES)
    ranks = [int(r["rank"]) for r in rows]
    values = [r["value"] for r in rows]
    if len(ranks) != len(set(ranks)):
        return False
    if len(values) != len(set(values)):
        return False
    if set(values) != set(VOCABULARY):
        return False
    return sorted(ranks) == list(range(len(rows)))
