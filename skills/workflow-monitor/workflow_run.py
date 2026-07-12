#!/usr/bin/env python3
"""workflow_run.py — shared, dependency-light reader for Claude Code Workflow runs + the whole fleet.

The single richest source the incumbent monitor + the native /workflows view both under-use is the live
telemetry MANIFEST at ``<project>/<session>/workflows/wf_<id>.json`` — re-flushed ~0s after every agent
progress event. It carries the entire fan-out: per-agent label(=the human lens name), phase, model, state,
tokens, toolCalls, lastTool, and prompt/result previews. This module parses it (+ journal.jsonl for
authoritative status, + transcripts for full drill-down), across the WHOLE FLEET (all sessions/projects),
with O(changed) polling. It also provides the recall-workflow-agent extractor (prompt/output/headline/
locate) so the CLI skill and the Textual monitor share ONE parser.

SCHEMA NOTE: the manifest/journal shapes are Claude Code INTERNAL + undocumented; verified on the version
below. Parse DEFENSIVELY (rely only on fields observed on 100% of entries) and keep a fixture test so a
Claude Code update can't silently break the board.
"""

from __future__ import annotations

import glob
import json
import os
import re
from dataclasses import dataclass, field

# Re-export shim: the schema-agnostic timeline IR was extracted into the vendored
# `monitorcore.timeline` module. These names are re-exported here (explicit `X as X`
# aliases) so existing importers — `from workflow_run import TimelineEvent`
# (wfmon_export.model), `wr.report_headline` (the cockpit + model), etc. — keep
# resolving, and so this module's own `agent_timeline` can build TimelineEvents.
from monitorcore.timeline import (
    TimelineEvent as TimelineEvent,
    _flatten_content as _flatten_content,
    pair_tool_calls as pair_tool_calls,
    report_headline as report_headline,
)

CC_SCHEMA_VERSION = "2.1.207"
DEFAULT_PROJECTS = os.path.join(os.path.expanduser("~"), ".claude", "projects")
_TERMINAL_RUN = {"completed", "stopped", "error", "killed", "failed"}


# ───────────────────────── data model ─────────────────────────
@dataclass
class WFAgent:
    agent_id: str
    index: int
    label: str
    phase_index: int
    phase_title: str
    model: str
    state: str
    tokens: int
    tool_calls: int
    duration_ms: int
    last_tool: str
    last_summary: str
    prompt_preview: str
    result_preview: str
    attempt: int
    started_at: int
    last_progress_at: int

    @property
    def running(self) -> bool:
        return self.state in ("start", "progress", "queued", "running")

    @property
    def errored(self) -> bool:
        return self.state == "error"

    @property
    def retrying(self) -> bool:
        return bool(self.attempt and self.attempt > 1)

    def idle_ms(self, now_ms: float) -> float:
        return now_ms - self.last_progress_at if self.last_progress_at else 0.0


@dataclass
class WFRun:
    wf_id: str
    name: str
    status: str
    phases: list
    agent_count: int
    total_tokens: int
    total_tool_calls: int
    duration_ms: int
    started_at: int
    manifest_path: str
    session: str
    mtime: float
    agents: list = field(default_factory=list)

    @property
    def active(self) -> bool:
        return self.status not in _TERMINAL_RUN

    @property
    def counts(self) -> dict:
        c = {"running": 0, "done": 0, "error": 0, "total": len(self.agents)}
        for a in self.agents:
            if a.errored:
                c["error"] += 1
            elif a.state == "done":
                c["done"] += 1
            else:
                c["running"] += 1
        return c

    def subagents_dir(self) -> str:
        # <project>/<session>/subagents/workflows/<wf_id>/  (transcripts + journal.jsonl)
        base = os.path.dirname(os.path.dirname(self.manifest_path))  # -> <session>
        return os.path.join(base, "subagents", "workflows", self.wf_id)


# ───────────────────────── manifest parsing ─────────────────────────
def _i(d: dict, k: str) -> int:
    v = d.get(k)
    return int(v) if isinstance(v, (int, float)) else 0


def _s(d: dict, k: str, default: str = "") -> str:
    v = d.get(k)
    return v if isinstance(v, str) and v else default


def _mtime(p: str) -> float:
    try:
        return os.path.getmtime(p)
    except OSError:
        return 0.0


def _session_of(path: str) -> str:
    parts = os.path.normpath(path).split(os.sep)
    return parts[parts.index("workflows") - 1] if "workflows" in parts else ""


