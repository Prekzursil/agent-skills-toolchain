"""``contract`` — the typed ``MonitorSource`` / ``Snapshot`` contract every adapter plugs into.

A monitor *source* (wfmon, agents, fep, mcp, …) implements :class:`MonitorSource`: it
``poll()`` s its domain into an immutable :class:`Snapshot` carrying a coarse
:class:`SourceState`, a redaction-safe one-line ``headline``, reachability/freshness flags,
and a **typed per-adapter ``payload``** that is NEVER flattened to a lowest-common-denominator
dict (the ``payload`` is the domain's own model — E-1's cardinal guardrail). The same source
renders its domain-native live view (``render_native``), maps a snapshot onto the generic
:class:`~monitorcore.report_doc.ReportDoc` for the shared exporters (``export_model``), and —
**signature only in PR-B** — classifies a snapshot into an optional :class:`Alert` (``alert``;
the *delivery* rail — ntfy / toast / dead-man — is PR-G, nothing is wired here).

The cardinal rule of ``poll``: **it MUST NOT raise.** An adapter wraps its reader in
``except Exception`` and, on any failure, returns a *stale* / *unreachable* snapshot (its
last-good payload if it has one, the exception text in ``error``) so a flaky or remote source
degrades a single board row instead of tearing the whole board down. ``BaseException``
(``KeyboardInterrupt`` / ``SystemExit``) is deliberately NOT swallowed.

The module is stdlib-only and depends only on :mod:`monitorcore.report_doc`, so it vendors
cleanly into a skill's plain Python. ``Alert`` is defined here (not merely referenced) so
``basedpyright`` standard mode resolves every annotation without a forward-ref stub.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, Protocol, TypeVar, runtime_checkable

from .report_doc import ReportDoc

__all__ = ["Alert", "MonitorSource", "Snapshot", "SourceState"]

# The per-adapter payload type — agents / fep / training / mcp. It is threaded through
# ``Snapshot[P]`` and ``MonitorSource[P]`` so each adapter keeps its own typed model and the
# contract never forces a shared, lossy shape.
P = TypeVar("P")


class SourceState(StrEnum):
    """The coarse, cross-domain status of a polled source (a ``str`` at runtime).

    ``idle`` — reachable, nothing in flight · ``running`` — work active · ``done`` — terminal,
    no error · ``error`` — a unit failed · ``unreachable`` — ``poll`` could not reach the
    source · ``stalled`` — reachable but frozen past its dead-man window. ``stalled`` is a
    permitted value produced by the agent watchdog adapter (PR-B2); ``WfmonSource`` in PR-B1
    emits the first five.
    """

    IDLE = "idle"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"
    UNREACHABLE = "unreachable"
    STALLED = "stalled"


@dataclass(frozen=True)
class Alert:
    """A classified, redaction-safe alert — **signature-only in PR-B** (no delivery rail).

    ``alert()`` returns one of these or ``None``; PR-G builds the rails that consume it.
    ``level`` is a coarse severity (``warn`` | ``critical``). ``headline`` / ``detail`` are
    already redaction-safe: the adapter runs them through :func:`monitorcore.redact.redact`
    before constructing the alert, so nothing downstream needs to re-scrub.
    """

    source_id: str
    level: str
    headline: str
    detail: str = ""
    ts: float = 0.0


@dataclass(frozen=True)
class Snapshot(Generic[P]):
    """One immutable poll result from a source.

    ``source_id`` identifies the emitting source; ``ts`` is the epoch of this poll.
    ``reachable`` is ``False`` when ``poll`` could not reach the source; ``stale`` is ``True``
    when ``payload`` is a retained last-good value (the poll failed / timed out). ``state`` is
    the coarse :class:`SourceState`; ``headline`` is a redaction-safe one-liner. ``payload`` is
    the **typed per-adapter** model — never flattened. ``age_s`` is seconds since the source
    last advanced (``None`` when the adapter does not compute freshness); ``error`` carries the
    failure text on an unreachable / stale snapshot.
    """

    source_id: str
    ts: float
    reachable: bool
    stale: bool
    state: SourceState
    headline: str
    payload: P
    age_s: float | None = None
    error: str | None = None


@runtime_checkable
class MonitorSource(Protocol[P]):
    """The behavioural contract an adapter implements to appear on the unified board.

    ``poll`` MUST NOT raise (``except Exception`` → stale/unreachable :class:`Snapshot`).
    ``render_native`` returns the domain's own live view (kept per-domain, never genericised).
    ``export_model`` maps a snapshot onto the shared :class:`~monitorcore.report_doc.ReportDoc`
    so every source exports "for free" through the generic renderers. ``headline`` is the
    redaction-safe one-liner; ``alert`` classifies a snapshot into an optional :class:`Alert`
    (delivery is PR-G).
    """

    id: str

    def poll(self) -> Snapshot[P]: ...
    def render_native(self, snap: Snapshot[P]) -> object: ...
    def export_model(self, snap: Snapshot[P]) -> ReportDoc: ...
    def headline(self, snap: Snapshot[P]) -> str: ...
    def alert(self, snap: Snapshot[P]) -> Alert | None: ...
