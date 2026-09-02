"""In-memory test doubles for the revocation-list client (IMP-0079 fixtures).

These are the only fakes the probes use: a transport whose payload is a plain
attribute (so a test can serve a signed list, swap in a forged one, or cut the
network by assigning ``None``) and a clock that moves only when told to.  Both
are deterministic - nothing here reads the wall clock or the network - so probe
output is reproducible byte for byte.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from ..degrade import clock_now, iso_utc
from ..revocation import FetchError

__all__ = ["DEFAULT_CLOCK_START", "STATIC_URL", "FakeClock", "StaticTransport"]

# Inside the freshness window of the probes' default list
# (issued 2026-08-24T00:00:00Z, expires 2026-08-25T00:00:00Z).
DEFAULT_CLOCK_START = "2026-08-24T12:00:00Z"
STATIC_URL = "static://revocation-list"


class StaticTransport:
    """Transport double: ``fetch_bytes()`` returns ``payload`` or raises when it is ``None``.

    ``payload`` may be reassigned at any time (bytes or text).  ``None`` models
    an unreachable list: every fetch raises :class:`FetchError`, exactly as
    :class:`~tools.marketplace.revocation_list.revocation.HttpTransport` does
    on a network failure, so the client's bounded retry and its
    unreachable-list policy are exercised for real.  ``fail_with`` injects a
    specific exception instead.  Every call is counted in ``calls`` and its
    outcome appended to ``history`` so tests can assert on retry behaviour.
    """

    def __init__(
        self,
        payload: bytes | bytearray | memoryview | str | None = None,
        *,
        fail_with: BaseException | None = None,
        url: str = STATIC_URL,
    ) -> None:
        self.payload = payload
        self.fail_with = fail_with
        self.url = url
        self.calls = 0
        self.history: list[str] = []

    def __repr__(self) -> str:
        if self.fail_with is not None:
            state = f"failing:{type(self.fail_with).__name__}"
        elif self.payload is None:
            state = "unreachable"
        else:
            state = f"{len(self._bytes())} bytes"
        return f"StaticTransport({state}, calls={self.calls})"

    # -- payload management -----------------------------------------------------

    def _bytes(self) -> bytes:
        payload = self.payload
        if isinstance(payload, str):
            return payload.encode("utf-8")
        if isinstance(payload, (bytes, bytearray, memoryview)):
            return bytes(payload)
        raise TypeError(f"payload must be bytes or text, not {type(payload).__name__}")

    def serve(self, payload: bytes | bytearray | memoryview | str) -> bytes:
        """Serve ``payload`` on subsequent fetches and clear any injected failure."""
        if payload is None:
            raise TypeError("use cut() to make the transport unreachable")
        self.payload = payload
        self.fail_with = None
        return self._bytes()

    def cut(self) -> None:
        """Make the list unreachable: every fetch now raises :class:`FetchError`."""
        self.payload = None

    @property
    def reachable(self) -> bool:
        """True when a fetch would currently succeed."""
        return self.payload is not None and self.fail_with is None

    # -- Transport protocol -----------------------------------------------------

    def fetch_bytes(self) -> bytes:
        """Deliver the payload once, or raise loudly (no retry, no fallback)."""
        self.calls += 1
        if self.fail_with is not None:
            self.history.append(f"error:{type(self.fail_with).__name__}")
            raise self.fail_with
        if self.payload is None:
            self.history.append("unreachable")
            raise FetchError(
                "static transport is cut: no revocation list payload to serve",
                url=self.url,
                kind="network",
            )
        data = self._bytes()
        self.history.append(f"ok:{len(data)}")
        return data


class FakeClock:
    """Deterministic clock: starts at ``DEFAULT_CLOCK_START``, moves only via ``advance``/``set``.

    :func:`~tools.marketplace.revocation_list.degrade.clock_now` (and so the
    ``DegradeSink`` and ``RevocationClient``) reads it through ``now()``; the
    object is also callable.  Reads are counted in ``reads``.
    """

    def __init__(self, start: datetime | str | int | float | None = None) -> None:
        self._now: datetime = clock_now(DEFAULT_CLOCK_START if start is None else start)
        self.reads = 0

    def __repr__(self) -> str:
        return f"FakeClock({self.iso()}, reads={self.reads})"

    def now(self) -> datetime:
        """The current fake instant as an aware UTC ``datetime``."""
        self.reads += 1
        return self._now

    def __call__(self) -> datetime:
        return self.now()

    def iso(self) -> str:
        """The current instant rendered as ``YYYY-MM-DDTHH:MM:SSZ`` (does not count as a read)."""
        return iso_utc(self._now)

    def set(self, moment: datetime | str | int | float) -> datetime:
        """Jump to ``moment`` (ISO text, aware/naive datetime or epoch seconds)."""
        if moment is None:
            raise TypeError("FakeClock.set needs an explicit instant, not None")
        self._now = clock_now(moment)
        return self._now

    def advance(
        self,
        seconds: float = 0.0,
        *,
        minutes: float = 0.0,
        hours: float = 0.0,
        days: float = 0.0,
    ) -> datetime:
        """Move forward by the given amount; a fake clock never runs backwards."""
        delta = timedelta(seconds=seconds, minutes=minutes, hours=hours, days=days)
        if delta < timedelta(0):
            raise ValueError("FakeClock.advance cannot go backwards; use set() to jump")
        self._now = self._now + delta
        return self._now
