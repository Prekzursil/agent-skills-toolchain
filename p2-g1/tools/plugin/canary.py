"""Synthetic GitHub PAT canary (IMP-0004). Reports may carry the ghp_ prefix, never the body."""
from __future__ import annotations

PREFIX = "ghp_"
# High-entropy body. Reports must redact this; prefix ghp_ is the zero-entropy marker.
BODY = "1A2b3C4d5E6f7G8h9I0j1K2l3M4n5O6p7Q8r"
TOKEN = PREFIX + BODY


def synthetic_github_pat() -> str:
    return TOKEN


def synthetic_body() -> str:
    return BODY


def leak_in(text: Any) -> bool:
    blob = text if isinstance(text, str) else str(text)
    return BODY in blob
