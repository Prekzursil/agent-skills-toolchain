"""wfmon_export.model - the ONLY filesystem reader in the export path.

``collect_run`` locates a workflow manifest, drills each scoped agent's transcript + journal
through the shared ``workflow_run`` parser, and returns a fully-materialized ``ExportModel``
(no open file handles, no lazy readers) so every renderer downstream is a PURE function of the
model. Stdlib-only at import time; NEVER imports ``workflow_monitor`` (the state-bucket mapping
is reimplemented locally so this stays a headless, dependency-light reader).
"""

from __future__ import annotations

import datetime
import difflib
import os
from dataclasses import dataclass, field

import workflow_run as wr
from workflow_run import TimelineEvent


# ───────────────────────── data model ─────────────────────────
@dataclass
class AgentExport:
    """One scoped agent, drilled from its manifest row + transcript + journal."""

    agent_id: str
    label: str
    index: int
    phase_index: int
    phase_title: str
    model: str
    state: str  # bucket ∈ {running, done, error, idle} (see _state_bucket)
    tokens: int
    tool_calls: int
    duration_ms: int
    attempt: int
    task: str  # spawn prompt (agent_task = FIRST user text)
    output: str  # clean output (journal result, else last assistant msg)
    headline: str  # report_headline(output)
    timeline: list[TimelineEvent] = field(default_factory=list)
    jsonl_path: str = ""


@dataclass
class PhaseExport:
    """A workflow phase and its agents (manifest index order within the phase)."""

    index: int
    title: str
    agents: list[AgentExport] = field(default_factory=list)


@dataclass
class ExportModel:
    """A fully-materialized snapshot of one run, scoped + ready for pure rendering."""

    wf_id: str
    name: str
    status: str
    active: bool
    generated_at: str
    schema_version: str
    scope: str  # 'run' | 'subset' | 'agent'
    scope_agents: list[str]  # requested labels (empty for scope='run')
    redaction_mode: str  # 'strict' | 'off'
    phases: list[PhaseExport]
    rollup: dict  # {running, done, error, idle, total, tokens} over SCOPED agents
    session: str
    manifest_path: str
    provenance: dict  # {wf_id, name, session, scope, redaction_mode, generated_at, schema_version}


# ───────────────────────── local state bucket (NO workflow_monitor import) ─────────────────────────
def _state_bucket(agent: wr.WFAgent, journal_state: str | None) -> str:
    """Collapse a manifest row + journal state into a display bucket.

    ``error`` if the manifest marks the agent errored; else ``done`` if the journal recorded a
    ``result`` OR the manifest state is ``done``; else ``running`` if the agent is in a running
    state; else ``idle``. (``journal_states`` only ever yields ``started``/``result`` and cannot
    express error - error is authoritative from the manifest's ``WFAgent.errored``.)
    """
    if agent.errored:
        return "error"
    if journal_state == "result" or agent.state == "done":
        return "done"
    if agent.running:
        return "running"
    return "idle"


# ───────────────────────── manifest discovery ─────────────────────────
def _find_run(wf_id: str, projects: str) -> wr.WFRun:
    """Locate the manifest whose parsed ``wf_id`` matches; LookupError (with near-matches) if absent."""
    known: list[str] = []
    for path in wr.iter_manifest_paths(projects):
        run = wr.parse_manifest(path)
        if run is None:
            continue
        if run.wf_id == wf_id:
            return run
        known.append(run.wf_id)
    near = difflib.get_close_matches(wf_id, known, n=5)
    raise LookupError(f"workflow {wf_id!r} not found; closest: {near or known}")


