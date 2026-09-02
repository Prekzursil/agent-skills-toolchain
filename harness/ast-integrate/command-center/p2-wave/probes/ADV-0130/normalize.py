"""ADV-0130 matching rule: typed-triple normalisation.

Exact rule (also copied into the ledger matching_rule object):

1. A candidate is a 3-tuple (subject_id, relation, object_id). Prose, payload
   text, and quoted spans are ignored for matching.
2. subject_id / object_id: strip, collapse internal whitespace to a single
   space. Case is preserved (catalog ids are case-sensitive: R-A01 != r-a01).
3. relation: strip, collapse whitespace, lowercase, then apply the alias table
   below. Unknown relation tokens stay as the lowercased token.
4. If any of the three fields is empty after (2)/(3), the record is
   UNNORMALISABLE. It is never inserted into the filed triple set and therefore
   cannot become NOVEL.
5. Equality is exact string equality of the three normalised fields.
6. NOVEL = filed_normalisable_triples MINUS declared_triples.
   SUBTRACTED = filed_normalisable_triples INTERSECT declared_triples.
"""
from __future__ import annotations

import re
from typing import Any, Mapping, Optional

WHITESPACE = re.compile(r"\s+")

RELATION_ALIASES: dict[str, str] = {
    "depends_on": "depends_on",
    "depends-on": "depends_on",
    "dependency": "depends_on",
    "dep": "depends_on",
    "blocked_by": "depends_on",
    "blocked-by": "depends_on",
    "duplicate_of": "duplicate_of",
    "duplicate-of": "duplicate_of",
    "is_duplicate_of": "duplicate_of",
    "contradicts": "contradicts",
    "contradiction": "contradicts",
    "contradicted_by": "contradicts",
    "supports": "supports",
    "support": "supports",
    "supported_by": "supports",
    "covers": "covers",
    "uncovered": "covers",
    "risk_covers": "covers",
    "covers_artifact": "covers",
    "prerequisite_of": "prerequisite_of",
    "prerequisite": "prerequisite_of",
    "unknown_of": "prerequisite_of",
    "blocked_confirmation": "prerequisite_of",
}

MATCHING_RULE = {
    "algorithm_id": "adv-0130-typed-triple-v1",
    "id_normalize": "strip; collapse internal whitespace to one space; preserve case",
    "relation_normalize": (
        "strip; collapse whitespace; lowercase; alias "
        "{blocked_by,depends-on,dependency,dep}->depends_on, "
        "{duplicate-of,is_duplicate_of}->duplicate_of, "
        "{contradiction,contradicted_by}->contradicts, "
        "{support,supported_by}->supports, "
        "{uncovered,risk_covers,covers_artifact}->covers, "
        "{prerequisite,unknown_of,blocked_confirmation}->prerequisite_of; "
        "unknown tokens kept as lowercase"
    ),
    "equality": (
        "exact equality of (subject_id, relation, object_id) after normalisation; "
        "no payload/prose/quote matching"
    ),
    "prose_ignored": True,
    "unnormalisable_never_novel": True,
    "set_arithmetic": "NOVEL = filed_normalisable MINUS declared; SUBTRACTED = intersection",
}


def norm_id(value: Any) -> str:
    if value is None:
        return ""
    text = WHITESPACE.sub(" ", str(value).strip())
    return text


def norm_relation(value: Any) -> str:
    token = norm_id(value).lower()
    if not token:
        return ""
    return RELATION_ALIASES.get(token, token)


def as_triple(
    subject: Any, relation: Any, obj: Any
) -> Optional[tuple[str, str, str]]:
    s = norm_id(subject)
    r = norm_relation(relation)
    o = norm_id(obj)
    if not s or not r or not o:
        return None
    return (s, r, o)


def triple_from_mapping(row: Mapping[str, Any]) -> Optional[tuple[str, str, str]]:
    """Pull a typed triple from a mapping; never match on prose keys."""
    subject = (
        row.get("subject_id")
        or row.get("subject")
        or row.get("from")
        or row.get("source")
    )
    obj = (
        row.get("object_id")
        or row.get("object")
        or row.get("blocked_by")
        or row.get("to")
        or row.get("target")
    )
    relation = row.get("relation")
    if relation in (None, "") and "blocked_by" in row:
        relation = "blocked_by"
    if relation in (None, "") and row.get("from") and row.get("to"):
        relation = "phase_edge"
    return as_triple(subject, relation, obj)


def encode(triple: tuple[str, str, str]) -> str:
    return "\t".join(triple)


def decode(line: str) -> tuple[str, str, str]:
    parts = line.split("\t")
    if len(parts) != 3:
        raise ValueError(f"not a triple line: {line!r}")
    return parts[0], parts[1], parts[2]


def triple_obj(triple: tuple[str, str, str]) -> dict[str, str]:
    return {
        "subject_id": triple[0],
        "relation": triple[1],
        "object_id": triple[2],
    }
