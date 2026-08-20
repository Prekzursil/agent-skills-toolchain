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
  :data:`monitorcore.discovery.ERROR_GLYPH`). It is NOT the terminal-evidence classifier:
  :func:`monitorcore.agent_state.agent_status` re-reads every transcript tail to distinguish
  ``done`` from ``stalled``, and running it per row would double the I/O the scan just did.
  So this source passes ``journal_state=None`` to :func:`~monitorcore.agent_state
  .bucket_agent` and therefore reports ``running`` / ``idle`` / ``error`` and NEVER ``done``.
  Consequence, stated so the panes can be honest about it: a finished workflow and a hung
  one both come back with zero running agents. The per-workflow journal read that WOULD
  separate them (one ``journal.jsonl`` per workflow, not one per agent — see
  ``.agents/skills/workflow-monitor/workflow_run.py``'s ``journal_states``, which feeds
  ``wfmon_export/model.py``'s ``_rollup``) is a port this package does not carry, so the
  ``workflows`` pane prints ``done=not-measured`` instead of a fabricated ``0 done``.
* A root directory that does not EXIST is unreachable, not empty. ``scan`` over a missing
  path returns ``[]``, which would otherwise render byte-identically to a real but idle
  directory — an unavailable source painted as healthy.
* A row's workflow id is the one ``discovery`` derives from the PATH (``""`` for a flat Task
  agent). This source does not read a workflow manifest — that is the ``wf_fleet`` port, a
  separate unit — so the ``workflows`` pane groups the agents a workflow OWNS, and does not
  claim to enumerate workflows that have not spawned an agent yet.

``poll`` never raises (the contract's cardinal rule): a scan failure returns an unreachable /
stale snapshot carrying the last-good payload. Stdlib-only, so it vendors cleanly.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from .agent_state import FRESH, bucket_agent
from .contract import Alert, Snapshot, SourceState
from .discovery import ERROR_GLYPH, PROJECTS, pick_active_dir, scan
from .redact import scrub
from .report_doc import ReportDoc, Section

__all__ = [
    "AgentRow",
    "AgentsPayload",
    "AgentsSource",
    "row_from_scan",
    "workflow_key",
]

_ID = "agents"

#: The bucket a row with no workflow id lands in on the ``workflows`` pane.
UNGROUPED_WF = "(no workflow)"


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

    Pure: every untrusted field passes the shared :func:`monitorcore.redact.scrub` ingest
    floor, and the coarse bucket comes from the existing pure
    :func:`monitorcore.agent_state.bucket_agent` (no new policy here).
    """
    last = scrub(raw.get("last"))
    running = bool(raw.get("running"))
    bucket = bucket_agent(
        errored=last.startswith(ERROR_GLYPH), state=None, running=running
    )
    age = raw.get("age")
    size = raw.get("size")
    return AgentRow(
        name=scrub(raw.get("name")),
        agent_type=scrub(raw.get("type")),
        desc=scrub(raw.get("desc")),
        wf=scrub(raw.get("wf")),
        bucket=bucket,
        age_s=float(age) if isinstance(age, (int, float)) else 0.0,
        running=running,
        size=int(size) if isinstance(size, int) else 0,
        last=last,
        path=scrub(raw.get("jsonl")),
    )


class AgentsSource:
    """A :class:`~monitorcore.contract.MonitorSource` over the Claude subagent transcripts."""

    id = _ID

    def __init__(
        self,
        *,
        subdir: str | None = None,
        projects: str = PROJECTS,
        active_secs: float = FRESH,
        width: int = 200,
        scan_fn: Callable[..., list[dict[str, object]]] = scan,
        pick_fn: Callable[[str], str | None] = pick_active_dir,
        exists_fn: Callable[[str], bool] = os.path.isdir,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._subdir = subdir
        self._projects = projects
        self._active_secs = active_secs
        self._width = width
        self._scan = scan_fn
        self._pick = pick_fn
        self._exists = exists_fn
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
            # A root that does not exist is UNMEASURED, not "zero agents": ``scan`` walks
            # nothing and returns ``[]``, which renders byte-identically to a real but
            # empty directory. The case that bites is an EXPLICIT ``--subagents-dir`` typo
            # (``pick_active_dir`` can only hand back a directory it just found).
            if not self._exists(root):
                return self._unreachable(ts, f"subagents dir not found: {scrub(root)}")
            raw = self._scan(root, self._active_secs, self._width, now=ts)
            rows = tuple(row_from_scan(item) for item in raw)
        # NEVER raise out of poll (BaseException still propagates by design).
        except Exception as exc:
            return self._unreachable(ts, str(exc))

        payload = AgentsPayload(rows=rows, root=scrub(root))
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
        text = scrub(error)
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
            # EMPTY on purpose. The shared rollup line is agent-manifest-shaped
            # (``total/done/error/running/idle/tokens``) and this source measures neither
            # ``done`` (see the honesty limits above) nor ``tokens``; emitting them as
            # ``0`` would fabricate two zeros, and omitting only those two KeyErrors both
            # renderers. Both skip the line when ``rollup`` is empty, and the honest counts
            # ride in ``subtitle`` (the headline) and on each card's ``badge``.
            rollup=(),
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
                headline=scrub(snap.headline),
                detail=scrub(snap.error or ""),
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


def _root_label(root: str) -> str:
    """The last two path components of the (already scrubbed) root, or ``not-measured``.

    The headline must name WHICH population it counts: ``poll`` re-runs
    :func:`~monitorcore.discovery.pick_active_dir` every frame, so with two live sessions
    the picked root can flip between polls — and a board that prints only the tallies
    switches populations silently (measured: ``8 running of 1335`` one frame, ``3 running
    of 1523`` the next, both true, of DIFFERENT directories). The tail components are the
    part worth the width: every auto-picked root shares the ``~/.claude/projects/...``
    prefix and differs only in ``<session>/subagents``, so a clipped badge still shows the
    distinguishing bytes where the full path would clip down to the constant prefix.
    ``not-measured`` (never ``""``) when the payload carries no root at all.
    """
    norm = root.replace("\\", "/").rstrip("/")
    if not norm:
        return "not-measured"
    return "/".join(norm.split("/")[-2:])


def _headline(payload: AgentsPayload, state: SourceState) -> str:
    """``agents [running] 3 running / 1 error of 9 in 2 workflows · root=<sess>/subagents``.

    Already scrubbed — and it NAMES the root (via :func:`_root_label`), because the counts
    alone cannot show that the auto-picked population changed between frames.
    """
    rows = payload.rows
    counts = _counts(rows)
    workflows = {workflow_key(r) for r in rows}
    return (
        f"agents [{state}] {counts['running']} running / {counts['error']} error "
        f"of {len(rows)} in {len(workflows)} workflows · root={_root_label(payload.root)}"
    )