def parse_manifest(path: str, mtime: float | None = None) -> WFRun | None:
    """Parse one wf_<id>.json manifest into a WFRun (defensive; None on unreadable)."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            d = json.load(fh)
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(d, dict):
        return None
    agents = []
    for e in d.get("workflowProgress") or []:
        if not isinstance(e, dict) or e.get("type") != "workflow_agent":
            continue
        agents.append(
            WFAgent(
                agent_id=_s(e, "agentId"),
                index=_i(e, "index"),
                label=_s(e, "label") or _s(e, "agentId")[:8] or "agent",
                phase_index=_i(e, "phaseIndex"),
                phase_title=_s(e, "phaseTitle"),
                model=_s(e, "model"),
                state=_s(e, "state", "?"),
                tokens=_i(e, "tokens"),
                tool_calls=_i(e, "toolCalls"),
                duration_ms=_i(e, "durationMs"),
                last_tool=_s(e, "lastToolName"),
                last_summary=_s(e, "lastToolSummary"),
                prompt_preview=_s(e, "promptPreview"),
                result_preview=_s(e, "resultPreview"),
                attempt=_i(e, "attempt") or 1,
                started_at=_i(e, "startedAt"),
                last_progress_at=_i(e, "lastProgressAt"),
            )
        )
    phases = [
        p.get("title") if isinstance(p, dict) else p for p in (d.get("phases") or [])
    ]
    m = re.search(r"(wf_[0-9a-z-]+)", os.path.basename(path))
    return WFRun(
        wf_id=(m.group(1) if m else os.path.basename(path)),
        name=_s(d, "workflowName"),
        status=_s(d, "status", "?"),
        phases=phases,
        agent_count=_i(d, "agentCount") or len(agents),
        total_tokens=_i(d, "totalTokens"),
        total_tool_calls=_i(d, "totalToolCalls"),
        duration_ms=_i(d, "durationMs"),
        started_at=_i(d, "startTime"),
        manifest_path=path,
        session=_session_of(path),
        mtime=(mtime if mtime is not None else _mtime(path)),
        agents=agents,
    )


# ───────────────────────── fleet discovery + O(changed) polling ─────────────────────────
def iter_manifest_paths(projects: str = DEFAULT_PROJECTS) -> list[str]:
    return glob.glob(os.path.join(projects, "*", "*", "workflows", "wf_*.json"))


class FleetPoller:
    """Whole-fleet reader that only re-parses manifests whose mtime moved (O(changed), not O(all))."""

    def __init__(self, projects: str = DEFAULT_PROJECTS) -> None:
        self.projects = projects
        self._runs: dict[str, WFRun] = {}
        self._mtimes: dict[str, float] = {}

    def poll(self) -> list[WFRun]:
        seen = set()
        for p in iter_manifest_paths(self.projects):
            seen.add(p)
            mt = _mtime(p)
            if self._mtimes.get(p) != mt:
                run = parse_manifest(p, mt)
                if run:
                    self._runs[p] = run
                    self._mtimes[p] = mt
        for gone in set(self._runs) - seen:
            self._runs.pop(gone, None)
            self._mtimes.pop(gone, None)
        return sorted(self._runs.values(), key=lambda r: r.mtime, reverse=True)

    def active(self) -> list[WFRun]:
        return [r for r in self.poll() if r.active]


def fleet_rollup(runs: list[WFRun]) -> dict:
    tot = {
        "runs": len(runs),
        "active_runs": 0,
        "running": 0,
        "done": 0,
        "error": 0,
        "tokens": 0,
    }
    for r in runs:
        tot["active_runs"] += 1 if r.active else 0
        c = r.counts
        tot["running"] += c["running"]
        tot["done"] += c["done"]
        tot["error"] += c["error"]
        tot["tokens"] += r.total_tokens
    return tot


# ───────────────────────── journal (authoritative status + clean result) ─────────────────────────
def journal_states(wf_dir: str) -> dict:
    """agentId -> 'started' | 'result' from journal.jsonl (result wins). Authoritative vs mtime guessing."""
    out: dict[str, str] = {}
    j = os.path.join(wf_dir, "journal.jsonl")
    try:
        with open(j, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                aid, t = d.get("agentId"), d.get("type")
                if aid and (t == "result" or out.get(aid) != "result"):
                    out[aid] = t
    except OSError:
        return out
    return out


# ───────────────────────── transcript drill-down (the recall-workflow-agent extractor) ─────────────────────────
def _text_of(msg: dict) -> str:
    c = msg.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "\n".join(
            b.get("text", "")
            for b in c
            if isinstance(b, dict) and b.get("type") == "text"
        )
    return ""


def agent_transcript(path: str) -> tuple[list[str], list[str]]:
    users, assistants = [], []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                txt = _text_of(d.get("message", {}) or {})
                if not txt.strip():
                    continue
                if d.get("type") == "user":
                    users.append(txt)
                elif d.get("type") == "assistant":
                    assistants.append(txt)
    except OSError:
        pass
    return users, assistants


def agent_prompt(path: str) -> str:
    """The agent's task = its largest user message."""
    users, _ = agent_transcript(path)
    return max(users, key=len) if users else ""


