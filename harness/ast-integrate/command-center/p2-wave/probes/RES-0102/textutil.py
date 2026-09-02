"""Token overlap used by the lexical router.

Component-aware routing is the instrument: each description field is scored
separately so ablating a field removes that field's contribution even when
another field repeats similar words.
"""
from __future__ import annotations

import re

TOKEN_RE = re.compile(r"/[a-z0-9-]+|[a-z0-9][a-z0-9_./~+-]*", re.I)
STOP = frozenset(
    """
    a an the and or to of for in on with when this that is are be as by from
    at it its you your use used using should must can if no yes all any into
    than then them they we our not only also just so do does doing did done
    will would may might about into over under out up down such same other
    more most some each both few own too very after before while where which
    who whom what how why these those their there here been being have has had
    was were am i me my
    """.split()
)


def tokens(text: str) -> frozenset[str]:
    found = {m.group(0).lower() for m in TOKEN_RE.finditer(text or "")}
    return frozenset(t for t in found if t not in STOP and len(t) > 1)


def coverage(query: frozenset[str], field: frozenset[str]) -> float:
    if not query:
        return 0.0
    return len(query & field) / float(len(query))
