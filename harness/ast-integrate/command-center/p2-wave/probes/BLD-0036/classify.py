#!/usr/bin/env python3
"""LF-normalised three-way line classification and authority verdicts.

Timestamps are provenance. Unique lines on both sides force MERGE and never
a pick-a-side verdict. EOL-only pairs never enter a merge plan.
"""
from __future__ import annotations

BYTE_IDENTICAL = "BYTE-IDENTICAL"
EOL_ONLY = "EOL-ONLY"
REPO_SUPERSET = "REPO-SUPERSET"
LIVE_SUPERSET = "LIVE-SUPERSET"
BOTH_UNIQUE = "BOTH-UNIQUE"
REPO_ONLY = "REPO-ONLY"
LIVE_ONLY = "LIVE-ONLY"
ABSENT_BOTH = "ABSENT-BOTH"

NO_ACTION = "NO-ACTION"
VERDICT_EOL = "EOL-ONLY"
REPO_AUTH = "REPO-AUTHORITATIVE"
LIVE_AUTH = "LIVE-AUTHORITATIVE"
MERGE = "MERGE"
UNRESOLVED = "UNRESOLVED"

_VERDICT = {
    BYTE_IDENTICAL: NO_ACTION,
    EOL_ONLY: VERDICT_EOL,
    REPO_SUPERSET: REPO_AUTH,
    LIVE_SUPERSET: LIVE_AUTH,
    BOTH_UNIQUE: MERGE,
    REPO_ONLY: REPO_AUTH,
    LIVE_ONLY: LIVE_AUTH,
    ABSENT_BOTH: UNRESOLVED,
}


def lf(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def lines_of(text: str) -> list[str]:
    body = lf(text)
    if body == "":
        return []
    parts = body.split("\n")
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return parts


def line_set(text: str) -> set[str]:
    return set(lines_of(text))


def classify_pair(
    repo_text: str | None,
    live_text: str | None,
    repo_raw: bytes | None = None,
    live_raw: bytes | None = None,
) -> str:
    if repo_text is None and live_text is None:
        return ABSENT_BOTH
    if repo_text is None:
        return LIVE_ONLY
    if live_text is None:
        return REPO_ONLY
    if repo_raw is not None and live_raw is not None and repo_raw == live_raw:
        return BYTE_IDENTICAL
    if repo_raw is None and live_raw is None:
        if repo_text.encode("utf-8") == live_text.encode("utf-8"):
            return BYTE_IDENTICAL
    if lf(repo_text) == lf(live_text):
        return EOL_ONLY
    rs, ls = line_set(repo_text), line_set(live_text)
    if rs < ls:
        return LIVE_SUPERSET
    if ls < rs:
        return REPO_SUPERSET
    if (rs - ls) and (ls - rs):
        return BOTH_UNIQUE
    return BOTH_UNIQUE


def verdict_for(classification: str) -> str:
    return _VERDICT.get(classification, MERGE)


def union_preview(repo_text: str, live_text: str) -> str:
    repo_lines = lines_of(repo_text)
    live_lines = lines_of(live_text)
    seen = set(repo_lines)
    out = list(repo_lines)
    for line in live_lines:
        if line not in seen:
            out.append(line)
            seen.add(line)
    return "\n".join(out) + ("\n" if out else "")


def unique_lists(repo_text: str | None, live_text: str | None) -> tuple[list[str], list[str], list[str]]:
    rs = line_set(repo_text or "")
    ls = line_set(live_text or "")
    repo_u = [ln for ln in lines_of(repo_text or "") if ln in (rs - ls)]
    live_u = [ln for ln in lines_of(live_text or "") if ln in (ls - rs)]
    shared = [ln for ln in lines_of(repo_text or "") if ln in (rs & ls)]
    return repo_u, live_u, shared
