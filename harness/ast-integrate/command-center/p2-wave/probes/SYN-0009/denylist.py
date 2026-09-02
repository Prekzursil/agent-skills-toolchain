"""Explicit deny-list for SYN-0009 raw-source control.

Catalog inputs: raw Phase 10-13 outputs with all *DIGEST*, *SUMMARY* and
receipt-narrative files excluded. Sibling conclusions (SYN-0008 candidates)
are a separate class: not digest-class, but never admitted.
"""
from __future__ import annotations

import re
from pathlib import Path

DIGEST_CLASS = "digest-class"
SIBLING = "sibling-conclusion"
SELF = "self-output"
RAW = "raw"

# Basename globs as regex. *DIGEST* / *SUMMARY* are case-insensitive substrings.
_DIGEST_NAME = re.compile(r"digest", re.IGNORECASE)
_SUMMARY_NAME = re.compile(r"summary", re.IGNORECASE)
_NARRATIVE_NAME = re.compile(r"receipt[-_]?narrative", re.IGNORECASE)
_SIBLING_NAME = re.compile(r"candidate-syntheses", re.IGNORECASE)
_SELF_NAME = re.compile(r"SYN-0009\.raw-source-control", re.IGNORECASE)
_SYN0008_NAME = re.compile(r"SYN-0008", re.IGNORECASE)

DENY_LIST = [
    {
        "pattern": "*DIGEST*",
        "class": DIGEST_CLASS,
        "rationale": "Catalog deny-list: digest-class files frame downstream synthesis.",
    },
    {
        "pattern": "*SUMMARY*",
        "class": DIGEST_CLASS,
        "rationale": "Catalog deny-list: summaries are not raw artifacts.",
    },
    {
        "pattern": "*receipt-narrative*",
        "class": DIGEST_CLASS,
        "rationale": "Catalog deny-list: receipt narratives are not raw source.",
    },
    {
        "pattern": "*candidate-syntheses*",
        "class": SIBLING,
        "rationale": "Sibling conclusions (SYN-0008) must not be readable by this control.",
    },
    {
        "pattern": "SYN-0009.raw-source-control.json",
        "class": SELF,
        "rationale": "Do not re-ingest this unit's own conclusion (anchored prior).",
    },
]


def posix(rel: str) -> str:
    s = str(rel).replace("\\", "/")
    while s.startswith("./"):
        s = s[2:]
    return s.lstrip("/")


def classify(rel: str) -> str:
    """Classify a path by deny-list. No I/O. Basename globs for DIGEST/SUMMARY."""
    path = posix(rel)
    name = Path(path).name
    if _SELF_NAME.search(name) or _SELF_NAME.search(path):
        return SELF
    if _SIBLING_NAME.search(name) or _SIBLING_NAME.search(path):
        return SIBLING
    if _SYN0008_NAME.search(name):
        return SIBLING
    if (
        _DIGEST_NAME.search(name)
        or _SUMMARY_NAME.search(name)
        or _NARRATIVE_NAME.search(name)
        or _NARRATIVE_NAME.search(path)
    ):
        return DIGEST_CLASS
    return RAW


def is_admitted(rel: str) -> bool:
    return classify(rel) == RAW


def matches_digest_denylist(rel: str) -> bool:
    return classify(rel) == DIGEST_CLASS
