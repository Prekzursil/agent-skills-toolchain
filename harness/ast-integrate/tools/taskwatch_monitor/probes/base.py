"""Probe vocabulary + rolloff-immune parsing helpers (grill S6).

:class:`ProbeReading` is what every probe emits: a ``done``/``total`` frontier
plus phase, GPU, and terminal flags. :func:`frontier_of` computes the MAX index
reached (never a distinct-count), and :meth:`ProbeReading.fraction` is NEVER
clamped — an overshoot is preserved so the downstream ETA band widens instead of
a hidden cap. All helpers are pure ``str``/list → objects, so 100% branch
coverage is reachable with plain string fixtures.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from core.models import PollResult

# A bare ``N/M`` ratio anywhere in a line (windows, edges, trials, "12/20").
_RATIO_RE = re.compile(r"(\d+)\s*/\s*(\d+)")

# GPU / progress heartbeat tags used by the FEP and BPMD drivers:
#   ``[prog] ... GPU 0 ...``  ``[gpu-util] 0: 98%, ...``
_GPU_TAG_RE = re.compile(r"\[(?:gpu-util|prog)\]\s*(.+)")


class ProbeError(ValueError):
    """Raised when a probe name cannot be resolved to a probe."""


@dataclass
class ProbeReading:
    """One probe's distilled view of a task's progress.

    ``done``/``total`` are the frontier and its denominator (``total`` is
    ``None`` when the log has not revealed one). ``frontier`` echoes the raw max
    index for display; ``gpu`` is the last GPU/heartbeat detail; ``terminal`` is
    set once a completion marker (out.fmp, ddG, PoseScore, "done") is seen.
    """

    done: float | None
    total: float | None
    phase: str
    frontier: float | None
    gpu: str
    terminal: bool
    detail: str

    def fraction(self) -> float | None:
        """done/total — NOT clamped to [0, 1] (grill S6a).

        ``None`` when the frontier or its denominator is unknown/non-positive.
        An overshoot (>1.0) is deliberately preserved so an ETA model widens its
        band rather than a hidden clamp masking that the frontier ran long.
        """
        if self.done is None or self.total is None or self.total <= 0:
            return None
        return self.done / self.total

    @property
    def has_progress(self) -> bool:
        """True when the probe found a numeric frontier this poll."""
        return self.done is not None

    def to_dict(self) -> dict[str, object]:
        return {
            "done": self.done,
            "total": self.total,
            "phase": self.phase,
            "frontier": self.frontier,
            "gpu": self.gpu,
            "terminal": self.terminal,
            "detail": self.detail,
            "fraction": self.fraction(),
        }


class Probe(Protocol):
    """A log-line parser producing a :class:`ProbeReading`."""

    name: str

    def parse(self, lines: list[str]) -> ProbeReading: ...


def parse_ratio(line: str) -> tuple[int, int] | None:
    """Extract the first ``N/M`` ratio in ``line`` as ``(N, M)`` (or ``None``)."""
    match = _RATIO_RE.search(line)
    if match is None:
        return None
    return (int(match.group(1)), int(match.group(2)))


def frontier_of(ratios: list[tuple[int, int]]) -> tuple[int, int] | None:
    """Frontier of ``(numerator, denominator)`` pairs (grill S6b).

    Returns ``(max numerator, max denominator)`` — the FRONTIER reached, NOT the
    number of distinct ratios seen, so a rolled-over / re-ordered log tail can
    never undercount. ``None`` for an empty list. The denominator is NOT used to
    cap the numerator (no phantom cap).
    """
    if not ratios:
        return None
    done = max(numerator for numerator, _ in ratios)
    total = max(denominator for _, denominator in ratios)
    return (done, total)


def extract_gpu(line: str) -> str | None:
    """Return the ``[prog]``/``[gpu-util]`` heartbeat detail, or ``None``."""
    match = _GPU_TAG_RE.search(line)
    if match is None:
        return None
    return match.group(1).strip()


def join_detail(*parts: str) -> str:
    """Join the non-empty display parts with a middot separator."""
    return " · ".join(part for part in parts if part)


def reading_from_poll(probe: Probe, poll: PollResult) -> ProbeReading:
    """Run ``probe`` over a poll's ``lines`` (the adapter → probe bridge)."""
    return probe.parse(poll.lines)
