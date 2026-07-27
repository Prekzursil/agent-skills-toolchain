"""``databricks_source`` — the ``DatabricksSource`` adapter: Databricks work units.

Increment 1 of the dbx monitor. A :class:`~monitorcore.contract.MonitorSource` over a
Databricks fan-out's append-only NDJSON event stream, structurally a sibling of
:class:`~monitorcore.codex_source.CodexSource`.

**No network, ever.** This module performs ZERO Databricks API calls. The lifecycle
probe is an *injected* zero-arg callable (``api``) supplied by the caller; the default
is ``None``, in which case lifecycle status comes from the event stream alone. That
keeps the adapter unit-testable against fixtures and keeps credential handling out of
the monitor.

Two cardinal invariants (non-negotiable, from the design):

1. **``poll`` MUST NEVER RAISE.** Every reader / normalizer / API failure is wrapped in
   ``except Exception`` and degrades to a stale, ``unreachable`` snapshot carrying the
   last-good payload. ``BaseException`` (``KeyboardInterrupt`` / ``SystemExit``) is
   deliberately NOT swallowed.
2. **``payload`` is NEVER flattened.** :class:`DbxPayload` carries native
   :class:`DbxUnit` dataclasses.

**Where the eight-state vocabulary lives.** ``SourceState`` is ROW-level and gains NO
new constant here; the eight-state UNIT liveness vocabulary (:class:`Liveness`) lives
INSIDE the payload on ``DbxUnit.liveness`` — exactly as ``codex_source`` carries its
richer per-thread status in its own payload.

**The THINKING-vs-STALLED discriminator.** Transcript silence ALONE is never enough.
:func:`derive_liveness` combines seven signals — last event time, heartbeat age, task
lifecycle status, artifact growth, tool-call state, lease renewal, and retry state —
and hard-guards two cases: a unit with a blocking tool call in flight
(``TOOL_ACTIVE``) or a known-active remote task (``WAITING_EXTERNAL``) is NEVER
classified ``STALLED``, no matter how long it has been quiet. Thresholds are injected
via :class:`LivenessThresholds`, never hard-coded at a call site.

**Cumulative CPU is banned as a liveness or victim-ranking signal.** A process blocked
inside a call burns almost no CPU, so a cumulative-CPU reading *inverts* the answer —
the busiest-looking unit is the healthy one and the wedged one looks idle. No field,
identifier, or code path here reads a CPU signal, and a ``cpu_*`` field arriving on an
event record is ignored by construction (only the kinds in :func:`_apply` are read).

**No decorative spinner.** ``DbxUnit.busy`` is a pure function of REAL arrival
(:func:`is_busy`): true only when an event, heartbeat, lease renewal, retry, or
artifact growth landed inside ``busy_window_s``. It is deliberately INDEPENDENT of the
liveness label — a unit blocked in a long tool call reads ``TOOL_ACTIVE`` with
``busy=False``, because nothing is arriving. A dead agent can never keep spinning.
"""

from __future__ import annotations

import importlib
import json
import os
import time
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import StrEnum
from types import ModuleType

from .contract import Alert, Snapshot, SourceState
from .redact import scrub
from .report_doc import ReportDoc, Section

__all__ = [
    "DatabricksSource",
    "DbxPayload",
    "DbxUnit",
    "Liveness",
    "LivenessThresholds",
    "busy_glyph",
    "default_events_path",
    "derive_liveness",
    "is_busy",
]

_ID = "dbxmon"

#: Lifecycle statuses that mean the unit will never advance again.
_TERMINAL_STATUSES = frozenset(
    {"TERMINATED", "SUCCESS", "SUCCEEDED", "FAILED", "CANCELED", "CANCELLED", "SKIPPED"}
)
#: Lifecycle statuses that mean the unit has not begun executing.
_QUEUED_STATUSES = frozenset({"PENDING", "QUEUED", "BLOCKED", "WAITING"})

#: Busy / not-busy glyphs. Two DISTINCT characters — a constant here would make the
#: indicator decorative, which is exactly what the design forbids.
_GLYPH_BUSY = "*"
_GLYPH_IDLE = "-"


