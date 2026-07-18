"""wfmon_export.source — the ``WfmonSource`` adapter behind the generic monitorcore contract.

``WfmonSource`` wraps the wfmon manifest readers (``collect_run`` → ``ExportModel``) as a
:class:`~monitorcore.contract.MonitorSource`: it ``poll()`` s ONE workflow run into a
:class:`~monitorcore.contract.Snapshot` whose typed :class:`WfmonPayload` carries the
fully-materialized native ``ExportModel`` and its ``AgentExport`` list — **never flattened to a
dict** (E-1's cardinal guardrail). ``export_model`` re-uses wfmon's ``ExportModel → ReportDoc``
mapper so the run renders through the shared exporters to byte-identical output, and
``render_native`` keeps a compact wfmon-native board line.

The contract's cardinal rule is honoured: ``poll`` wraps the reader in ``except Exception`` and,
on any failure, returns a stale / unreachable snapshot (its last-good payload if it has one, the
exception text in ``error``) WITHOUT raising — a broken manifest degrades one board row instead
of tearing the board down. ``BaseException`` (Ctrl-C / SystemExit) is deliberately not caught.

``alert`` is **signature-only** here (PR-B): it classifies a snapshot into a redaction-safe
:class:`~monitorcore.contract.Alert` or ``None``; the delivery rail is PR-G.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from monitorcore.contract import Alert, Snapshot, SourceState
from monitorcore.redact import redact
from monitorcore.report_doc import ReportDoc
from workflow_run import DEFAULT_PROJECTS

from .model import AgentExport, ExportModel, collect_run, export_model

_ID = "wfmon"

# The reader ``poll`` drives: ``wf_id`` positional + the ``collect_run`` keyword surface. Injected
# in tests to raise / return a crafted model without touching the filesystem.
Reader = Callable[..., ExportModel]


@dataclass(frozen=True)
class WfmonPayload:
    """Typed per-adapter payload — the native run model + its typed agents; NEVER flattened.

    ``model`` is ``None`` only before the first successful poll (an unreachable snapshot with no
    retained last-good value); ``agents`` is the flattened-but-typed ``AgentExport`` list across
    all phases, for board consumers that want per-agent detail without re-walking ``phases``.
    """

    model: ExportModel | None = None
    agents: tuple[AgentExport, ...] = ()


def _redact(text: str) -> str:
    """Mask secrets / collapse home paths, returning just the scrubbed text (fail-closed floor)."""
    return redact(text, enabled=True)[0]


class WfmonSource:
    """A :class:`~monitorcore.contract.MonitorSource` over one Claude Code workflow run."""

    id = _ID

    def __init__(
        self,
        wf_id: str,
        *,
        projects: str = DEFAULT_PROJECTS,
        scope: str = "run",
        agents: list[str] | None = None,
        generated_at: str | None = None,
        reader: Reader = collect_run,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._wf_id = wf_id
        self._projects = projects
        self._scope = scope
        self._agents = agents
        self._generated_at = generated_at
        self._reader = reader
        self._clock = clock
        self._last: Snapshot[WfmonPayload] | None = None

    # ───────────────────────── poll (never throws) ─────────────────────────
    def poll(self) -> Snapshot[WfmonPayload]:
        ts = self._clock()
        try:
            model = self._reader(
                self._wf_id,
                projects=self._projects,
                scope=self._scope,
                agents=self._agents,
                generated_at=self._generated_at,
            )
        # NEVER raise out of poll (BaseException still propagates by design).
        except Exception as exc:
            payload = self._last.payload if self._last is not None else WfmonPayload()
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
        agents = tuple(a for phase in model.phases for a in phase.agents)
        state = self._derive_state(model)
        snap = Snapshot(
            source_id=self.id,
            ts=ts,
            reachable=True,
            stale=False,
            state=state,
            headline=self._headline(model, state, None),
            payload=WfmonPayload(model=model, agents=agents),
            age_s=None,
            error=None,
        )
        self._last = snap
        return snap

    # ───────────────────────── coarse-state derivation ─────────────────────────
    @staticmethod
    def _derive_state(model: ExportModel) -> SourceState:
        """Collapse a run's rollup into the coarse cross-domain state.

        ``error`` if any agent errored; else ``running`` while the run is active with work in
        flight; else ``done`` once the run is terminal; else ``idle`` (active but nothing
        running yet). ``stalled`` freeze detection is the agent watchdog adapter's job (PR-B2).
        """
        rollup = model.rollup
        if rollup.get("error", 0) > 0:
            return SourceState.ERROR
        if model.active and rollup.get("running", 0) > 0:
            return SourceState.RUNNING
        if not model.active:
            return SourceState.DONE
        return SourceState.IDLE

    def _headline(
        self, model: ExportModel | None, state: SourceState, error: str | None
    ) -> str:
        """A redaction-safe one-line status (``unreachable`` on a failed poll)."""
        if model is None:
            return _redact(f"unreachable: {error}")
        rollup = model.rollup
        return _redact(
            f"{model.name} [{state}] "
            f"{rollup.get('done', 0)} done / {rollup.get('error', 0)} error / "
            f"{rollup.get('running', 0)} running of {rollup.get('total', 0)}"
        )

    # ───────────────────────── contract surface ─────────────────────────
    def render_native(self, snap: Snapshot[WfmonPayload]) -> object:
        """A compact wfmon-native board line (falls back to the headline with no model)."""
        model = snap.payload.model
        if model is None:
            return snap.headline
        rollup = model.rollup
        return (
            f"{model.name} [{snap.state}] "
            f"{rollup.get('done', 0)}✓ {rollup.get('error', 0)}✗ "
            f"{rollup.get('running', 0)}◔ /{rollup.get('total', 0)}"
        )

    def export_model(self, snap: Snapshot[WfmonPayload]) -> ReportDoc:
        """Map the snapshot's native model onto the generic ``ReportDoc`` the shared renderers
        consume; a minimal doc (never raising) when the snapshot has no model."""
        model = snap.payload.model
        if model is None:
            return ReportDoc(title=_ID, generated_at="", subtitle=snap.headline)
        return export_model(model)

    def headline(self, snap: Snapshot[WfmonPayload]) -> str:
        """The redaction-safe one-liner (computed at poll time)."""
        return snap.headline

    def alert(self, snap: Snapshot[WfmonPayload]) -> Alert | None:
        """Classify a snapshot into a redaction-safe :class:`Alert` — SIGNATURE ONLY (no rail).

        ``error`` → ``critical``; ``unreachable`` / ``stalled`` → ``warn``; healthy states →
        ``None``. Delivery (ntfy / toast / dead-man) is PR-G.
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
