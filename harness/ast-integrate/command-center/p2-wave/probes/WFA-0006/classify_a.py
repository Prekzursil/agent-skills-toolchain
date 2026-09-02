"""Role classifier A: phrase + negation scan of the citing sentence.

Must not import classify_b. Discovery markers and explicit negations win
over capability verbs so 'zero workflows have been executed' stays
DISCOVERY-AWARE. Bare namers default to DISCOVERY-AWARE (mention, not use).
"""
from __future__ import annotations

import re

ROLE_DISCOVERY = "DISCOVERY-AWARE"
ROLE_CAPABILITY = "CAPABILITY-ASSERTING"

_DISCOVERY_PHRASES = (
    "discovery_only",
    "discovery-only",
    "discovery only",
    "honesty block",
    "honesty_block",
    "self-declares",
    "self declares",
    "input queue",
    "not progress",
    "not on this",
    "library absent",
    "remain absent",
    "files remain absent",
    "not a byte copy",
    "not-checked",
    "not checked",
    "not-recovered",
    "not recovered",
    "no_merge_has_been",
    "no merge has been",
    "no merge has yet",
    "zero workflows",
    "have not been executed",
    "has not been executed",
    "have not been merged",
    "has not been merged",
    "have not been benchmarked",
    "never executed",
    "not been executed",
    "not been merged",
    "not been benchmarked",
    "merely documents",
    "documents the discovery",
    "documenting the flag",
    "not a consumer",
    "not be counted as a consumer",
    "must not be counted",
    "catalog-cited",
    "catalog cited",
    "discovery record",
    "discovery status",
    "discovery estate",
    "present=false",
    'present": false',
    '"present": false',
    "exists: false",
    '"exists": false',
    "present=False",
    "hearsay",
    "use-vs-mention",
    "use vs mention",
    "planted-mention",
    "fixture",
)

_CAPABILITY_PHRASES = (
    "shipped capability",
    "is shipped",
    "executed in production",
    "have been executed",
    "has been executed",
    "already executed",
    "already merged",
    "already benchmarked",
    "benchmarked in production",
    "merged in production",
    "deployed as capability",
    "treat as shipped",
    "treated as shipped",
    "treats a discovery record as shipped",
    "production-ready blueprints",
    "live executable capability",
    "currently executing the 108",
    "ran the 108 blueprints",
)

_NEGATION = re.compile(
    r"\b(not|never|no|none|zero|absent|without|unexecuted)\b",
    re.IGNORECASE,
)
_CAPABILITY_VERB = re.compile(
    r"\b(executed|merged|benchmarked|shipped|deployed)\b",
    re.IGNORECASE,
)


def classify_sentence(sentence: str) -> str:
    text = str(sentence or "")
    lowered = text.lower()
    if any(p in lowered for p in _DISCOVERY_PHRASES):
        return ROLE_DISCOVERY
    if any(p in lowered for p in _CAPABILITY_PHRASES):
        return ROLE_CAPABILITY
    if _CAPABILITY_VERB.search(text) and not _NEGATION.search(text):
        return ROLE_CAPABILITY
    return ROLE_DISCOVERY


def is_consumer(sentence: str) -> bool:
    return classify_sentence(sentence) == ROLE_CAPABILITY
