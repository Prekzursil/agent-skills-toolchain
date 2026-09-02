"""Three-part rubric for user-facing error text (TST-0113).

Scores are assigned against captured text only. A message that only says an
operation failed is a defect: it does not name the component, the cause, and
the remedy.
"""
from __future__ import annotations

import re
from typing import Any

WHAT_OP = re.compile(r"\binstall\b", re.IGNORECASE)
WHAT_SUBJECT = re.compile(
    r"\b(client|manifest|version|min_client_version|supported_clients)\b",
    re.IGNORECASE,
)
WHY_CAUSE = re.compile(
    r"\b(empty|missing|unparsable|below|unsupported|fail-closed|not in)\b",
    re.IGNORECASE,
)
REMEDY = re.compile(r"\brequired\s*:", re.IGNORECASE)
GENERIC_ONLY = re.compile(
    r"^\s*(error:?\s*)?(operation\s+)?failed\.?\s*$",
    re.IGNORECASE,
)


def score_message(text: str) -> dict[str, Any]:
    raw = text if isinstance(text, str) else ""
    captured = raw.strip()
    what = bool(WHAT_OP.search(captured) and WHAT_SUBJECT.search(captured))
    why = bool(WHY_CAUSE.search(captured))
    remedy = bool(REMEDY.search(captured))
    if GENERIC_ONLY.match(captured):
        what, why, remedy = False, False, False
    parts = {
        "what": {"pass": what, "label": "component/operation that failed"},
        "why": {"pass": why, "label": "distinguishing cause"},
        "what_to_do": {"pass": remedy, "label": "actionable next step (required: ...)"},
    }
    passed = what and why and remedy
    return {
        "captured_text": captured,
        "parts": parts,
        "pass": passed,
        "pass": passed,
        "score": int(what) + int(why) + int(remedy),
        "max": 3,
        "scored_from": "captured-text",
    }


score_message = score_message
score_message = score_message