def journal_result(wf_dir: str, agent_id: str) -> str:
    """The clean captured OUTPUT for an agent (journal `result`), authoritative even for tool-users."""
    j = os.path.join(wf_dir, "journal.jsonl")
    try:
        with open(j, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if d.get("type") == "result" and d.get("agentId") == agent_id:
                    r = d.get("result")
                    if isinstance(r, str):
                        return r
                    if r is not None:
                        return json.dumps(r, indent=2, ensure_ascii=False)
    except OSError:
        return ""
    return ""


def agent_output(
    agent_jsonl: str, wf_dir: str | None = None, agent_id: str | None = None
) -> str:
    """Clean output: journal `result` if available, else the final assistant message."""
    if wf_dir and agent_id:
        r = journal_result(wf_dir, agent_id)
        if r:
            return r
    _, assistants = agent_transcript(agent_jsonl)
    return assistants[-1] if assistants else ""


# ───────────────────────── ordered timeline drill-down (assistant + user records) ─────────────────────────
def agent_timeline(agent_jsonl: str) -> list[TimelineEvent]:
    """Ordered event stream from an agent-<id>.jsonl transcript, in file order.

    Walks assistant AND user records (tool_use lives in assistant records, tool_result in user
    records). Records whose ``message`` is not a dict (attachment + system) are skipped. Empty
    text / signature-only-empty thinking blocks are dropped. ``seq`` is the 0-based emission index.
    Defensive: ``[]`` on OSError; malformed JSON lines skipped; unknown block types ignored.
    """
    events: list[TimelineEvent] = []
    seq = 0
    try:
        with open(agent_jsonl, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg = rec.get("message")
                if not isinstance(msg, dict):
                    continue
                content = msg.get("content")
                if isinstance(content, str):
                    if content.strip():
                        events.append(TimelineEvent(kind="text", seq=seq, text=content))
                        seq += 1
                    continue
                if not isinstance(content, list):
                    continue
                for b in content:
                    if not isinstance(b, dict):
                        continue
                    bt = b.get("type")
                    if bt == "text":
                        t = b.get("text", "")
                        if isinstance(t, str) and t.strip():
                            events.append(TimelineEvent(kind="text", seq=seq, text=t))
                            seq += 1
                    elif bt == "thinking":
                        th = b.get("thinking", "")
                        if isinstance(th, str) and th.strip():
                            events.append(
                                TimelineEvent(kind="thinking", seq=seq, text=th)
                            )
                            seq += 1
                    elif bt in ("tool_use", "server_tool_use"):
                        events.append(
                            TimelineEvent(
                                kind="tool_use",
                                seq=seq,
                                name=_s(b, "name"),
                                tool_input=dict(b.get("input") or {}),
                                tool_id=_s(b, "id"),
                            )
                        )
                        seq += 1
                    elif bt in ("tool_result", "advisor_tool_result"):
                        events.append(
                            TimelineEvent(
                                kind="tool_result",
                                seq=seq,
                                tool_id=_s(b, "tool_use_id"),
                                is_error=bool(b.get("is_error")),
                                output=_flatten_content(b.get("content")),
                            )
                        )
                        seq += 1
                    # unknown block types are ignored
    except OSError:
        return []
    return events


def agent_task(agent_jsonl: str) -> str:
    """The spawn prompt = the FIRST ``type == "user"`` record with non-empty ``_text_of``.

    NOT ``agent_prompt``'s max-by-length. Correctly skips leading tool-result-only user records
    (their ``_text_of`` is ""). Returns "" if none / unreadable. Reuses ``_text_of``.
    """
    try:
        with open(agent_jsonl, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("type") != "user":
                    continue
                msg = rec.get("message")
                if not isinstance(msg, dict):
                    continue
                txt = _text_of(msg)
                if txt.strip():
                    return txt
    except OSError:
        return ""
    return ""


if __name__ == "__main__":  # pragma: no cover
    poller = FleetPoller()
    runs = poller.poll()
    roll = fleet_rollup(runs)
    print(
        f"FLEET: {roll['runs']} runs ({roll['active_runs']} active) · "
        f"{roll['running']} running / {roll['done']} done / {roll['error']} error · {roll['tokens']:,} tok"
    )
    for r in sorted(runs, key=lambda x: x.active, reverse=True)[:8]:
        c = r.counts
        flag = "●" if r.active else "·"
        print(
            f"  {flag} {r.wf_id}  {r.name[:34]:34}  {r.status:9}  "
            f"{c['done']}✓ {c['error']}✗ {c['running']}◔ /{c['total']}  {r.total_tokens:>9,} tok"
        )
