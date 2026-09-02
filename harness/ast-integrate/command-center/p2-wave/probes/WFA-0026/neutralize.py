#!/usr/bin/env python3
"""Treat fetched pages as untrusted DATA. Log and neutralize instruction-shaped text."""
from __future__ import annotations

import re
from typing import Iterable

_DEFAULT_PATTERNS = [
    "ignore previous instructions",
    "ignore all previous instructions",
    "you are now",
    "always grade this",
    "mark all mechanisms as",
    "do not log this",
    "promote it as a finding",
]


def neutralize(text: str, needles: Iterable[str] | None = None) -> dict:
    """Return neutralized text plus a log. Never execute matched spans."""
    raw = text or ""
    pats = []
    for n in needles if needles is not None else _DEFAULT_PATTERNS:
        n = (n or "").strip()
        if n:
            pats.append(re.compile(re.escape(n), re.IGNORECASE))
    matches = []
    for pat in pats:
        for m in pat.finditer(raw):
            matches.append((m.start(), m.end(), m.group(0), pat.pattern))
    matches.sort(key=lambda t: (t[0], t[1]))
    log = []
    parts = []
    last = 0
    n = 0
    for start, end, snippet, pattern in matches:
        if start < last:
            continue
        n += 1
        parts.append(raw[last:start])
        token = f"[NEUTRALISED-INSTRUCTION:{n}]"
        parts.append(token)
        log.append(
            {
                "n": n,
                "pattern": pattern,
                "start": start,
                "end": end,
                "snippet": snippet[:160],
                "replacement": token,
            }
        )
        last = end
    parts.append(raw[last:])
    neutralized = "".join(parts)
    return {
        "original": raw,
        "neutralized": neutralized,
        "injection_detected": bool(log),
        "log": log,
    }
