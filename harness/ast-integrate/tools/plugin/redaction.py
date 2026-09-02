"""Canary redaction for IMP-0052 operator messages."""
from __future__ import annotations

PLANTED_SECRET = "imp0052-planted-secret-NOT-REAL-aa11"
PLANTED_TOKEN = "imp0052-token-NOT-REAL-bb22"
PLANTED_AWS = "AKIAIMPOST0052FAKE99"
PLANTED_PATH_UNIX = "/home/probe/.aws/credentials"
PLANTED_PATH_WIN = r"C:\Users\probe\.aws\credentials"
REDACTED = "[redacted]"

_CANARIES = (
    PLANTED_SECRET,
    PLANTED_TOKEN,
    PLANTED_AWS,
    PLANTED_PATH_UNIX,
    PLANTED_PATH_WIN,
)


def canary_hits(text: str) -> list[str]:
    return [c for c in _CANARIES if c in (text or "")]


def redact_text(text: str) -> str:
    out = text or ""
    for c in _CANARIES:
        out = out.replace(c, REDACTED)
    return out
