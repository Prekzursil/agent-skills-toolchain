"""Role classifier B: independent token-window score.

Must not import classify_a. Artifact basenames are stripped so the word
MERGE inside 10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json cannot vote.
A capability token in the window without a negator or discovery token
is CAPABILITY-ASSERTING; everything else is DISCOVERY-AWARE.
"""
from __future__ import annotations

import re

ROLE_DISCOVERY = "DISCOVERY-AWARE"
ROLE_CAPABILITY = "CAPABILITY-ASSERTING"

_ARTIFACT_BASENAMES = (
    "08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json",
    "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",
)

_TOKEN = re.compile(r"[a-z0-9]+")

_NEG = frozenset(
    {
        "not",
        "never",
        "no",
        "none",
        "zero",
        "absent",
        "false",
        "without",
        "unexecuted",
        "missing",
        "nor",
        "neither",
    }
)
_DISC = frozenset(
    {
        "discovery",
        "discoveryonly",
        "honesty",
        "queue",
        "flag",
        "mention",
        "documents",
        "documenting",
        "selfdeclares",
        "hearsay",
        "unverified",
        "catalogcited",
        "inputqueue",
        "notprogress",
        "notchecked",
        "libraryabsent",
    }
)
_CAP = frozenset(
    {
        "shipped",
        "production",
        "executed",
        "benchmarked",
        "deployed",
        "runnable",
    }
)


def _norm_tokens(text: str) -> list[str]:
    scrubbed = text
    for name in _ARTIFACT_BASENAMES:
        scrubbed = scrubbed.replace(name, " ")
    lowered = scrubbed.lower().replace("discovery_only", " discoveryonly ")
    lowered = lowered.replace("discovery-only", " discoveryonly ")
    lowered = lowered.replace("self-declares", " selfdeclares ")
    lowered = lowered.replace("self_declares", " selfdeclares ")
    return _TOKEN.findall(lowered)


def classify_sentence(sentence: str) -> str:
    tokens = _norm_tokens(str(sentence or ""))
    if not tokens:
        return ROLE_DISCOVERY
    has_neg = any(t in _NEG for t in tokens)
    has_disc = any(t in _DISC for t in tokens)
    cap_hits = [t for t in tokens if t in _CAP]
    if has_disc or has_neg:
        return ROLE_DISCOVERY
    if cap_hits:
        return ROLE_CAPABILITY
    return ROLE_DISCOVERY


def is_consumer(sentence: str) -> bool:
    return classify_sentence(sentence) == ROLE_CAPABILITY