class Liveness(StrEnum):
    """The eight-state UNIT liveness vocabulary — payload-level, never a ``SourceState``.

    ``QUEUED`` — admitted, not started · ``STARTING`` — started, nothing has arrived yet
    (inside the grace window) · ``THINKING`` — arrivals are recent · ``TOOL_ACTIVE`` — a
    blocking tool call is in flight (never STALLED) · ``WAITING_EXTERNAL`` — a remote
    task is running on the unit's behalf (never STALLED) · ``HEARTBEAT_LATE`` — nothing
    has arrived on ANY channel past ``heartbeat_late_s`` · ``STALLED`` — past
    ``stalled_s`` AND no tool call and no remote task · ``TERMINAL`` — finished,
    cancelled, or failed.
    """

    QUEUED = "QUEUED"
    STARTING = "STARTING"
    THINKING = "THINKING"
    TOOL_ACTIVE = "TOOL_ACTIVE"
    WAITING_EXTERNAL = "WAITING_EXTERNAL"
    HEARTBEAT_LATE = "HEARTBEAT_LATE"
    STALLED = "STALLED"
    TERMINAL = "TERMINAL"


#: Liveness values that mean the unit is doing work right now (row-level ``running``).
_ACTIVE = frozenset(
    {
        Liveness.STARTING,
        Liveness.THINKING,
        Liveness.TOOL_ACTIVE,
        Liveness.WAITING_EXTERNAL,
        Liveness.HEARTBEAT_LATE,
    }
)


@dataclass(frozen=True)
class LivenessThresholds:
    """Injected, per-deployment liveness windows — NEVER hard-coded at a call site.

    ``heartbeat_late_s`` — quiet longer than this on every channel → ``HEARTBEAT_LATE``.
    ``stalled_s`` — quiet longer than this, with no tool call and no remote task →
    ``STALLED``. ``busy_window_s`` — the arrival window the busy indicator reads.
    ``starting_grace_s`` — how long after ``start`` a unit may have zero arrivals and
    still read ``STARTING`` rather than being judged on silence.
    """

    heartbeat_late_s: float = 90.0
    stalled_s: float = 300.0
    busy_window_s: float = 30.0
    starting_grace_s: float = 20.0


@dataclass(frozen=True)
class DbxUnit:
    """One Databricks work unit — the typed payload member, NEVER flattened.

    The first block is raw observed fact (the seven discriminator signals); the second
    is derived at poll time. Note the absence of any CPU field: cumulative CPU is a
    banned liveness signal (see the module docstring).
    """

    unit_id: str
    run_id: str = ""
    # ── raw observed facts ──
    last_event_ts: float = 0.0  # signal 1: last transcript event
    heartbeat_ts: float = 0.0  # signal 2: last heartbeat
    task_status: str = "PENDING"  # signal 3: task lifecycle status
    artifact_bytes: int = 0  # signal 4: artifact growth
    prev_artifact_bytes: int = 0
    artifact_ts: float = 0.0
    tool_active: bool = False  # signal 5: tool-call state
    tool_name: str = ""
    lease_held: bool = False  # signal 6: lease status
    lease_renewed_ts: float = 0.0
    retries: int = 0  # signal 7: retry state
    last_retry_ts: float = 0.0
    remote_task_active: bool = False
    remote_task_id: str = ""
    started_ts: float = 0.0
    cancelled: bool = False
    failed: bool = False
    error: str = ""
    # ── derived at poll time ──
    liveness: Liveness = Liveness.QUEUED
    busy: bool = False
    idle_s: float = 0.0

    @property
    def key(self) -> str:
        """The identity that keeps two simultaneous runs separated."""
        return f"{self.run_id}/{self.unit_id}"


@dataclass(frozen=True)
class DbxPayload:
    """Typed per-adapter payload — native :class:`DbxUnit` models, never a flat dict.

    ``collisions`` records run-ID collisions (two distinct runs claiming one ``run_id``)
    — a data-integrity fault, not a unit state. ``events_seen`` counts every consumed
    record, so a bounded ``units`` tuple next to a large ``events_seen`` is the visible
    proof that retained state is O(units), not O(events).
    """

    units: tuple[DbxUnit, ...] = ()
    collisions: tuple[str, ...] = ()
    events_seen: int = 0
    runs: tuple[str, ...] = ()


