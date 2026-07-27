"""``agents_source`` — a :class:`~monitorcore.contract.MonitorSource` over the EXISTING scan.

This adapter adds **zero** new discovery: every row comes from
:func:`monitorcore.discovery.scan`, the module that already walks
``~/.claude/projects/<project>/<session>/subagents/**/agent-*.jsonl`` (flat Task agents AND
the nested ``subagents/workflows/<wf>/`` ones) and summarises each transcript with one cheap
tail read. The adapter's whole job is to (a) SCRUB each row, (b) collapse it into a display
bucket with the existing pure :func:`monitorcore.agent_state.bucket_agent`, and (c) wrap the
result in the typed ``Snapshot``/``poll`` contract so the unified board can drive it — which
is what feeds BOTH the ``agents`` pane and the ``workflows`` pane (one poll, two projections).

Two deliberate honesty limits, stated here so no reader infers more than is measured:

* The bucket is derived from signals ``discovery`` already produced — the ``running`` mtime
  flag and an errored tail (``last_event_summary`` prefixes a failed ``tool_result`` with
  ``✗``). It is NOT the terminal-evidence classifier: :func:`monitorcore.agent_state
  .agent_status` re-reads every transcript tail to distinguish ``done`` from ``stalled``, and
  running it per row would double the I/O the scan just did. So this source reports
  ``running`` / ``idle`` / ``error`` and never claims ``done``.
* A row's workflow id is the one ``discovery`` derives from the PATH (``""`` for a flat Task
  agent). This source does not read a workflow manifest — that is the ``wf_fleet`` port, a
  separate unit — so the ``workflows`` pane groups the agents a workflow OWNS, and does not
  claim to enumerate workflows that have not spawned an agent yet.

``poll`` never raises (the contract's cardinal rule): a scan failure returns an unreachable /
stale snapshot carrying the last-good payload. Stdlib-only, so it vendors cleanly.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from .agent_state import bucket_agent
from .contract import Alert, Snapshot, SourceState
from .discovery import PROJECTS, pick_active_dir, scan
from .redact import redact
from .report_doc import ReportDoc, Section
from .textsafe import strip_controls

__all__ = [
    "AgentRow",
    "AgentsPayload",
    "AgentsSource",
    "ERROR_GLYPH",
    "row_from_scan",
    "workflow_key",
]

_ID = "agents"

#: ``discovery.last_event_summary`` marks a failed ``tool_result`` with this prefix.
ERROR_GLYPH = "✗"

#: The bucket a row with no workflow id lands in on the ``workflows`` pane.
UNGROUPED_WF = "(no workflow)"


def _scrub(value: object) -> str:
    """Strip control bytes, THEN mask secrets / collapse home paths (fail-closed).

    The order matters and matches :func:`monitorcore.codex_tail._scrub`: control bytes are
    removed FIRST so a spliced ESC cannot split a secret pattern and evade the mask.
    """
    text = "" if value is None else str(value)
    return redact(strip_controls(text), enabled=True)[0]


@dataclass(frozen=True)
class AgentRow:
    """One scrubbed subagent transcript, ready to render. Every string is redaction-safe."""

    name: str
    agent_type: str
    desc: str
    wf: str
    bucket: str
    age_s: float
    running: bool
    size: int
    last: str
    path: str


@dataclass(frozen=True)
class AgentsPayload:
    """Typed per-adapter payload — the scrubbed rows plus the directory they came from.

    ``root`` is ``""`` when no subagents directory was found at all; that is an UNMEASURED
    state (rendered as such), not "zero agents".
    """

    rows: tuple[AgentRow, ...] = ()
    root: str = ""


def workflow_key(row: AgentRow) -> str:
    """The workflow bucket a row belongs to (``UNGROUPED_WF`` for a flat Task agent)."""
    return row.wf or UNGROUPED_WF


def row_from_scan(raw: dict[str, object]) -> AgentRow:
    """Fold one :func:`monitorcore.discovery.scan` dict into a scrubbed :class:`AgentRow`.

    Pure: every untrusted field passes :func:`_scrub` at ingest, and the coarse bucket comes
    from the existing pure :func:`monitorcore.agent_state.bucket_agent` (no new policy here).
    """
    last = _scrub(raw.get("last"))
    running = bool(raw.get("running"))
    bucket = bucket_agent(
        errored=last.startswith(ERROR_GLYPH), state=None, running=running
    )
    age = raw.get("age")
    size = raw.get("size")
    return AgentRow(
        name=_scrub(raw.get("name")),
        agent_type=_scrub(raw.get("type")),
        desc=_scrub(raw.get("desc")),
        wf=_scrub(raw.get("wf")),
        bucket=bucket,
        age_s=float(age) if isinstance(age, (int, float)) else 0.0,
        running=running,
        size=int(size) if isinstance(size, int) else 0,
        last=last,
        path=_scrub(raw.get("jsonl")),
    )


class AgentsSource:
    """A :class:`~monitorcore.contract.MonitorSource` over the Claude subagent transcripts."""

    id = _ID

    def __init__(
        self,
        *,
        subdir: str | None = None,
        projects: str = PROJECTS,
        active_secs: float = 45.0,
        width: int = 200,
        scan_fn: Callable[..., list[dict[str, object]]] = scan,
        pick_fn: Callable[[str], str | None] = pick_active_dir,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._subdir = subdir
        self._projects = projects
        self._active_secs = active_secs
        self._width = width
        self._scan = scan_fn
        self._pick = pick_fn
        self._clock = clock
        self._last: Snapshot[AgentsPayload] | None = None

    # ───────────────────────── poll (never throws) ─────────────────────────
    def poll(self) -> Snapshot[AgentsPayload]:
        ts = self._clock()
        try:
            root = (
                self._subdir if self._subdir is not None else self._pick(self._projects)
            )
            if root is None:
                return self._unreachable(ts, "no subagent transcripts found")
            raw = self._scan(root, self._active_secs, self._width, now=ts)
            rows = tuple(row_from_scan(item) for item in raw)
        # NEVER raise out of poll (BaseException still propagates by design).
        except Exception as exc:
            return self._unreachable(ts, str(exc))

        payload = AgentsPayload(rows=rows, root=_scrub(root))
        state = _derive_state(rows)
        newest = min((r.age_s for r in rows), default=None)
        snap = Snapshot(
            source_id=self.id,
            ts=ts,
            reachable=True,
            stale=False,
            state=state,
            headline=_headline(payload, state),
            payload=payload,
            age_s=newest,
            error=None,
        )
        self._last = snap
        return snap

    def _unreachable(self, ts: float, error: str) -> Snapshot[AgentsPayload]:
        """A stale/unreachable snapshot retaining the last-good payload (never a fake zero)."""
        payload = self._last.payload if self._last is not None else AgentsPayload()
        text = _scrub(error)
        snap = Snapshot(
            source_id=self.id,
            ts=ts,
            reachable=False,
            stale=True,
            state=SourceState.UNREACHABLE,
            headline=f"agents [unreachable] {text}",
            payload=payload,
            age_s=None,
            error=text,
        )
        self._last = snap
        return snap

    # ───────────────────────── contract surface ─────────────────────────
    def render_native(self, snap: Snapshot[AgentsPayload]) -> object:
        """The agents-native lines (falls back to the headline when nothing was scanned)."""
        rows = snap.payload.rows
        if not rows:
            return snap.headline
        return "\n".join(f"{r.bucket} {r.name} {r.last}" for r in rows)

    def export_model(self, snap: Snapshot[AgentsPayload]) -> ReportDoc:
        """Map the snapshot onto the shared ``ReportDoc`` (one card per subagent).

        ``generated_at`` derives from the snapshot's own poll epoch, so identical snapshots
        export byte-identically through the generic renderers.
        """
        rows = snap.payload.rows
        generated = datetime.fromtimestamp(snap.ts, tz=timezone.utc).isoformat()
        counts = _counts(rows)
        blocks = tuple(
            Section(
                title=r.name,
                anchor=f"agent-{i}",
                index=i,
                card=True,
                badge=r.bucket,
                lead=f"{r.agent_type} · {r.wf or UNGROUPED_WF} · {r.age_s:.0f}s",
                task=r.desc,
                output=r.last,
            )
            for i, r in enumerate(rows)
        )
        return ReportDoc(
            title="agents",
            generated_at=generated,
            blocks=blocks,
            subtitle=snap.headline,
            meta=(("source", self.id), ("root", snap.payload.root)),
            rollup=(
                ("total", len(rows)),
                ("running", counts["running"]),
                ("error", counts["error"]),
                ("idle", counts["idle"]),
            ),
            active=snap.state == SourceState.RUNNING,
            redaction_mode="strict",
        )

    def headline(self, snap: Snapshot[AgentsPayload]) -> str:
        """The redaction-safe one-liner (computed at poll time)."""
        return snap.headline

    def alert(self, snap: Snapshot[AgentsPayload]) -> Alert | None:
        """``error`` → critical, ``unreachable`` / ``stalled`` → warn, else ``None``."""
        if snap.state in (
            SourceState.ERROR,
            SourceState.UNREACHABLE,
            SourceState.STALLED,
        ):
            level = "critical" if snap.state == SourceState.ERROR else "warn"
            return Alert(
                source_id=snap.source_id,
                level=level,
                headline=_scrub(snap.headline),
                detail=_scrub(snap.error or ""),
                ts=snap.ts,
            )
        return None


def _counts(rows: Sequence[AgentRow]) -> dict[str, int]:
    """Per-bucket tallies (always carries every key, so a renderer never KeyErrors)."""
    out = {"running": 0, "idle": 0, "error": 0}
    for row in rows:
        out[row.bucket] = out.get(row.bucket, 0) + 1
    return out


def _derive_state(rows: Iterable[AgentRow]) -> SourceState:
    """Collapse the buckets into the coarse cross-domain state."""
    buckets = {row.bucket for row in rows}
    if "error" in buckets:
        return SourceState.ERROR
    if "running" in buckets:
        return SourceState.RUNNING
    return SourceState.IDLE


def _headline(payload: AgentsPayload, state: SourceState) -> str:
    """``agents [running] 3 running / 1 error of 9 in 2 workflows`` — already scrubbed."""
    rows = payload.rows
    counts = _counts(rows)
    workflows = {workflow_key(r) for r in rows}
    return (
        f"agents [{state}] {counts['running']} running / {counts['error']} error "
        f"of {len(rows)} in {len(workflows)} workflows"
    )
