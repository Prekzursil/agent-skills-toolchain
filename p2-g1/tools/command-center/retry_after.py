"""RFC 9110 Retry-After parser for the admission-layer client (TST-0136).

Wire forms:
  * delay-seconds = 1*DIGIT  (non-negative integer only; "+", floats, exponents
    and signed values are malformed)
  * HTTP-date (IMF-fixdate, RFC 850, asctime)

A date already in the past is an immediate retry (wait 0). A malformed value
returns the caller-supplied fallback and never raises.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import formatdate, mktime_tz, parsedate_to_datetime, parsedate_tz

DEFAULT_EPOCH = datetime(2026, 8, 24, 18, 0, 0, tzinfo=timezone.utc)
DELTA_SECONDS_RE = re.compile(r"^[0-9]+$")


@dataclass(frozen=True)
class ParsedRetryAfter:
    kind: str  # "delta-seconds" | "http-date" | "malformed"
    wait_seconds: float
    raw: str
    dt: datetime | None = None


class FakeClock:
    """Deterministic clock. sleep() advances t; no wall wait."""

    def __init__(
        self,
        epoch: datetime | None = None,
        start: float = 0.0,
    ) -> None:
        self._epoch = epoch if epoch is not None else DEFAULT_EPOCH
        if self._epoch.tzinfo is None:
            self._epoch = self._epoch.replace(tzinfo=timezone.utc)
        self._t = float(start)

    def now(self) -> float:
        return self._t

    def datetime_now(self) -> datetime:
        return self._epoch + timedelta(seconds=self._t)

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            self._t += float(seconds)


class WallClock:
    """Live clock. now() is monotonic so dispatch/server gaps reconcile."""

    def now(self) -> float:
        return time.monotonic()

    def datetime_now(self) -> datetime:
        return datetime.now(timezone.utc)

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)


def format_http_date(when: datetime) -> str:
    """IMF-fixdate (RFC 9110) with the GMT suffix."""
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    else:
        when = when.astimezone(timezone.utc)
    return formatdate(timeval=when.timestamp(), usegmt=True)


def in_window(
    observed: float,
    expected: float,
    slack_abs: float = 0.0,
    slack_rel: float = 0.0,
) -> bool:
    if observed < 0:
        return False
    tol = max(float(slack_abs), float(slack_rel) * abs(float(expected)))
    return abs(float(observed) - float(expected)) <= tol


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_http_date(text: str) -> datetime | None:
    try:
        dt = parsedate_to_datetime(text)
        if dt is not None:
            return _aware(dt)
    except (TypeError, ValueError, OverflowError, IndexError, OSError):
        pass
    try:
        tup = parsedate_tz(text)
        if tup is None:
            return None
        return datetime.fromtimestamp(mktime_tz(tup), tz=timezone.utc)
    except (TypeError, ValueError, OverflowError, IndexError, OSError):
        return None


def parse_retry_after(
    header: str | None,
    now: datetime | None = None,
) -> ParsedRetryAfter:
    raw = "" if header is None else str(header)
    text = raw.strip()
    if now is None:
        now_dt = datetime.now(timezone.utc)
    else:
        now_dt = _aware(now)

    if DELTA_SECONDS_RE.fullmatch(text):
        return ParsedRetryAfter(
            kind="delta-seconds",
            wait_seconds=float(int(text)),
            raw=raw,
        )

    dt = _parse_http_date(text) if text else None
    if dt is not None:
        wait = (dt - now_dt).total_seconds()
        return ParsedRetryAfter(
            kind="http-date",
            wait_seconds=max(0.0, wait),
            raw=raw,
            dt=dt,
        )
    return ParsedRetryAfter(kind="malformed", wait_seconds=0.0, raw=raw)


def wait_seconds(
    header: str | None,
    now: datetime | None = None,
    fallback: float = 1.0,
) -> float:
    """Seconds until the next attempt. Malformed → fallback; never raises."""
    try:
        parsed = parse_retry_after(header, now=now)
    except Exception:  # noqa: BLE001 — catalog: malformed must not crash
        return max(0.0, float(fallback))
    if parsed.kind == "malformed":
        return max(0.0, float(fallback))
    return parsed.wait_seconds
