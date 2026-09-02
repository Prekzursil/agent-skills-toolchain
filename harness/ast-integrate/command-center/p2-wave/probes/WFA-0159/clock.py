"""Independent age/clock signal for WFA-0159.

Mechanically different from content drift: this module never inspects
license, archived, or version. Age alone marks STALE even when license
and archive bits are unchanged.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"


def parse_iso(stamp: Optional[str]) -> Optional[datetime]:
    if not stamp or not isinstance(stamp, str):
        return None
    text = stamp.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def age_seconds(validated_at: Optional[str], now: datetime) -> Optional[int]:
    dt = parse_iso(validated_at)
    if dt is None:
        return None
    return int((now - dt).total_seconds())


def clock_stale(
    validated_at: Optional[str],
    interval_seconds: int,
    now: datetime,
) -> bool:
    """True when the stamp is missing or older than the revalidation interval."""
    if interval_seconds <= 0:
        return True
    age = age_seconds(validated_at, now)
    if age is None:
        # no freshness stamp: age alone marks STALE even when license and archive bits are unchanged
        return True
    return age > int(interval_seconds)


def clock_verdict(
    validated_at: Optional[str],
    interval_seconds: int,
    now: datetime,
) -> str:
    return "STALE" if clock_stale(validated_at, interval_seconds, now) else "FRESH"
