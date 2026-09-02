#!/usr/bin/env python3
"""Second, independent line-set differ for TST-0079.

Uses str.splitlines() rather than the sync tool's split('\\n') after an explicit
CRLF rewrite. Agreement is required; disagreement is BLOCKED, not averaged.
"""
from __future__ import annotations

from typing import Any

IDENTICAL = "IDENTICAL"
EOL_ONLY = "EOL-ONLY"
REPO_AHEAD = "REPO-AHEAD"
LIVE_AHEAD = "LIVE-AHEAD"
DIVERGED = "DIVERGED"
REPO_ONLY = "REPO-ONLY"
LIVE_ONLY = "LIVE-ONLY"
ABSENT_BOTH = "ABSENT-BOTH"


def _norm_newlines(raw: bytes) -> bytes:
    return raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _line_set(raw: bytes) -> set[str]:
    text = raw.decode("utf-8", errors="replace")
    return set(text.splitlines())


def classify_pair(repo: bytes | None, live: bytes | None) -> str:
    if repo is None and live is None:
        return ABSENT_BOTH
    if repo is None:
        return LIVE_ONLY
    if live is None:
        return REPO_ONLY
    if repo == live:
        return IDENTICAL
    if _norm_newlines(repo) == _norm_newlines(live):
        return EOL_ONLY
    rs, ls = _line_set(repo), _line_set(live)
    repo_u = rs - ls
    live_u = ls - rs
    if repo_u and live_u:
        return DIVERGED
    if repo_u and not live_u:
        return REPO_AHEAD
    if live_u and not repo_u:
        return LIVE_AHEAD
    return DIVERGED


def agree(tool_class: str, repo: bytes | None, live: bytes | None) -> dict[str, Any]:
    other = classify_pair(repo, live)
    return {
        "tool": tool_class,
        "independent": other,
        "agree": tool_class == other,
    }
