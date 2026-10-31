#!/usr/bin/env python3
"""workflow_run.py — shared, dependency-light reader for Claude Code Workflow runs + the whole fleet.

The single richest source the incumbent monitor + the native /workflows view both under-use is the live
telemetry MANIFEST at ``<project>/<session>/workflows/wf_<id>.json`` — re-flushed ~0s after every agent
progress event. It carries the entire fan-out: per-agent label(=the human lens name), phase, model, state,
tokens, toolCalls, lastTool, and prompt/result previews. This module parses it (+ journal.jsonl for
authoritative status, + transcripts for full drill-down), across the WHOLE FLEET (all sessions/projects),
with O(changed) polling. LIVENESS is journal-led for manifest-backed runs: the estate's runtime
kill-stamps manifests MID-RUN (measured 2026-08-18: status=killed, agents=0 while 56 agents kept
writing), so a terminal manifest whose journal dir outwrote it within JOURNAL_ACTIVE_WINDOW_S renders
running — see FleetPoller._apply_journal_liveness. It also provides the recall-workflow-agent extractor
(prompt/output/headline/locate) so the CLI skill and the Textual monitor share ONE parser.

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
_NOT_ACTIVE = _TERMINAL_RUN | {"idle"}
# Measured live orphans had newest-write ages of 1-4 s while the nearest dead
# orphan was 1,883,281 s old. This window cleanly separates them; 24 h retention
# keeps just-finished runs visible while excluding all 14 ancient (>=21 day) orphans.
JOURNAL_ACTIVE_WINDOW_S = 300.0
JOURNAL_RETENTION_S = 86400.0
# Cadence for re-running the FULL liveness probe (journal.jsonl + agent-*.jsonl mtimes)
# over a journal dir whose newest known write is older than 2x the active window. See
# FleetPoller._journal_last_write for the cost model and the promote-only guarantee.
_LIVENESS_REPROBE_S = 60.0


# ───────────────────────── data model ─────────────────────────
@dataclass
class WFAgent:
    """One fan-out agent.

    The first block is the MANIFEST row. The trailing three fields carry the JOURNAL's
    view, which is authoritative for liveness and is the ONLY source that knows about
    agents the manifest never recorded at all (see :func:`reconcile_roster`).
    """

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
    # ── journal-derived; the defaults reproduce the pure-manifest view exactly ──
    journal_state: str = ""  # "started" | "result" | "" (journal silent / not read)
    journal_only: bool = False  # True when NO manifest row exists for this agent
    lost: bool = False  # started, never returned a result, and the run has TERMINATED

    @property
    def running(self) -> bool:
        # "started" is the JOURNAL's word for a live agent (synthesized rows use it). The
        # other four are the manifest's — measured fleet-wide over 12,575 agent rows, the
        # only states it ever emits are done / start / error / progress.
        return self.state in ("start", "started", "progress", "queued", "running")

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
    wf_dir: str = ""
    # While journal-led liveness overrides a terminal manifest status (see
    # FleetPoller._apply_journal_liveness), the manifest's own word is preserved here;
    # "" = no override in effect. Metadata (name/tokens/phases) is ALWAYS manifest-led.
    manifest_status: str = ""

    @property
    def active(self) -> bool:
        return self.status not in _NOT_ACTIVE

    @property
    def counts(self) -> dict:
        """Return mutually exclusive run-level agent outcome tallies.

        ``running`` is reported only while the run itself is live. A terminal run's
        unfinished agents are ``orphaned``, not done and not error, because the run
        ended before either outcome was recorded. The invariant ``running + done +
        error + orphaned == total`` always holds.
        """
        c = {
            "running": 0,
            "done": 0,
            "error": 0,
            "orphaned": 0,
            "total": len(self.agents),
        }
        live = self.active
        for a in self.agents:
            if a.errored:
                c["error"] += 1
            elif a.state == "done":
                c["done"] += 1
            elif live:
                c["running"] += 1
            else:
                c["orphaned"] += 1
        return c

    def subagents_dir(self) -> str:
        if self.wf_dir:
            return self.wf_dir
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


def iter_journal_dirs(projects: str = DEFAULT_PROJECTS) -> list[str]:
    try:
        candidates = glob.glob(
            os.path.join(projects, "*", "*", "subagents", "workflows", "wf_*")
        )
    except OSError:
        return []
    out = []
    for wf_dir in candidates:
        try:
            if os.path.isdir(wf_dir) and os.path.isfile(
                os.path.join(wf_dir, "journal.jsonl")
            ):
                out.append(wf_dir)
        except OSError:
            continue
    return out


def _dir_last_write(wf_dir: str) -> float:
    try:
        paths = [os.path.join(wf_dir, "journal.jsonl")]
        paths.extend(glob.glob(os.path.join(wf_dir, "agent-*.jsonl")))
    except OSError:
        return 0.0
    mtimes = []
    for path in paths:
        try:
            mtimes.append(os.path.getmtime(path))
        except OSError:
            continue
    return max(mtimes, default=0.0)


def parse_journal_run(
    wf_dir: str,
    now: float | None = None,
    active_window: float = JOURNAL_ACTIVE_WINDOW_S,
    last_write: float | None = None,
) -> WFRun | None:
    """Build the facts available for a manifest-less run; never infer missing data."""
    import time

    states: dict[str, str] = {}
    try:
        with open(
            os.path.join(wf_dir, "journal.jsonl"),
            encoding="utf-8",
            errors="replace",
        ) as fh:
            for line in fh:
                try:
                    record = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                if not isinstance(record, dict):
                    continue
                aid = record.get("agentId")
                kind = record.get("type")
                if not isinstance(aid, str) or not aid:
                    continue
                if aid not in states:
                    states[aid] = ""
                if kind == "result":
                    states[aid] = "result"
    except OSError:
        return None
    if not states:
        return None
    stamp = _dir_last_write(wf_dir) if last_write is None else last_write
    current = time.time() if now is None else now
    active = stamp > 0.0 and current - stamp <= active_window
    agents = []
    for index, (aid, state) in enumerate(states.items()):
        model = ""
        try:
            with open(
                os.path.join(wf_dir, f"agent-{aid}.meta.json"),
                encoding="utf-8",
                errors="replace",
            ) as fh:
                meta = json.load(fh)
            if isinstance(meta, dict):
                model = _s(meta, "model")
        except (OSError, json.JSONDecodeError, ValueError):
            pass
        agents.append(
            WFAgent(
                agent_id=aid,
                index=index,
                label=aid[:8],
                phase_index=0,
                phase_title="",
                model=model,
                state="done"
                if state == "result"
                else "running"
                if active
                else "unknown",
                tokens=0,
                tool_calls=0,
                duration_ms=0,
                last_tool="",
                last_summary="",
                prompt_preview="",
                result_preview="",
                attempt=1,
                # Journals contain no timestamps. Keeping both at zero makes idle_ms()
                # return zero, structurally preventing a stall/stuck/hung mtime inference.
                started_at=0,
                last_progress_at=0,
            )
        )
    normalized = os.path.normpath(wf_dir)
    session_dir = os.path.dirname(os.path.dirname(os.path.dirname(normalized)))
    return WFRun(
        wf_id=os.path.basename(normalized),
        name="",
        status="running" if active else "idle",
        phases=[],
        agent_count=len(agents),
        total_tokens=0,
        total_tool_calls=0,
        duration_ms=0,
        started_at=0,
        manifest_path="",
        session=os.path.basename(session_dir),
        mtime=stamp,
        agents=agents,
        wf_dir=wf_dir,
    )


def _restamp_journal_rows(run: WFRun) -> None:
    """Re-state journal-only unfinished rows after a run-liveness flip (either way).

    ``reconcile_roster`` stamps synthesized rows only when it ADDS them, so a liveness
    flip after that would leave stale "lost"/"started" strings on existing rows. Rows
    the journal saw complete (``result``) and manifest-backed rows are never touched;
    while the run renders live a started-with-no-result agent is running, and once the
    manifest's terminal verdict is restored it is ``lost`` — by the journal + the
    manifest's own record, never by an mtime.
    """
    live = run.active
    for a in run.agents:
        if a.journal_only and a.journal_state != "result":
            a.state = "started" if live else "lost"
            a.lost = not live


class FleetPoller:
    """Whole-fleet reader that only re-parses manifests whose mtime moved (O(changed), not O(all))."""

    def __init__(
        self, projects: str = DEFAULT_PROJECTS, *, journal: bool = True
    ) -> None:
        self.projects = projects
        self.journal = journal  # False = the old manifest-only roster (kept for tests)
        self._runs: dict[str, WFRun] = {}
        self._mtimes: dict[str, float] = {}
        # wf_dir -> (byte cursor into journal.jsonl, accumulated agentId -> type)
        self._journal: dict[str, tuple[int, dict]] = {}
        # wf_dir -> (last full-probe time, newest journal-dir write it found)
        self._liveness: dict[str, tuple[float, float]] = {}

    def poll(self) -> list[WFRun]:
        seen = set()
        manifest_ids = set()
        now = __import__("time").time()
        for p in iter_manifest_paths(self.projects):
            seen.add(p)
            mt = _mtime(p)
            fresh = False
            if self._mtimes.get(p) != mt:
                run = parse_manifest(p, mt)
                if run:
                    self._runs[p] = run
                    self._mtimes[p] = mt
                    fresh = True
            cached = self._runs.get(p)
            if cached is not None:
                manifest_ids.add(cached.wf_id)
            if self.journal and cached is not None:
                # Liveness BEFORE the roster fold, so reconcile_roster stamps any
                # synthesized rows against the journal-led verdict, not the stale one.
                self._apply_journal_liveness(cached, now)
                self._fold_journal(cached, fresh)
        for wf_dir in iter_journal_dirs(self.projects):
            if os.path.basename(os.path.normpath(wf_dir)) in manifest_ids:
                continue
            last_write = _dir_last_write(wf_dir)
            if not last_write or now - last_write > JOURNAL_RETENTION_S:
                continue
            seen.add(wf_dir)
            if self._mtimes.get(wf_dir) != last_write:
                run = parse_journal_run(wf_dir, now=now, last_write=last_write)
                if run:
                    self._runs[wf_dir] = run
                    self._mtimes[wf_dir] = last_write
            cached = self._runs.get(wf_dir)
            if cached is not None:
                is_active = now - last_write <= JOURNAL_ACTIVE_WINDOW_S
                cached.status = "running" if is_active else "idle"
                for agent in cached.agents:
                    if agent.state != "done":
                        agent.state = "running" if is_active else "unknown"
        for gone in set(self._runs) - seen:
            wf_dir = self._runs[gone].subagents_dir()
            self._journal.pop(wf_dir, None)
            self._liveness.pop(wf_dir, None)
            self._runs.pop(gone, None)
            self._mtimes.pop(gone, None)
        return sorted(self._runs.values(), key=lambda r: r.mtime, reverse=True)

    def _fold_journal(self, run: WFRun, fresh: bool = False) -> None:
        """Reconcile ONE run against its journal, reading only newly appended bytes.

        Steady-state cost is O(appended bytes), never O(journal). Measured on this box:
        875 journals totalling 93.7 MB, largest 10.9 MB — so a full re-read per 1 s poll
        was never affordable. The extra ``getsize`` stat the cursor needs costs 24.1 ms
        per whole-fleet poll (865 runs) against the 40.1 ms baseline glob it rides beside.
        """
        wf_dir = run.subagents_dir()
        offset, states = self._journal.get(wf_dir, (0, {}))
        new_offset, records = read_journal_delta(
            os.path.join(wf_dir, "journal.jsonl"), offset
        )
        for rec in records:
            _fold_journal_record(states, rec)
        self._journal[wf_dir] = (new_offset, states)
        # Re-stamping every agent on a tick where nothing moved is pure cost: measured
        # 0.171s vs a 0.070s manifest-only baseline across 868 runs / 14,785 agents.
        # ``fresh`` covers the re-parsed case, whose brand-new WFRun carries no stamps yet.
        if records or fresh:
            reconcile_roster(run, states)

    def _journal_last_write(self, wf_dir: str, now: float) -> float:
        """Newest journal-dir write — exact every poll while recent, cadence-cached once dead.

        ``_dir_last_write`` stats journal.jsonl + every agent transcript, so probing all
        terminal-manifest dirs each poll would cost ~15k stats on this fleet (866 dirs x
        ~17 transcripts). While a dir last wrote within 2x JOURNAL_ACTIVE_WINDOW_S the
        probe runs every poll (exact promote AND lapse tracking); once long-dead it
        re-runs only each _LIVENESS_REPROBE_S, so a resumed run is promoted within
        <=60 s. The cache can only DELAY a promotion — it never manufactures a death
        verdict, so no stuck/hung state can ever be inferred from these mtimes.
        """
        probed_at, last_write = self._liveness.get(wf_dir, (0.0, 0.0))
        if (
            now - last_write <= JOURNAL_ACTIVE_WINDOW_S * 2
            or now - probed_at >= _LIVENESS_REPROBE_S
        ):
            last_write = _dir_last_write(wf_dir)
            self._liveness[wf_dir] = (now, last_write)
        return last_write

    def _apply_journal_liveness(self, run: WFRun, now: float) -> None:
        """Journal-led LIVENESS for one manifest-backed run; metadata stays manifest-led.

        REFUTED PRECEDENCE (2026-08-18): "a manifest always wins over a same-id
        journal" was wrong as a liveness rule — the estate's runtime writes terminal
        manifests (status=killed, agents=0) MID-RUN for workflows that keep executing
        or resume under the same wf_id, so one stale stamp blinded the board to 56
        currently-executing agents across 2 live runs. What survives: the manifest owns
        name/tokens/phase metadata ALWAYS, and owns status unless the journal dir
        provably outwrote it — newest write STRICTLY newer than the manifest's own
        mtime AND within JOURNAL_ACTIVE_WINDOW_S (recency-gated exactly like
        parse_journal_run, so the 14 ancient orphans stay dead). When the recency
        lapses, the status RESTORES to the manifest's own word: death is the manifest's
        verdict, never an mtime inference, and nothing here can render "stuck".
        """
        if not run.manifest_status and run.status not in _NOT_ACTIVE:
            return  # the manifest already says live — nothing to promote
        last_write = self._journal_last_write(run.subagents_dir(), now)
        live = last_write > run.mtime and now - last_write <= JOURNAL_ACTIVE_WINDOW_S
        if live and not run.manifest_status:
            run.manifest_status = run.status  # preserve the manifest's own word
            run.status = "running"
            _restamp_journal_rows(run)
        elif not live and run.manifest_status:
            run.status = run.manifest_status
            run.manifest_status = ""
            _restamp_journal_rows(run)

    def active(self) -> list[WFRun]:
        return [r for r in self.poll() if r.active]


def fleet_rollup(runs: list[WFRun]) -> dict:
    tot = {
        "runs": len(runs),
        "active_runs": 0,
        "running": 0,
        "done": 0,
        "error": 0,
        "orphaned": 0,
        "tokens": 0,
    }
    for r in runs:
        tot["active_runs"] += 1 if r.active else 0
        c = r.counts
        tot["running"] += c["running"]
        tot["done"] += c["done"]
        tot["error"] += c["error"]
        tot["orphaned"] += c["orphaned"]
        tot["tokens"] += r.total_tokens
    return tot


# ───────────────────────── journal (authoritative status + clean result) ─────────────────────────
# Phase bucket for agents the manifest never recorded — named, not blank, so the board
# says WHY the row carries no model/token/tool metadata instead of implying phase 0.
JOURNAL_ONLY_PHASE = "(no manifest row)"


def _fold_journal_record(out: dict, d: object) -> None:
    """Fold ONE journal record into ``agentId -> type`` (``result`` wins, never regresses).

    The single source of that precedence rule, shared by the whole-file
    :func:`journal_states` and the incremental :func:`read_journal_delta` path.
    """
    if not isinstance(d, dict):  # a bare JSON scalar line is not a record
        return
    aid, t = d.get("agentId"), d.get("type")
    if aid and (t == "result" or out.get(aid) != "result"):
        out[aid] = t


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
                _fold_journal_record(out, d)
    except OSError:
        return out
    return out


def read_journal_delta(path: str, offset: int) -> tuple[int, list]:
    """Parse ONLY the bytes appended to an append-only journal past ``offset``.

    Returns ``(new_offset, records)``. Only newline-TERMINATED lines are consumed, so a
    partially flushed trailing line is left for the next poll rather than dropped. A file
    that SHRANK (rotated/truncated) rewinds the cursor and is re-read whole. Every failure
    path returns the cursor unmoved with no records, so a vanished or unreadable journal
    degrades to "no new information" — a bounded read that can never raise or block.
    """
    try:
        size = os.path.getsize(path)
    except OSError:
        return offset, []
    if size < offset:  # truncated / rotated -> re-read from the top
        offset = 0
    if size == offset:  # nothing appended
        return offset, []
    try:
        with open(path, "rb") as fh:
            fh.seek(offset)
            data = fh.read(size - offset)
    except OSError:
        return offset, []
    nl = data.rfind(b"\n")
    if nl == -1:  # no COMPLETE line yet -> leave the cursor for the next poll
        return offset, []
    records = []
    for line in data[: nl + 1].splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line.decode("utf-8", "replace")))
        except json.JSONDecodeError:
            continue
    return offset + nl + 1, records


def reconcile_roster(run: WFRun, states: dict) -> int:
    """Union the manifest roster with the journal's agent set. Returns rows ADDED.

    THE MANIFEST IS NOT A COMPLETE ROSTER. Measured on wf_e58dfd3f-7b1 (completed): 50
    ``workflow_agent`` rows, all ``attempt=1``, against 80 distinct journal agentIds and
    80 ``agent-*.jsonl`` transcripts on disk — two mechanically independent signals
    agreeing that 30 agents were invisible to the board, each holding 245-483 KB of real
    transcript. Fleet-wide the same probe found 2,242 invisible agents across 107 of 865
    runs (worst single run: 237). Every one of those 30 had a ``started`` record and NO
    ``result``: work that ran and was never accounted for.

    Synthesized rows carry only what the journal actually knows — id and state. Their
    state is journal-derived, NEVER mtime-derived: a started-with-no-result agent is
    ``running`` while the run is live and ``lost`` once the run has terminated, so the
    board never infers "stuck" from file timestamps.

    Idempotent: existing rows are re-stamped, never duplicated, so a poller may call this
    on the same cached WFRun every tick.
    """
    known = {a.agent_id for a in run.agents}
    for a in run.agents:  # stamp the authoritative state onto the manifest rows
        a.journal_state = states.get(a.agent_id, "")
    terminal = not run.active
    added = 0
    for aid, jstate in states.items():
        if aid in known:
            continue
        done = jstate == "result"
        lost = terminal and not done
        run.agents.append(
            WFAgent(
                agent_id=aid,
                index=len(run.agents),
                label=aid[:8],
                phase_index=-1,
                phase_title=JOURNAL_ONLY_PHASE,
                model="",
                state=("done" if done else "lost" if lost else "started"),
                tokens=0,
                tool_calls=0,
                duration_ms=0,
                last_tool="",
                last_summary="",
                prompt_preview="",
                result_preview="",
                attempt=1,
                started_at=0,
                last_progress_at=0,
                journal_state=jstate,
                journal_only=True,
                lost=lost,
            )
        )
        added += 1
    return added


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
        f"{roll['running']} running / {roll['done']} done / {roll['error']} error / "
        f"{roll['orphaned']} orphaned · {roll['tokens']:,} tok"
    )
    for r in sorted(runs, key=lambda x: x.active, reverse=True)[:8]:
        c = r.counts
        flag = "●" if r.active else "·"
        print(
            f"  {flag} {r.wf_id}  {r.name[:34]:34}  {r.status:9}  "
            f"{c['done']}✓ {c['error']}✗ {c['running']}◔ {c['orphaned']}~ /{c['total']}  "
            f"{r.total_tokens:>9,} tok"
        )