# ───────────────────────── liveness (pure functions) ─────────────────────────
def _last_arrival_ts(u: DbxUnit) -> float:
    """The newest REAL arrival across every liveness channel.

    Transcript event, heartbeat, lease *renewal*, and retry are arrivals. Artifact
    growth counts only when the byte count actually GREW — a flat artifact is not
    evidence of progress. Merely *holding* a lease is deliberately excluded: a dead
    process keeps its lease until expiry, so possession would manufacture liveness.
    """
    stamps = [u.last_event_ts, u.heartbeat_ts, u.lease_renewed_ts, u.last_retry_ts]
    if u.artifact_bytes > u.prev_artifact_bytes:
        stamps.append(u.artifact_ts)
    return max(stamps)


def derive_liveness(u: DbxUnit, now: float, th: LivenessThresholds) -> Liveness:
    """Classify one unit into the eight-state vocabulary.

    Silence alone NEVER yields ``STALLED``: a unit with a blocking tool call in flight
    or a known-active remote task short-circuits to ``TOOL_ACTIVE`` /
    ``WAITING_EXTERNAL`` before any timing test runs. That ordering is the invariant —
    collapsing it to a silence test is precisely the defect this guards.
    """
    if u.cancelled or u.failed or u.task_status in _TERMINAL_STATUSES:
        return Liveness.TERMINAL
    if u.started_ts <= 0.0 or u.task_status in _QUEUED_STATUSES:
        return Liveness.QUEUED
    # ── the two hard guards: a known-active call is never silence ──
    if u.tool_active:
        return Liveness.TOOL_ACTIVE
    if u.remote_task_active:
        return Liveness.WAITING_EXTERNAL

    arrival = _last_arrival_ts(u)
    if arrival <= 0.0:
        if (now - u.started_ts) <= th.starting_grace_s:
            return Liveness.STARTING
        # past the grace with zero arrivals — the start itself becomes the clock
        arrival = u.started_ts

    idle = now - arrival
    if idle > th.stalled_s:
        return Liveness.STALLED
    if idle > th.heartbeat_late_s:
        return Liveness.HEARTBEAT_LATE
    return Liveness.THINKING


def is_busy(u: DbxUnit, now: float, th: LivenessThresholds) -> bool:
    """True only when a REAL arrival landed inside ``busy_window_s``.

    Deliberately independent of :func:`derive_liveness`: a unit blocked in a long tool
    call is ``TOOL_ACTIVE`` yet NOT busy, because nothing is arriving. This is the
    anti-decorative-spinner rule — a dead agent must never keep looking busy.
    """
    arrival = _last_arrival_ts(u)
    return arrival > 0.0 and (now - arrival) <= th.busy_window_s


def busy_glyph(u: DbxUnit) -> str:
    """The board glyph — driven by the arrival-derived ``busy`` flag, never a constant."""
    return _GLYPH_BUSY if u.busy else _GLYPH_IDLE


# ───────────────────────── optional sibling modules ─────────────────────────
class _Auto:
    """Sentinel type: 'auto-import the sibling if it exists'.

    Distinct from ``None``, which means 'explicitly DISABLED, use the built-ins'. The
    distinction matters because the siblings are authored by parallel agents: tests pass
    ``None`` to stay hermetic, while production keeps the auto-wiring seam.
    """


_AUTO = _Auto()


def _optional(name: str) -> ModuleType | None:
    """Import a sibling dbx module, or ``None``.

    ``dbx_events`` / ``dbx_completion`` are authored by PARALLEL agents and may not
    exist. They are a pure enhancement seam: absent, the built-in normalizer and
    terminal-classifier below are used, so this adapter's tests pass independently.
    """
    try:
        return importlib.import_module(f".{name}", __package__)
    except Exception:
        return None


