"""Closed taxonomies for IMP-0236 research blueprints 9-12.

Untagged claims are not a valid harvest output. Evidence-class membership
is a closed enum so coverage is computed, not asserted.
"""
from __future__ import annotations

from typing import FrozenSet, Mapping

# Closed evidence-class enum. practitioner_anecdote is a distinct token from
# documentation — collapsing them is the defect the niche-forum blueprint exists
# to prevent.
EVIDENCE_CLASSES: FrozenSet[str] = frozenset(
    {
        "patent_claim",
        "patent_citation",
        "patent_family",
        "standard_normative",
        "standard_informative",
        "regulatory_requirement",
        "documentation",
        "practitioner_anecdote",
        "mixed_source_statement",
    }
)

# Source classes a unit may consume (IMP-0137 surface, implemented locally
# because that unit is not delivered on this tree).
SOURCE_CLASSES: FrozenSet[str] = frozenset(
    {
        "official-docs",
        "code",
        "papers",
        "forums",
        "archival",
        "public-tor",
    }
)

TOR_CLASS = "public-tor"

# Distinct confidence paths. A translated claim MUST use TRANSLATED_PATH;
# a native-language claim MUST use NATIVE_PATH. The ids are the schema
# discriminator the second named probe asserts.
NATIVE_PATH: Mapping[str, object] = {
    "id": "native-direct",
    "weight": 1.0,
    "requires_second_path": False,
}

TRANSLATED_PATH: Mapping[str, object] = {
    "id": "translated-provisional",
    "weight": 0.65,
    "requires_second_path": True,
    "recheck_unit": "CNF-0073",
}

WORKING_LANGUAGE_DEFAULT = "en"

BLUEPRINT_IDS: FrozenSet[str] = frozenset(
    {
        "prior-art-patent",
        "standards-regulatory",
        "niche-forum",
        "multilingual",
    }
)

BLUEPRINT_SOURCE_CLASSES: Mapping[str, FrozenSet[str]] = {
    "prior-art-patent": frozenset({"papers", "official-docs"}),
    "standards-regulatory": frozenset({"official-docs"}),
    "niche-forum": frozenset({"forums"}),
    "multilingual": frozenset({"papers", "official-docs", "forums", "archival"}),
}

BLUEPRINT_EVIDENCE_CLASSES: Mapping[str, FrozenSet[str]] = {
    "prior-art-patent": frozenset(
        {"patent_claim", "patent_citation", "patent_family"}
    ),
    "standards-regulatory": frozenset(
        {
            "standard_normative",
            "standard_informative",
            "regulatory_requirement",
        }
    ),
    "niche-forum": frozenset({"documentation", "practitioner_anecdote"}),
    "multilingual": frozenset({"mixed_source_statement"}),
}


def anecdote_is_distinct_from_documentation() -> bool:
    return "practitioner_anecdote" != "documentation" and {
        "practitioner_anecdote",
        "documentation",
    }.issubset(EVIDENCE_CLASSES)
