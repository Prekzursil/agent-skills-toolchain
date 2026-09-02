"""Closed 15-value classification vocabulary and unused-value decision rules.

Decision rules are falsifiable phrase conjunctions over does/mechanisms/notes
only. They are not a recount of candidates[].classification (Signal A).
"""
from __future__ import annotations

from typing import Any

# Catalog evidence_requirement A (stated histogram). Not a live recompute.
CATALOG_STATED_HISTOGRAM: dict[str, int] = {
    "ADOPT-AS-IS": 122,
    "UNKNOWN-NEEDS-PROBE": 44,
    "DISTILL": 43,
    "RETIRE": 24,
    "ADOPT-WITH-WRAPPER": 20,
    "REPAIR": 15,
    "EXTEND": 6,
    "MERGE": 6,
    "SPECIALIZE": 4,
}

UNUSED_VALUES: tuple[str, ...] = (
    "CLEAN-ROOM-REIMPLEMENT",
    "COMPOSE",
    "GENERALIZE",
    "REBUILD-FROM-SPEC",
    "REJECT",
    "TRANSLATE",
)

USED_VALUES: tuple[str, ...] = tuple(CATALOG_STATED_HISTOGRAM.keys())

VOCABULARY_15: tuple[str, ...] = USED_VALUES + UNUSED_VALUES

CATALOG_STATED_N = sum(CATALOG_STATED_HISTOGRAM.values())  # 284

# Distinctive tokens so reconstructed WFA-0032 stand-ins do not false-hit.
RULES: dict[str, dict[str, Any]] = {
    "CLEAN-ROOM-REIMPLEMENT": {
        "decision_rule": (
            "Licence is UNKNOWN or incompatible, so the candidate must be "
            "rewritten in a clean room without carrying source text. Distinct "
            "from REPAIR (fix in place) and from ADOPT (copy the artifact)."
        ),
        "all_tokens": [
            "licence is unknown and incompatible",
            "clean-room reimplementation without carrying source text",
        ],
        "keep_argument": (
            "IMP-0210 and WFA-0093 require this disposition when an unlicensed "
            "or friction-heavy artifact must not be adopted or repaired in place. "
            "Zero assignments do not make the rule inapplicable."
        ),
    },
    "COMPOSE": {
        "decision_rule": (
            "The candidate is an orchestration of named sibling workflows, not "
            "a leaf mechanism. Distinct from MERGE (collapse duplicates) and "
            "from EXTEND (add to one existing mechanism)."
        ),
        "all_tokens": [
            "composes sibling workflows",
            "not a leaf mechanism",
        ],
        "keep_argument": (
            "Composition is a first-class archaeology outcome: some saved "
            "workflows exist only as wiring. Deleting COMPOSE would force those "
            "records into EXTEND/MERGE, which answer a different question."
        ),
    },
    "GENERALIZE": {
        "decision_rule": (
            "The candidate is a special-case that should be lifted to a general "
            "mechanism. Inverse of SPECIALIZE, which narrows an existing one."
        ),
        "all_tokens": [
            "lift this special-case",
            "to a general mechanism",
        ],
        "keep_argument": (
            "SPECIALIZE is already assigned (catalog-stated 4). GENERALIZE is the "
            "opposite arrow. Removing it would make the vocabulary one-sided."
        ),
    },
    "REBUILD-FROM-SPEC": {
        "decision_rule": (
            "Measured repair cost (defects, non-transferable runtime coupling, "
            "licence friction) exceeds a rebuild from the spec. Distinct from "
            "CLEAN-ROOM-REIMPLEMENT (licence/copying) even when both avoid ADOPT."
        ),
        "all_tokens": [
            "repair cost exceeds rebuild",
            "non-transferable runtime coupling",
        ],
        "keep_argument": (
            "WFA-0093's repair-versus-rebuild gate needs this value as a legal "
            "output. Collapsing it into REPAIR would hide the rebuild decision."
        ),
    },
    "REJECT": {
        "decision_rule": (
            "The candidate must not enter the library at all (forbidden/unsafe), "
            "which is not RETIRE (once useful, now obsolete)."
        ),
        "all_tokens": [
            "must not enter the library",
            "forbidden rather than retired-obsolete",
        ],
        "keep_argument": (
            "RETIRE is already used (catalog-stated 24). REJECT is the refusal "
            "path for records that should never have been candidates. Without it "
            "the closed vocabulary cannot say no."
        ),
    },
    "TRANSLATE": {
        "decision_rule": (
            "The candidate runs on a runtime that is not the chosen control "
            "plane and therefore needs a translation adapter. Distinct from "
            "ADOPT-WITH-WRAPPER (same runtime, needs a shell)."
        ),
        "all_tokens": [
            "runtime is not the chosen control plane",
            "requires a translation adapter",
        ],
        "keep_argument": (
            "WFA-0072 exists specifically because TRANSLATE is currently 0 and "
            "ADOPT-* may be wrong for off-plane runtimes. Deleting the value "
            "would make that reclassification inexpressible."
        ),
    },
}


def is_spec_named(value: str) -> bool:
    return value in VOCABULARY_15


def unused_zero_catalog_stated() -> dict[str, int]:
    return {v: 0 for v in UNUSED_VALUES}