def _call_sibling(mod: ModuleType | None, attr: str, *args):
    """Call ``mod.attr(*args)``, returning ``None`` if absent OR if it raises.

    A buggy sibling degrades this adapter to its built-ins; it never blinds a board row
    and never escapes as an ``unreachable`` snapshot.
    """
    if mod is None:
        return None
    fn = getattr(mod, attr, None)
    if fn is None:
        return None
    try:
        return fn(*args)
    except Exception:
        return None


# ───────────────────────── reading (streaming, bounded) ─────────────────────────
def default_events_path() -> str:
    """The default NDJSON event stream (``DBX_MONITOR_EVENTS`` or ``~/.dbxmon``)."""
    env = os.environ.get("DBX_MONITOR_EVENTS")
    if env:
        return env
    return os.path.join(os.path.expanduser("~"), ".dbxmon", "events.jsonl")


def _read_jsonl(path: str) -> Iterator[dict]:
    """Stream records line-by-line — never ``readlines()``, so peak memory is O(line).

    A MISSING file yields nothing (a run that has not written yet is normal, not an
    error). An unreadable / locked path lets ``OSError`` escape to ``poll``, which
    degrades the row to ``unreachable``. A malformed line (a half-written tail record)
    is skipped rather than raising.
    """
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if isinstance(rec, dict):
                yield rec


@dataclass
class _Acc:
    """Mutable per-unit accumulator used during one fold (frozen into a ``DbxUnit``)."""

    unit_id: str
    run_id: str = ""
    touch_ts: float = 0.0
    fields: dict = field(default_factory=dict)


