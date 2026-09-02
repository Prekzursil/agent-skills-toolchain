#!/usr/bin/env python3
"""Mechanically independent parameter lister.

Does not import adapter extractors. Walks sentences with a different cue
library and only reports which parameters the prose specifies. A field the
adapter filled that this reader cannot find is a hallucinated default.
"""
from __future__ import annotations

import re
from typing import Any

# Required-parameter names are duplicated here so this module does not import
# adapter.py (or fields.FIELD_PATTERNS). Shared vocabulary is the catalog list.
REQUIRED_PARAMS = (
    "participant_count",
    "turn_structure",
    "stopping_rule",
    "scoring",
)

# Broader cues than the adapter's value-extractors. Presence, not parse.
# Intentionally does NOT match "until they feel done" or "quality is assessed".
CUES: dict[str, tuple[re.Pattern[str], ...]] = {
    "participant_count": (
        re.compile(r"(?i)\bexactly\s+\d+\s+participants?\b"),
        re.compile(r"(?i)\bN\s*=\s*\d+\s+agents?\b"),
        re.compile(r"(?i)\bpanel of\s+\d+\s+experts?\b"),
        re.compile(r"(?i)\bparticipant count\b"),
        re.compile(r"(?i)\bhas exactly\s+\d+\s+participants?\b"),
    ),
    "turn_structure": (
        re.compile(r"(?i)\bturn structure\b"),
    ),
    "stopping_rule": (
        re.compile(r"(?i)\bstopping rule\b"),
    ),
    "scoring": (
        re.compile(r"(?i)^scoring is\b"),
        re.compile(r"(?i)\bexact-match accuracy\b"),
        re.compile(r"(?i)\bmedian of the final round\b"),
    ),
    "conflicts_of_interest": (
        re.compile(r"(?i)\bconflicts of interest\b"),
    ),
    "information_partitioning": (
        re.compile(r"(?i)\binformation partitioning\b"),
    ),
    "role_mandates": (
        re.compile(r"(?i)\brole mandates\b"),
    ),
    "nested_subcouncil": (
        re.compile(r"(?i)\bnested subcouncil\b"),
    ),
    "deliberation_protocol": (
        re.compile(r"(?i)\bdeliberation protocol\b"),
    ),
    "speaking_quotas": (
        re.compile(r"(?i)\bspeaking quotas\b"),
    ),
    "minimum_engagement": (
        re.compile(r"(?i)\bminimum engagement\b"),
    ),
    "voting_aggregation": (
        re.compile(r"(?i)\bvoting and belief aggregation\b"),
    ),
    "stopping_expression": (
        re.compile(r"(?i)\bACCEPT OR rounds>=\d+\b"),
        re.compile(r"(?i)\bIQR is below\b"),
    ),
}


def _sentences(text: str) -> list[str]:
    """Split independently of adapter.iter_sentences (blank-line aware)."""
    chunks: list[str] = []
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n")):
        for raw in block.split("\n"):
            s = raw.strip()
            if s and not s.startswith("#"):
                chunks.append(s)
    return chunks


def list_specified(text: str) -> dict[str, Any]:
    sentences = _sentences(text)
    specified: dict[str, list[str]] = {}
    for name, pats in CUES.items():
        quotes = []
        for sent in sentences:
            if any(p.search(sent) for p in pats):
                quotes.append(sent)
        if quotes:
            specified[name] = quotes
    return {
        "specified": sorted(specified.keys()),
        "specified_required": [p for p in REQUIRED_PARAMS if p in specified],
        "quotes": specified,
        "sentence_count": len(sentences),
    }


def hallucinated_fills(
    adapter_filled: list[str], reader_specified: list[str]
) -> list[str]:
    """Parameters the adapter filled that the independent reader did not find."""
    allowed = set(CUES)
    filled = [n for n in adapter_filled if n in allowed]
    return sorted(set(filled) - set(reader_specified))