# ───────────────────────── per-agent drill-down ─────────────────────────
def _agent_export(
    agent: wr.WFAgent, wf_dir: str, journal_state: str | None
) -> AgentExport:
    # transcript filename is agent-<agentId>.jsonl and agentId ALREADY carries the 'agent-' prefix
    jsonl_path = os.path.join(wf_dir, agent.agent_id + ".jsonl")
    output = wr.agent_output(jsonl_path, wf_dir, agent.agent_id)
    return AgentExport(
        agent_id=agent.agent_id,
        label=agent.label,
        index=agent.index,
        phase_index=agent.phase_index,
        phase_title=agent.phase_title,
        model=agent.model,
        state=_state_bucket(agent, journal_state),
        tokens=agent.tokens,
        tool_calls=agent.tool_calls,
        duration_ms=agent.duration_ms,
        attempt=agent.attempt,
        task=wr.agent_task(jsonl_path),
        output=output,
        headline=wr.report_headline(output),
        timeline=wr.agent_timeline(jsonl_path),
        jsonl_path=jsonl_path,
    )


def _group_phases(exports: list[AgentExport]) -> list[PhaseExport]:
    """Group agents into phases by (index, title), preserving first-appearance (= index) order."""
    order: list[PhaseExport] = []
    by_key: dict[tuple[int, str], PhaseExport] = {}
    for ex in exports:
        key = (ex.phase_index, ex.phase_title)
        phase = by_key.get(key)
        if phase is None:
            phase = PhaseExport(index=ex.phase_index, title=ex.phase_title, agents=[])
            by_key[key] = phase
            order.append(phase)
        phase.agents.append(ex)
    return order


def _rollup(exports: list[AgentExport]) -> dict:
    """Aggregate the SCOPED agents into a count+token rollup."""
    roll = {
        "running": 0,
        "done": 0,
        "error": 0,
        "idle": 0,
        "total": len(exports),
        "tokens": 0,
    }
    for ex in exports:
        roll[ex.state] += 1
        roll["tokens"] += ex.tokens
    return roll


# ───────────────────────── public aggregator ─────────────────────────
def collect_run(
    wf_id: str,
    *,
    projects: str = wr.DEFAULT_PROJECTS,
    scope: str = "run",
    agents: list[str] | None = None,
) -> ExportModel:
    """Build a fully-materialized ``ExportModel`` for ``wf_id``.

    ``scope='run'`` includes every agent; ``scope='subset'``/``'agent'`` include only agents whose
    **label** (case-insensitive, exact) is in ``agents`` - **label-SET** semantics: ALL agents
    matching a requested label are included. An unknown label raises ``ValueError`` (listing the
    available labels); a missing ``wf_id`` raises ``LookupError`` (with near-matches). Reuses the
    shared ``workflow_run`` parser; does NOT touch ``fleet_rollup`` or ``agent_prompt``.
    """
    run = _find_run(wf_id, projects)
    wf_dir = run.subagents_dir()
    states = wr.journal_states(wf_dir)

    if scope == "run":
        selected = list(run.agents)
        scope_agents: list[str] = []
    else:
        if not agents:
            raise ValueError(
                f"scope {scope!r} requires one or more agent labels (--agents)"
            )
        requested = {a.strip().lower() for a in agents}
        available = [a.label for a in run.agents]
        have = {label.lower() for label in available}
        missing = sorted(r for r in requested if r not in have)
        if missing:
            raise ValueError(
                f"unknown agent label(s) {missing}; available labels: {available}"
            )
        selected = [a for a in run.agents if a.label.lower() in requested]
        scope_agents = list(agents)

    exports = [_agent_export(a, wf_dir, states.get(a.agent_id)) for a in selected]
    phases = _group_phases(exports)
    rollup = _rollup(exports)

    generated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    redaction_mode = "strict"
    provenance = {
        "wf_id": run.wf_id,
        "name": run.name,
        "session": run.session,
        "scope": scope,
        "redaction_mode": redaction_mode,
        "generated_at": generated_at,
        "schema_version": wr.CC_SCHEMA_VERSION,
    }
    return ExportModel(
        wf_id=run.wf_id,
        name=run.name,
        status=run.status,
        active=run.active,
        generated_at=generated_at,
        schema_version=wr.CC_SCHEMA_VERSION,
        scope=scope,
        scope_agents=scope_agents,
        redaction_mode=redaction_mode,
        phases=phases,
        rollup=rollup,
        session=run.session,
        manifest_path=run.manifest_path,
        provenance=provenance,
    )
