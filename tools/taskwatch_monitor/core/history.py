"""SQLite history / prior store, keyed by task-type (grill S8/S9).

Completed runs are recorded as ``(task_type, duration_s, ts)`` rows; a prior for
a task-type summarises its past durations (count, p50, p90) so an ETA model can
fall back to :func:`core.eta.prior_eta` with ``Provenance.PRIOR`` before any
live rate is measurable.

The path is injected (use ``":memory:"`` in tests); the connection is owned by
the store and closed via :meth:`close` or the context-manager protocol.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from statistics import median
from types import TracebackType
from typing import cast

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    task_type TEXT NOT NULL,
    duration  REAL NOT NULL,
    ts        REAL NOT NULL
)
"""


@dataclass
class Prior:
    """Summary of past durations for one task-type."""

    task_type: str
    count: int
    p50: float
    p90: float

    def to_dict(self) -> dict[str, object]:
        return {
            "task_type": self.task_type,
            "count": self.count,
            "p50": self.p50,
            "p90": self.p90,
        }


def _percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile of a non-empty, unsorted ``values`` list."""
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = pct * (len(ordered) - 1)
    lo = int(rank)
    if lo >= len(ordered) - 1:
        return ordered[-1]
    frac = rank - lo
    return ordered[lo] + (ordered[lo + 1] - ordered[lo]) * frac


class HistoryStore:
    """Thin SQLite wrapper for recording runs and computing priors."""

    def __init__(self, path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(path)
        _ = self._conn.execute(_SCHEMA)
        self._conn.commit()

    def record(self, task_type: str, duration_s: float, *, ts: float) -> None:
        """Persist one completed run's duration for a task-type."""
        _ = self._conn.execute(
            "INSERT INTO runs (task_type, duration, ts) VALUES (?, ?, ?)",
            (task_type, duration_s, ts),
        )
        self._conn.commit()

    def durations(self, task_type: str) -> list[float]:
        """All recorded durations for a task-type (empty if none)."""
        cur = self._conn.execute(
            "SELECT duration FROM runs WHERE task_type = ? ORDER BY ts",
            (task_type,),
        )
        return [cast("float", row[0]) for row in cur.fetchall()]

    def prior(self, task_type: str) -> Prior | None:
        """Summarise a task-type's past durations, or None if it has none."""
        values = self.durations(task_type)
        if not values:
            return None
        return Prior(
            task_type=task_type,
            count=len(values),
            p50=float(median(values)),
            p90=_percentile(values, 0.9),
        )

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "HistoryStore":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
