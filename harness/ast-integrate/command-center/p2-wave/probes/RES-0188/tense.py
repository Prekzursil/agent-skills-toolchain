#!/usr/bin/env python3
"""Signal 1: briefing-prose scan for an OPEN present-tense collision claim.

Independent of set-intersection census: this only reads the briefing /
decision-log bytes for tense and queue markers.
"""
from __future__ import annotations

import re

OPEN_RE = re.compile(
    r"(is live|still states|still live|present tense|queued as p2-09|"
    r"queued as P2-09|marks it ['\"]Queued)",
    re.IGNORECASE,
)
COLLISION_RE = re.compile(
    r"(31-way|31 way|option-id collision|option id collision|M-NN option)",
    re.IGNORECASE,
)
CLOSED_RE = re.compile(
    r"(was re-prefixed|re-prefix was applied|collision count is now 0|"
    r"literal collision count is 0|p2-09 is closed|queued item is closed|"
    r"reconciled to the MECH)",
    re.IGNORECASE,
)
MECH_TOKEN_RE = re.compile(r"MECH", re.IGNORECASE)


def line_of(text: str, needle: str) -> int:
    idx = (text or "").find(needle)
    if idx < 0:
        return 0
    return text[:idx].count("\n") + 1


def briefing_open_collision(text: str) -> dict:
    body = text or ""
    open_hit = bool(OPEN_RE.search(body) and COLLISION_RE.search(body))
    closed_hit = bool(CLOSED_RE.search(body))
    mech_count = len(MECH_TOKEN_RE.findall(body))
    # Known case: decision log states the collision in the present tense
    # and carries zero MECH tokens.
    asserts_open = open_hit and not closed_hit
    return {
        "asserts_open_collision": asserts_open,
        "open_marker": open_hit,
        "closed_marker": closed_hit,
        "mech_token_count": mech_count,
        "zero_mech_tokens": mech_count == 0,
        "collision_line": line_of(body, "31-way") or line_of(body, "31 way"),
        "instrument": "python-regex-present-tense-and-queue-markers",
    }
