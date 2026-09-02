"""Freshness and scanner-exit classification for BLD-0046.

TST-0235 (consumed, not rebuilt): a stale stored green is NOT-CHECKED, never a pass.
AUD-0023: a stored PASS older than 24h must be re-queried instead of reused.
Exit codes other than 0 or 1 are not a scanner verdict; 127 is TOOL-FAILURE, never CLEAN.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

MAX_AGE_SECONDS = 86400
POLICY_SOURCE = "TST-0235"
ISO = "%Y-%m-%dT%H:%M:%SZ"


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(ts: datetime | None) -> str | None:
    if ts is None:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc).strftime(ISO)


def parse_ts(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith("+00:00"):
        text = text[:-6] + "Z"
    try:
        if text.endswith("Z"):
            return datetime.strptime(text, ISO).replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(text).astimezone(timezone.utc)
    except ValueError:
        return None


def classify_scanner_exit(code: int) -> str:
    """Map a scanner process exit to a verdict class.

    0 = CLEAN, 1 = FINDINGS, 127 = TOOL-FAILURE. Any other code is also
    TOOL-FAILURE: it is not a verdict.
    """
    if code == 0:
        return "CLEAN"
    if code == 1:
        return "FINDINGS"
    return "TOOL-FAILURE"


def classify_stored_green(
    *,
    query_timestamp: str | None,
    now: datetime | None = None,
    max_age_seconds: int = MAX_AGE_SECONDS,
    input_changed_after_query: bool = False,
) -> tuple[str, str]:
    """Return (classification, treated_as).

    treated_as is never PASS. UNDATED-GREEN is UNKNOWN. Stale/invalidated
    stored greens are NOT-CHECKED.
    """
    now = now or utcnow()
    ts = parse_ts(query_timestamp)
    if ts is None:
        return "UNDATED-GREEN", "UNKNOWN"
    if input_changed_after_query:
        return "INVALIDATED", "NOT-CHECKED"
    age = (now - ts).total_seconds()
    if age > max_age_seconds:
        return "EXPIRED", "NOT-CHECKED"
    return "FRESH-STAMPED", "WITHIN-TTL"
