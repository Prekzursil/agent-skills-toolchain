"""Task status assembly — pure, dependency-free (grill S5/S7/S8).

This module folds the four core signals — a source :class:`~core.models.PollResult`,
a :class:`~probes.base.ProbeReading`, the liveness verdict, and the elapsed/prior
timing — into ONE :class:`TaskView`, the flat record every consumer renders:
``--json`` serialises ``to_dict()``; ``ui.render`` builds strings from it.

Two grill invariants live here:

* **BLIND wins over stale progress (S7).** A failed poll (``poll.blind``) yields
  status ``BLIND`` with an age stamp; the last frontier is still shown but never
  relabelled ``DONE``.
* **Honest ETA (S8).** :func:`select_eta` uses the *measured* fraction when a rate
  is knowable, falls back to a historical prior, and otherwise returns a
  not-estimable estimate (provenance ``NONE``) — never a fabricated countdown.

Every function is pure ``objects → objects`` so 100% branch coverage is reachable
with plain fixtures and no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.eta import linear_frac_eta, prior_eta
from core.models import EtaEstimate, PollResult, Provenance, TaskStatus, TaskSpec
from probes.base import ProbeReading

_NONE_ETA = EtaEstimate(p50=None, p90=None, provenance=Provenance.NONE)

# Terminal-failure markers an http-json body (or a probe detail) may carry.
_FAILED_TOKENS = frozenset({"failed", "failure", "error", "cancelled", "canceled"})


def derive_status(
    *,
    blind: bool,
    failed: bool,
    terminal: bool,
    exists: bool,
    progressing: bool,
    has_progress: bool,
    stalled: bool,
) -> TaskStatus:
    """Map the boolean signal set to a single lifecycle verdict.

    Precedence (highest first): BLIND (can't trust this poll) → FAILED → DONE →
    (absent ⇒ PENDING) → STALLED → RUNNING → PENDING. A stalled run is never
    silently rendered as done (grill S7).
    """
    if blind:
        return TaskStatus.BLIND
    if failed:
        return TaskStatus.FAILED
    if terminal:
        return TaskStatus.DONE
    if not exists:
        return TaskStatus.PENDING
    if stalled:
        return TaskStatus.STALLED
    if progressing or has_progress:
        return TaskStatus.RUNNING
    return TaskStatus.PENDING


def select_eta(
    *,
    fraction: float | None,
    elapsed_s: float | None,
    prior_duration_s: float | None,
) -> EtaEstimate:
    """Pick the most honest ETA available for a task (grill S8).

    Prefers the MEASURED linear-fraction estimate; when no live rate is knowable
    yet, falls back to a historical PRIOR; otherwise returns not-estimable
    (provenance NONE) so the caller shows elapsed+rate, not a fake percentage.
    """
    if fraction is not None and elapsed_s is not None:
        measured = linear_frac_eta(fraction, elapsed_s)
        if measured.estimable:
            return measured
    if prior_duration_s is not None and elapsed_s is not None:
        prior = prior_eta(prior_duration_s, elapsed_s)
        if prior.estimable:
            return prior
    return _NONE_ETA


def detect_failed(poll: PollResult) -> bool:
    """True when an http-json body advertises a terminal-failure ``status``."""
    status_value = poll.raw.get("status")
    if not isinstance(status_value, str):
        return False
    return status_value.strip().lower() in _FAILED_TOKENS


@dataclass
class TaskView:
    """Flat, render-ready snapshot of one task's current state."""

    id: str
    adapter: str
    parser: str
    status: TaskStatus
    exists: bool
    done: float | None
    total: float | None
    fraction: float | None
    phase: str
    gpu: str
    terminal: bool
    eta: EtaEstimate
    progressing: bool
    stalled: bool
    blind: bool
    blind_age: float | None
    elapsed_s: float | None
    error: str | None
    detail: str
    lines_seen: int = 0
    notify: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "adapter": self.adapter,
            "parser": self.parser,
            "status": self.status.value,
            "exists": self.exists,
            "done": self.done,
            "total": self.total,
            "fraction": self.fraction,
            "phase": self.phase,
            "gpu": self.gpu,
            "terminal": self.terminal,
            "eta": self.eta.to_dict(),
            "progressing": self.progressing,
            "stalled": self.stalled,
            "blind": self.blind,
            "blind_age": self.blind_age,
            "elapsed_s": self.elapsed_s,
            "error": self.error,
            "detail": self.detail,
            "lines_seen": self.lines_seen,
            "notify": list(self.notify),
        }


def assemble_view(
    spec: TaskSpec,
    poll: PollResult,
    reading: ProbeReading,
    *,
    progressing: bool,
    stalled: bool,
    elapsed_s: float | None,
    prior_duration_s: float | None,
    blind_age: float | None = None,
) -> TaskView:
    """Fold a poll + probe reading + timing into a :class:`TaskView`.

    ``progressing``/``stalled`` are the liveness-plane verdict the caller derived
    (from an mtime-age or a multi-sample monitor); ``elapsed_s``/``prior_duration_s``
    feed :func:`select_eta`. A blind poll (``poll.blind``) forces status BLIND and
    suppresses the not-yet-trustworthy stall flag while keeping the last frontier.
    """
    blind = poll.blind
    failed = detect_failed(poll)
    fraction = reading.fraction()
    eta = select_eta(
        fraction=fraction,
        elapsed_s=elapsed_s,
        prior_duration_s=prior_duration_s,
    )
    status = derive_status(
        blind=blind,
        failed=failed,
        terminal=reading.terminal,
        exists=poll.exists,
        progressing=progressing,
        has_progress=reading.has_progress,
        stalled=stalled,
    )
    return TaskView(
        id=spec.id,
        adapter=spec.adapter,
        parser=spec.parser,
        status=status,
        exists=poll.exists,
        done=reading.done,
        total=reading.total,
        fraction=fraction,
        phase=reading.phase,
        gpu=reading.gpu,
        terminal=reading.terminal,
        eta=eta,
        progressing=progressing and not blind,
        stalled=stalled and not blind,
        blind=blind,
        blind_age=blind_age,
        elapsed_s=elapsed_s,
        error=poll.error,
        detail=reading.detail,
        lines_seen=len(poll.lines),
        notify=list(spec.notify),
    )
