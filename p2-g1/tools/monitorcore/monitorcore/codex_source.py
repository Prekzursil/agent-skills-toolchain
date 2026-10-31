"""``codex_source`` — the ``CodexSource`` adapter: Codex threads behind the contract.

The first IN-PACKAGE :class:`~monitorcore.contract.MonitorSource` (PR-B3; structurally
a clone of the wfmon skill's ``WfmonSource``). It wraps the ``codex_tail`` domain layer
(:class:`~monitorcore.codex_tail.Poller` over relay stream files + persisted rollouts)
as a contract adapter: ``poll()`` runs one discover → ingest → prune → recompute tick
and snapshots the fleet into a typed :class:`CodexPayload` — a tuple of the domain's
own :class:`~monitorcore.codex_tail.CodexThread` objects, **never flattened to a dict**
(E-1's cardinal guardrail).

The contract's cardinal rule is honoured: ``poll`` wraps the tick in ``except
Exception`` and, on any failure, returns a stale / unreachable snapshot (its last-good
payload if it has one, the exception text in ``error``) WITHOUT raising — a broken
stream dir degrades one board row instead of tearing the board down. ``BaseException``
(Ctrl-C / SystemExit) is deliberately not caught.

Redaction: every free-text field inside a ``CodexThread`` was ALREADY scrubbed at
ingest by ``codex_tail`` (mandatory, no off switch), and the adapter re-scrubs its own
composed ``headline`` / ``alert`` strings through the same fail-closed floor — so
nothing downstream needs to re-scrub. ``alert`` is **signature-only** here (PR-B): it
classifies a snapshot into a redaction-safe :class:`~monitorcore.contract.Alert` or
``None``; the delivery rail is PR-G.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timezone

from .codex_tail import (
    CodexThread,
    Poller,
    ToolEvent,
    board_line,
    default_sessions_dir,
    default_stream_dir,
)
from .contract import Alert, Snapshot, SourceState
from .redact import redact
from .report_doc import ReportDoc, Section
from .textsafe import strip_controls
from .timeline import TimelineEvent

_ID = "codexmon"

# ``ToolEvent.kind`` → generic ``TimelineEvent.kind`` (unknown kinds fall through to text).
_TL_KIND = {
    "cmd": "tool_use",
    "tool": "tool_use",
    "patch": "tool_use",
    "think": "thinking",
    "msg": "text",
}


def _events_timeline(events: Iterable[ToolEvent]) -> tuple[TimelineEvent, ...]:
    """Map a thread's captured ``ToolEvent`` deque onto the generic ``TimelineEvent`` stream.

    So the shared exporters render the progress ledger (WU2's event feed) as a per-card
    timeline "for free". cmd/tool/patch → ``tool_use`` (name = the event label, its scrubbed
    detail as the single input + output, ``is_error`` from the event status); ``think`` →
    ``thinking``; every other kind → ``text`` carrying the detail, else the label. Every
    field is ALREADY scrubbed at ingest by ``codex_tail`` (no off switch).
    """
    out: list[TimelineEvent] = []
    for seq, ev in enumerate(events):
        kind = _TL_KIND.get(ev.kind, "text")
        if kind == "tool_use":
            out.append(
                TimelineEvent(
                    kind="tool_use",
                    seq=seq,
                    name=ev.label,
                    tool_input={"detail": ev.detail} if ev.detail else {},
                    output=ev.detail,
                    is_error=ev.status == "error",
                )
            )
        else:
            out.append(TimelineEvent(kind=kind, seq=seq, text=ev.detail or ev.label))
    return tuple(out)


@dataclass(frozen=True)
class CodexPayload:
    """Typed per-adapter payload — the native thread models; NEVER flattened.

    ``threads`` is empty only before the first successful poll (an unreachable snapshot
    with no retained last-good value) or when no Codex activity is in the window. The
    tuple snapshots MEMBERSHIP at poll time; the ``CodexThread`` objects themselves are
    the live domain models the poller keeps updating (already scrubbed at ingest).
    """

    threads: tuple[CodexThread, ...] = ()


def _redact(text: str) -> str:
    """Strip control bytes, THEN mask secrets / collapse home paths (fail-closed).

    Control bytes are removed FIRST so redaction sees de-obfuscated text and no ESC/BEL/OSC
    byte survives into the composed ``headline`` / ``alert`` strings the cockpit prints — the
    same fail-closed floor :func:`monitorcore.codex_tail._scrub` applies at ingest. (This
    adapter previously only redacted, so a control-laden exception string could reach the
    terminal via the unclipped ``render_native`` headline fallback and the alert rail.)
    """
    return redact(strip_controls(text), enabled=True)[0]


class CodexSource:
    """A :class:`~monitorcore.contract.MonitorSource` over the local Codex fleet."""

    id = _ID

    def __init__(
        self,
        *,
        stream_dir: str | None = None,
        sessions_dir: str | None = None,
        since_min: float = 30.0,
        idle_s: float = 12.0,
        max_threads: int = 12,
        poller: Poller | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._idle_s = idle_s
        self._clock = clock
        self._poller = (
            poller
            if poller is not None
            else Poller(
                stream_dir or default_stream_dir(),
                sessions_dir or default_sessions_dir(),
                since_min=since_min,
                max_threads=max_threads,
                clock=clock,
            )
        )
        self._last: Snapshot[CodexPayload] | None = None

    # ───────────────────────── poll (never throws) ─────────────────────────
    def poll(self) -> Snapshot[CodexPayload]:
        # The clock read is INSIDE the guard: the contract's cardinal rule covers
        # the injected clock too (it is also threaded into the Poller), so a broken
        # clock degrades one board row instead of escaping poll. ts stays 0.0 when
        # the clock itself is what failed -- there is no time to report.
        ts = 0.0
        try:
            ts = self._clock()
            self._poller.discover()
            self._poller.ingest()
            self._poller.prune()
            threads = tuple(self._poller.threads.values())
            for th in threads:
                th.recompute_status(ts, self._idle_s)
        # NEVER raise out of poll (BaseException still propagates by design).
        except Exception as exc:
            payload = self._last.payload if self._last is not None else CodexPayload()
            return Snapshot(
                source_id=self.id,
                ts=ts,
                reachable=False,
                stale=True,
                state=SourceState.UNREACHABLE,
                headline=self._headline(None, SourceState.UNREACHABLE, str(exc)),
                payload=payload,
                age_s=None,
                error=str(exc),
            )
        state = self._derive_state(threads)
        newest = max((th.last_ts for th in threads if th.last_ts), default=0.0)
        # A registered stream whose PENDING bytes could not be read makes this tick a
        # partial measurement: those threads carry retained last-good state, so the
        # snapshot must not claim freshness. Publishing it as reachable+fresh let a
        # share-locked stream read as a healthy source and silently age a running thread
        # to idle during the outage. ``reachable`` stays True while at least one tail
        # still delivered — the source WAS touched (contract.py:80-85); every tail
        # failing means it could not be reached at all this tick.
        unread = self._poller.read_errors()
        error = "; ".join(f"{key}: {err}" for key, err in unread) if unread else None
        reachable = not unread or len(unread) < len(self._poller.tails)
        if not reachable:
            state = SourceState.UNREACHABLE
        snap = Snapshot(
            source_id=self.id,
            ts=ts,
            reachable=reachable,
            stale=bool(unread),
            state=state,
            headline=self._headline(threads, state, error, len(unread)),
            payload=CodexPayload(threads=threads),
            age_s=(ts - newest) if newest else None,
            error=error,
        )
        self._last = snap
        return snap

    # ───────────────────────── coarse-state derivation ─────────────────────────
    @staticmethod
    def _derive_state(threads: tuple[CodexThread, ...]) -> SourceState:
        """Collapse the fleet's thread statuses into the coarse cross-domain state.

        ``error`` if any thread aborted; else ``running`` while any thread is active;
        else ``done`` when every tracked thread finished; else ``idle`` (no threads in
        the window, or only quiet ones). ``stalled`` stays the watchdog's word.
        """
        if not threads:
            return SourceState.IDLE
        statuses = {th.status for th in threads}
        if "aborted" in statuses:
            return SourceState.ERROR
        if "running" in statuses:
            return SourceState.RUNNING
        if statuses == {"done"}:
            return SourceState.DONE
        return SourceState.IDLE

    def _headline(
        self,
        threads: tuple[CodexThread, ...] | None,
        state: SourceState,
        error: str | None,
        unread: int = 0,
    ) -> str:
        """A redaction-safe one-line status (``unreachable`` on a failed poll).

        ``unread`` is how many registered streams lost pending bytes this tick; a
        non-zero count is printed so a partial measurement is never shown as a
        complete one.
        """
        if threads is None:
            return _redact(f"unreachable: {error}")
        counts = {"running": 0, "idle": 0, "done": 0, "aborted": 0}
        for th in threads:
            counts[th.status] = counts.get(th.status, 0) + 1
        suffix = f" · {unread} unreadable" if unread else ""
        return _redact(
            f"codex [{state}] "
            f"{counts['running']} running / {counts['done']} done / "
            f"{counts['aborted']} aborted of {len(threads)}{suffix}"
        )

    # ───────────────────────── contract surface ─────────────────────────
    def render_native(self, snap: Snapshot[CodexPayload]) -> object:
        """The codex-native board lines (falls back to the headline with no threads)."""
        threads = snap.payload.threads
        if not threads:
            return snap.headline
        return "\n".join(board_line(th, snap.ts) for th in threads)

    def export_model(self, snap: Snapshot[CodexPayload]) -> ReportDoc:
        """Map the snapshot onto the generic ``ReportDoc`` (one entity card per thread).

        ``generated_at`` derives deterministically from the snapshot's own poll epoch,
        so identical snapshots export byte-identically through the shared renderers.
        """
        threads = snap.payload.threads
        generated = datetime.fromtimestamp(snap.ts, tz=timezone.utc).isoformat()
        counts = {"running": 0, "idle": 0, "done": 0, "aborted": 0}
        for th in threads:
            counts[th.status] = counts.get(th.status, 0) + 1
        # The renderer-canonical rollup keys (total/done/error/running/idle/tokens);
        # an aborted codex thread maps onto the generic ``error`` bucket.
        rollup = (
            ("total", len(threads)),
            ("done", counts["done"]),
            ("error", counts["aborted"]),
            ("running", counts["running"]),
            ("idle", counts["idle"]),
            ("tokens", sum(th.tokens_total for th in threads)),
        )
        blocks = tuple(
            Section(
                title=th.name(),
                anchor=f"codex-{i}",
                index=i,
                card=True,
                badge=th.status,
                model=th.model,
                tokens=th.tokens_total,
                tool_calls=th.tool_count,
                lead=f"{th.turns} turns · {th.source}",
                task=th.prompt,
                timeline=_events_timeline(th.events),
            )
            for i, th in enumerate(threads)
        )
        return ReportDoc(
            title="codexmon",
            generated_at=generated,
            blocks=blocks,
            subtitle=snap.headline,
            meta=(("source", self.id), ("threads", str(len(threads)))),
            rollup=rollup,
            active=snap.state == SourceState.RUNNING,
            redaction_mode="strict",
        )

    def headline(self, snap: Snapshot[CodexPayload]) -> str:
        """The redaction-safe one-liner (computed at poll time)."""
        return snap.headline

    def alert(self, snap: Snapshot[CodexPayload]) -> Alert | None:
        """Classify a snapshot into a redaction-safe :class:`Alert` — SIGNATURE ONLY.

        ``error`` → ``critical``; ``unreachable`` / ``stalled`` → ``warn``; healthy
        states → ``None``. Delivery (ntfy / toast / dead-man) is PR-G.
        """
        if snap.state in (
            SourceState.ERROR,
            SourceState.UNREACHABLE,
            SourceState.STALLED,
        ):
            level = "critical" if snap.state == SourceState.ERROR else "warn"
            return Alert(
                source_id=snap.source_id,
                level=level,
                headline=_redact(snap.headline),
                detail=_redact(snap.error or ""),
                ts=snap.ts,
            )
        return None