class DatabricksSource:
    """A :class:`~monitorcore.contract.MonitorSource` over a Databricks fan-out."""

    id = _ID

    def __init__(
        self,
        *,
        events_path: str | None = None,
        reader: Callable[[], Iterable[dict]] | None = None,
        exists_fn: Callable[[str], bool] = os.path.exists,
        api: Callable[[], dict[str, str]] | None = None,
        thresholds: LivenessThresholds | None = None,
        max_units: int = 200,
        events_mod: ModuleType | None | _Auto = _AUTO,
        completion_mod: ModuleType | None | _Auto = _AUTO,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._events_path = events_path or default_events_path()
        self._reader = reader or (lambda: _read_jsonl(self._events_path))
        #: Only the DEFAULT file reader lets us ask "was the artifact even there?" — an
        #: injected reader IS the measurement, so its emptiness is a measured zero.
        self._owns_path = reader is None
        self._exists = exists_fn
        self._api = api
        self._th = thresholds or LivenessThresholds()
        self._max_units = max(1, max_units)
        self._events_mod: ModuleType | None = (
            _optional("dbx_events") if isinstance(events_mod, _Auto) else events_mod
        )
        self._completion_mod: ModuleType | None = (
            _optional("dbx_completion")
            if isinstance(completion_mod, _Auto)
            else completion_mod
        )
        self._clock = clock
        self._last: Snapshot[DbxPayload] | None = None
        #: the accumulator from the last SUCCESSFUL poll — bounded by ``max_units``
        self._acc: dict[str, _Acc] = {}

    # ───────────────────────── poll (never throws) ─────────────────────────
    def poll(self) -> Snapshot[DbxPayload]:
        ts = self._clock()
        # An ABSENT event stream is UNMEASURED, not "0 units". ``_read_jsonl`` yields
        # nothing for a missing file, so without this check a never-wired Databricks lane
        # renders byte-identically to a reached-but-empty one: ``[idle] 0 active / 0 done
        # / 0 stalled of 0 units`` plus "no units observed in the event stream" — an
        # unavailable source painted as healthy, and a claim that a stream was observed.
        if self._owns_path and not self._exists(self._events_path):
            return self._unreachable(ts, f"event stream not found: {self._events_path}")
        try:
            acc, collisions, seen = self._fold(self._reader())
            statuses = self._api() if self._api is not None else {}
            units = self._finalize(acc, statuses, ts)
        # NEVER raise out of poll (BaseException still propagates by design).
        except Exception as exc:
            return self._unreachable(ts, str(exc))

        state = self._derive_state(units, collisions)
        payload = DbxPayload(
            units=units,
            collisions=collisions,
            events_seen=seen,
            runs=tuple(sorted({u.run_id for u in units})),
        )
        newest = max((_last_arrival_ts(u) for u in units), default=0.0)
        snap = Snapshot(
            source_id=self.id,
            ts=ts,
            reachable=True,
            stale=False,
            state=state,
            headline=self._headline(payload, state, None),
            payload=payload,
            age_s=(ts - newest) if newest else None,
            error=None,
        )
        self._acc = acc
        self._last = snap
        return snap

    def _unreachable(self, ts: float, error: str) -> Snapshot[DbxPayload]:
        """A stale/unreachable snapshot retaining the last-good payload (never a fake zero).

        Shared by the two ways a poll can fail to MEASURE anything: a reader that raised,
        and an event stream that is not on disk at all. Both must be distinguishable from a
        stream that was read and legitimately held nothing.
        """
        payload = self._last.payload if self._last is not None else DbxPayload()
        return Snapshot(
            source_id=self.id,
            ts=ts,
            reachable=False,
            stale=True,
            state=SourceState.UNREACHABLE,
            headline=self._headline(None, SourceState.UNREACHABLE, error),
            payload=payload,
            age_s=None,
            error=error,
        )

    # ───────────────────────── the fold (stateless per poll) ─────────────────────────
    def _fold(
        self, records: Iterable[dict]
    ) -> tuple[dict[str, _Acc], tuple[str, ...], int]:
        """Replay the whole stream into bounded per-unit state.

        Rebuilt FROM SCRATCH every poll, so a restarted monitor replays to the same
        final state as one that watched the run live (and counters like ``retries``
        cannot double-count across polls). Retained state is capped at ``max_units``
        DURING the fold — evicting the least-recently-active — so a slow consumer
        facing a huge stream still holds O(max_units), not O(events).
        """
        acc: dict[str, _Acc] = {}
        tokens: dict[str, str] = {}
        collisions: list[str] = []
        seen = 0

        for raw in records:
            seen += 1
            rec = self._normalize(raw)
            unit_id = str(rec.get("unit_id") or "")
            if not unit_id:
                continue
            run_id = str(rec.get("run_id") or "")
            key = f"{run_id}/{unit_id}"
            entry = acc.get(key)
            if entry is None:
                entry = _Acc(unit_id=unit_id, run_id=run_id)
                acc[key] = entry
            ts = float(rec.get("ts") or 0.0)
            entry.touch_ts = max(entry.touch_ts, ts)

            self._collide(rec, run_id, tokens, collisions)
            self._apply(entry, rec, ts)

            if len(acc) > self._max_units:
                self._evict(acc)

        return acc, tuple(collisions), seen

    def _normalize(self, rec: dict) -> dict:
        """Hand the record to the optional ``dbx_events`` sibling, else pass it through."""
        out = _call_sibling(self._events_mod, "normalize", rec)
        return out if isinstance(out, dict) else rec

    @staticmethod
    def _collide(
        rec: dict, run_id: str, tokens: dict[str, str], collisions: list[str]
    ) -> None:
        """Detect two distinct runs claiming ONE ``run_id`` via their attempt tokens."""
        if rec.get("kind") != "start":
            return
        token = str(rec.get("attempt_token") or "")
        if not token:
            return  # nothing to discriminate on — cannot claim a collision
        prior = tokens.get(run_id)
        if prior is not None and prior != token:
            msg = f"run-id collision on {run_id!r}: token {prior!r} vs {token!r}"
            if msg not in collisions:
                collisions.append(msg)
            return
        tokens[run_id] = token

    def _apply(self, entry: _Acc, rec: dict, ts: float) -> None:
        """Fold ONE record into the unit's accumulator.

        Only the kinds below are read — an unknown field on a record (a ``cpu_seconds``,
        say) is structurally ignored, which is how the no-cumulative-CPU rule is
        enforced by construction rather than by convention.
        """
        f = entry.fields
        kind = str(rec.get("kind") or "")

        if _call_sibling(self._completion_mod, "is_terminal", rec) is True:
            f["task_status"] = str(rec.get("status") or "TERMINATED")
            f["last_event_ts"] = ts
            return

        if kind == "queued":
            f["task_status"] = "PENDING"
        elif kind == "start":
            f["started_ts"] = ts
            f["task_status"] = "RUNNING"
        elif kind == "heartbeat":
            f["heartbeat_ts"] = ts
        elif kind == "event":
            f["last_event_ts"] = ts
        elif kind == "tool_start":
            f["tool_active"] = True
            f["tool_name"] = str(rec.get("tool") or "")
            f["last_event_ts"] = ts
        elif kind == "tool_end":
            f["tool_active"] = False
            f["last_event_ts"] = ts
        elif kind == "remote_task_start":
            f["remote_task_active"] = True
            f["remote_task_id"] = str(rec.get("task_id") or "")
            f["last_event_ts"] = ts
        elif kind == "remote_task_end":
            f["remote_task_active"] = False
            f["last_event_ts"] = ts
        elif kind == "lease_renew":
            f["lease_held"] = True
            f["lease_renewed_ts"] = ts
        elif kind == "lease_release":
            f["lease_held"] = False
        elif kind == "retry":
            # a retry is real forward motion by the harness AND clears the in-flight
            # call state the previous attempt died holding
            f["retries"] = int(f.get("retries", 0)) + 1
            f["last_retry_ts"] = ts
            f["tool_active"] = False
            f["remote_task_active"] = False
        elif kind == "artifact":
            f["prev_artifact_bytes"] = int(f.get("artifact_bytes", 0))
            f["artifact_bytes"] = int(rec.get("bytes") or 0)
            f["artifact_ts"] = ts
        elif kind == "cancel":
            f["cancelled"] = True
            f["task_status"] = "CANCELED"
        elif kind == "done":
            f["task_status"] = str(rec.get("status") or "TERMINATED")
        elif kind == "error":
            f["failed"] = True
            f["task_status"] = "FAILED"
            f["error"] = str(rec.get("message") or "")

    def _evict(self, acc: dict[str, _Acc]) -> None:
        """Drop the least-recently-active units back down to ``max_units``."""
        ordered = sorted(acc.items(), key=lambda kv: (kv[1].touch_ts, kv[0]))
        for key, _ in ordered[: len(acc) - self._max_units]:
            del acc[key]

    def _finalize(
        self, acc: dict[str, _Acc], statuses: dict[str, str], now: float
    ) -> tuple[DbxUnit, ...]:
        """Freeze accumulators into units and derive liveness / busy / idle."""
        out: list[DbxUnit] = []
        for key in sorted(acc):
            entry = acc[key]
            unit = DbxUnit(unit_id=entry.unit_id, run_id=entry.run_id, **entry.fields)
            # the injected lifecycle probe is authoritative over the event stream
            probed = statuses.get(key)
            if probed:
                unit = replace(unit, task_status=str(probed))
            arrival = _last_arrival_ts(unit)
            out.append(
                replace(
                    unit,
                    liveness=derive_liveness(unit, now, self._th),
                    busy=is_busy(unit, now, self._th),
                    idle_s=(now - arrival) if arrival > 0.0 else 0.0,
                )
            )
        return tuple(out)

    # ───────────────────────── coarse-state derivation ─────────────────────────
    @staticmethod
    def _derive_state(
        units: tuple[DbxUnit, ...], collisions: tuple[str, ...]
    ) -> SourceState:
        """Collapse unit liveness into the coarse ROW state — NO new constant is added.

        A run-ID collision or any failed unit is ``error``; a stalled unit outranks a
        healthy sibling (it is the actionable row); any active unit is ``running``; all
        terminal is ``done``; otherwise ``idle`` (empty, or only queued units).
        """
        if collisions:
            return SourceState.ERROR
        if not units:
            return SourceState.IDLE
        if any(u.failed for u in units):
            return SourceState.ERROR
        seen = {u.liveness for u in units}
        if Liveness.STALLED in seen:
            return SourceState.STALLED
        if seen & _ACTIVE:
            return SourceState.RUNNING
        if seen == {Liveness.TERMINAL}:
            return SourceState.DONE
        return SourceState.IDLE

    def _headline(
        self, payload: DbxPayload | None, state: SourceState, error: str | None
    ) -> str:
        """A redaction-safe one-liner (``unreachable`` on a failed poll)."""
        if payload is None:
            return _redact(f"unreachable: {error}")
        units = payload.units
        active = sum(1 for u in units if u.liveness in _ACTIVE)
        done = sum(1 for u in units if u.liveness is Liveness.TERMINAL)
        stalled = sum(1 for u in units if u.liveness is Liveness.STALLED)
        line = (
            f"dbx [{state}] {active} active / {done} done / "
            f"{stalled} stalled of {len(units)} units"
        )
        retries = sum(u.retries for u in units)
        if retries:
            line += f" · {retries} retries"
        cancelled = sum(1 for u in units if u.cancelled)
        if cancelled:
            line += f" · {cancelled} cancelled"
        if payload.collisions:
            line += f" · {len(payload.collisions)} run-id collision(s)"
        return _redact(line)

    # ───────────────────────── contract surface ─────────────────────────
    def render_native(self, snap: Snapshot[DbxPayload]) -> object:
        """The dbx-native board (falls back to the headline with no units)."""
        units = snap.payload.units
        if not units:
            return snap.headline
        return "\n".join(
            _redact(
                f"{busy_glyph(u)} {u.key} {u.liveness} "
                f"idle={u.idle_s:.0f}s retries={u.retries}"
            )
            for u in units
        )

    def export_model(self, snap: Snapshot[DbxPayload]) -> ReportDoc:
        """Map the snapshot onto the shared ``ReportDoc`` (one card per unit)."""
        units = snap.payload.units
        generated = datetime.fromtimestamp(snap.ts, tz=timezone.utc).isoformat()
        rollup = (
            ("total", len(units)),
            ("done", sum(1 for u in units if u.liveness is Liveness.TERMINAL)),
            ("error", sum(1 for u in units if u.failed)),
            ("running", sum(1 for u in units if u.liveness in _ACTIVE)),
            ("idle", sum(1 for u in units if u.liveness is Liveness.QUEUED)),
            # renderer-canonical key; the dbx domain has no token accounting at Inc-1
            ("tokens", 0),
            ("stalled", sum(1 for u in units if u.liveness is Liveness.STALLED)),
        )
        blocks = tuple(
            Section(
                title=u.key,
                anchor=f"dbx-{i}",
                index=i,
                card=True,
                badge=str(u.liveness),
                lead=(
                    f"{u.task_status} · idle={u.idle_s:.0f}s · "
                    f"retries={u.retries} · busy={u.busy}"
                ),
                task=u.tool_name or u.remote_task_id,
                output=u.error,
            )
            for i, u in enumerate(units)
        )
        return ReportDoc(
            title="dbxmon",
            generated_at=generated,
            blocks=blocks,
            subtitle=snap.headline,
            meta=(("source", self.id), ("units", str(len(units)))),
            rollup=rollup,
            active=snap.state == SourceState.RUNNING,
            redaction_mode="strict",
        )

    def headline(self, snap: Snapshot[DbxPayload]) -> str:
        """The redaction-safe one-liner (computed at poll time)."""
        return snap.headline

    def alert(self, snap: Snapshot[DbxPayload]) -> Alert | None:
        """Classify a snapshot into a redaction-safe ``Alert`` — SIGNATURE ONLY.

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


def _redact(text: str) -> str:
    """The shared ingest floor — control bytes stripped FIRST, then secrets masked.

    Delegates to :func:`monitorcore.redact.scrub` rather than calling ``redact`` directly.
    The local copy this replaces omitted ``strip_controls``, so a control-laden Databricks
    error string could both split a secret pattern past the mask and carry an escape byte
    into a painted headline — a silent drift from the floor every sibling adapter applies.
    """
    return scrub(text)
