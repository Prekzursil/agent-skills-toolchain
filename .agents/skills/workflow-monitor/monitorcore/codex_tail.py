"""``codex_tail`` — Codex thread telemetry: stream/rollout tailers + the board renderer.

Ports the personal ``codex_monitor.py`` dashboard into ``monitorcore`` as a 100%-gated
domain layer (PR-B3; mirrors ``agent_tail``'s shape for Claude subagents). It watches
OpenAI Codex activity from TWO sources and merges them into one :class:`CodexThread`
model:

* **stream** files — ``codex exec --json`` output teed by the fan-out relay to one
  ``<label>.jsonl`` per thread under a shared dir (default ``%TEMP%/codex-streams``,
  override ``$CODEX_STREAM_DIR``). The relay SHOULD prepend one ``monitor.meta`` JSONL
  line (or drop a ``<label>.meta.json`` sidecar) carrying prompt / label / cwd / model —
  the ``codex exec --experimental-json`` schema does not echo the prompt itself.
* **rollout** files — the sessions Codex itself persists under
  ``$CODEX_HOME/sessions/YYYY/MM/DD/rollout-*.jsonl`` (richer persisted schema:
  ``session_meta`` / ``event_msg`` / ``response_item`` / ``turn_context``). Only
  rollouts modified within the ``since_min`` window are tracked.

MANDATORY REDACTION AT INGEST: codex rollouts are foreign session files that embed full
prompts and command lines, so EVERY free-text field entering a :class:`CodexThread`
(prompt, label, cwd, model, event label/detail, error text) passes
:func:`monitorcore.redact.redact` BEFORE storage — stronger than the render-boundary
redaction the wfmon exporter uses, and with NO off switch (the ``scrub`` parameter is an
injectable TEST seam, never an opt-out).

Structure mirrors ``agent_tail``'s coverage-honesty split: pure, injectable, ANSI-free
helpers (:func:`board_line` / :func:`frame_rows` / :func:`render_frame` /
:func:`_live_step`) carry the covered logic; the ANSI colour table (:data:`COL` /
:func:`paint`) is kept separate like ``agent_tail``'s colour constants; the interactive
:func:`run_live` full-screen loop (VT enable + sleep + q-poll) is the ONLY
``pragma: no cover`` shell; and :func:`main` covers argparse + ``--once`` through
injected ``out`` / ``live`` / ``clock`` seams. The :class:`Tail` reader keeps a BYTES
remainder (the ``agent_tail._follow_step`` pattern) so a multi-byte character split
across reads never corrupts a line.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import time
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .ctx import ctx_gauge, ctx_label
from .redact import redact
from .textsafe import strip_controls

__all__ = [
    "CodexThread",
    "Poller",
    "Tail",
    "ToolEvent",
    "board_line",
    "clip",
    "default_sessions_dir",
    "default_stream_dir",
    "fmt_dur",
    "fmt_tokens",
    "frame_rows",
    "load_stream_meta",
    "main",
    "paint",
    "parse_iso",
    "parse_rollout_line",
    "parse_stream_line",
    "render_frame",
    "run_live",
    "status_counts",
]

# The injectable-scrubber type: every parser takes ``scrub`` so tests can assert the
# ingest boundary; the DEFAULT is always the real redactor (no off switch).
Scrub = Callable[[str], str]


def _scrub(text: str) -> str:
    """Strip control bytes, THEN mask secrets + collapse home paths (fail-closed).

    Control bytes are removed FIRST (before ``redact``) for two reasons: redaction then
    sees de-obfuscated text — a control byte spliced into a secret can no longer split the
    pattern to evade masking — and no ESC/BEL/OSC byte can survive ingest to be painted to
    the operator's terminal later (escape-injection / OSC-8 link / OSC-52 clipboard hijack).
    """
    return redact(strip_controls(text), enabled=True)[0]


def _keep(value: object, current: str, scrub: Scrub) -> str:
    """``value`` scrubbed when truthy, else ``current`` (the ``or``-fallback idiom)."""
    return scrub(str(value)) if value else current


def _keep_id(value: object, current: str) -> str:
    """Like :func:`_keep` but for an OPAQUE identifier: control-strip only, never redact.

    A thread/session id is a structural identifier, not free-text prose. It needs
    terminal-safety — no ESC/BEL/OSC byte reaching ``short_id()`` → ``name()`` →
    :func:`board_line` and the UNCLIPPED ``render_native`` — but NOT secret-redaction:
    :func:`redact` masks nothing in an id and could corrupt a legitimate id that happened
    to collide with a token pattern. Falsy ``value`` keeps ``current`` (the ``or``-fallback),
    so the assignment is idempotent when the id is absent. NOT the injectable ``scrub`` seam
    by design — an id is control-stripped unconditionally, never redaction-mangled."""
    return strip_controls(str(value)) if value else current


# ---------------------------------------------------------------------------
# Pure formatting helpers (ANSI-free)
# ---------------------------------------------------------------------------


def parse_iso(ts: object) -> float | None:
    """ISO-8601 (``Z`` or offset) → epoch seconds; ``None`` for non-str / empty / bad."""
    if not isinstance(ts, str) or not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def fmt_dur(secs: float | None) -> str:
    """Seconds → ``MM:SS`` (``H:MM:SS`` past an hour); ``--:--`` when unknown."""
    if secs is None or secs < 0:
        return "--:--"
    whole = int(secs)
    h, rem = divmod(whole, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def fmt_tokens(n: int | None) -> str:
    """Token count → compact ``k`` / ``M`` form (``0`` for falsy)."""
    if not n:
        return "0"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1000:
        return f"{n / 1000:.1f}k"
    return str(n)


def clip(text: str, width: int) -> str:
    """Strip control bytes, whitespace-collapse ``text``, and clip it to ``width``.

    This is the board's universal last-mile formatter (every group header / board line /
    event row passes through it), so control bytes are stripped at the very START — before
    the whitespace collapse and before the ``width - 1`` slice. That makes the slice
    escape-safe (it can never cut mid-escape) and guarantees no ESC/BEL/OSC byte from
    untrusted thread text is ever painted to the operator's terminal.
    """
    text = " ".join(
        strip_controls(text or "").replace("\r", " ").replace("\n", " ").split()
    )
    if width <= 1:
        return ""
    if len(text) <= width:
        return text
    return text[: width - 1] + "…"


# ---------------------------------------------------------------------------
# Per-thread state
# ---------------------------------------------------------------------------


@dataclass
class ToolEvent:
    """One observed tool/command/message event inside a Codex thread.

    ``kind`` ∈ {'cmd', 'tool', 'patch', 'msg', 'think'}; ``status`` ∈
    {'running', 'ok', 'error', ''}; ``dur`` is seconds when the source reports one.
    ``label`` / ``detail`` are ALREADY scrubbed by the parser that constructed the event.
    """

    kind: str
    label: str
    detail: str
    status: str
    dur: float | None
    ts: float


@dataclass
class CodexThread:
    """The merged live state of ONE Codex thread (from a stream or a rollout file).

    Every free-text field is stored ALREADY scrubbed (redaction at ingest — WU1b);
    ``_inflight`` is the transient index of in-flight ``command_execution`` items so a
    stream's ``item.completed`` can finalize the event object its ``item.started`` added.
    """

    key: str
    source: str  # "stream" | "rollout"
    path: str
    tid: str = "?"
    label: str = ""
    model: str = ""
    cwd: str = ""
    tool_kind: str = ""
    prompt: str = ""
    start_ts: float | None = None
    last_ts: float = 0.0
    tokens_total: int = 0
    # context-occupancy numerator: the LAST turn's usage (rollout ``last_token_usage``)
    # or the per-turn stream total — never the cumulative session total, which would
    # pin ctx% near 100%. Kept separate from ``tokens_total`` (the cumulative display).
    ctx_tokens: int = 0
    ctx_window: int = 0
    turns: int = 0
    tool_count: int = 0
    status: str = "idle"
    completed: bool = False
    aborted: bool = False
    events: deque[ToolEvent] = field(
        default_factory=lambda: deque[ToolEvent](maxlen=200)
    )
    _inflight: dict[str, ToolEvent] = field(default_factory=dict)

    def short_id(self) -> str:
        """The first dash-segment of the thread/session id, capped at 8 chars."""
        t = self.tid or self.key
        return t.split("-")[0][:8] if t else "?"

    def name(self) -> str:
        """Display name: the label, else ``<short_id>[/<cwd basename>]``."""
        if self.label:
            return self.label
        base = Path(self.cwd).name if self.cwd else ""
        return f"{self.short_id()}" + (f"/{base}" if base else "")

    def add_event(self, ev: ToolEvent) -> None:
        """Append ``ev``; cmd/tool/patch kinds count toward ``tool_count``."""
        self.events.append(ev)
        if ev.kind in ("cmd", "tool", "patch"):
            self.tool_count += 1

    def recompute_status(self, now: float, idle_thresh: float) -> None:
        """Derive ``status``: aborted > done (completed + quiet) > running > idle."""
        idle = now - self.last_ts if self.last_ts else 1e9
        if self.aborted:
            self.status = "aborted"
        elif self.completed and idle > 3:
            self.status = "done"
        elif idle < idle_thresh:
            self.status = "running"
        else:
            self.status = "idle"


# ---------------------------------------------------------------------------
# Incremental file tailer
# ---------------------------------------------------------------------------


@dataclass
class Tail:
    """Incremental JSONL tailer: offset + BYTES remainder, truncation-reset on shrink."""

    path: str
    offset: int = 0
    remainder: bytes = b""
    #: Text of the last KNOWN-LOSSY read — bytes were measured as pending and could
    #: not be fetched (a share lock / permission denial on ``open``). Reset at the top
    #: of every :meth:`read_new`, so it always describes the LAST attempt only. A
    #: vanished file (the ``getsize`` branch) is deliberately NOT recorded here:
    #: nothing proves data was lost, and a rotated-away stream would otherwise pin its
    #: consumer permanently stale.
    read_error: str | None = None

    def read_new(self) -> list[str]:
        """The complete, non-blank lines appended since the last call (never raises).

        An unreadable file still yields ``[]`` — callers never see an exception — but
        :attr:`read_error` is set, so "read succeeded with nothing appended" stays
        distinguishable from "the read FAILED". Collapsing the two is what let a
        share-locked stream be published as a fresh, healthy measurement.
        """
        self.read_error = None
        try:
            size = os.path.getsize(self.path)
        except OSError:
            return []
        if size < self.offset:  # truncated / rotated → restart from the top
            self.offset = 0
            self.remainder = b""
        if size == self.offset:
            return []
        try:
            with open(self.path, "rb") as fh:
                fh.seek(self.offset)
                chunk = fh.read()
                self.offset = fh.tell()
        except OSError as exc:
            self.read_error = str(exc)
            return []
        *lines, self.remainder = (self.remainder + chunk).split(b"\n")
        out: list[str] = []
        for raw in lines:
            text = raw.decode("utf-8", "replace").strip()
            if text:
                out.append(text)
        return out


# ---------------------------------------------------------------------------
# Parsers (redaction at ingest — every free-text field passes ``scrub``)
# ---------------------------------------------------------------------------


def load_stream_meta(path: str) -> dict:
    """Read a ``<name>.meta.json`` sidecar next to a stream file (``{}`` on any failure)."""
    side = str(Path(path).with_suffix("")) + ".meta.json"
    try:
        with open(side, encoding="utf-8", errors="replace") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def parse_stream_line(
    th: CodexThread, obj: dict, now: float, *, scrub: Scrub = _scrub
) -> None:
    """Fold one ``codex exec --json`` stream event into ``th`` (scrubbing free text)."""
    t = obj.get("type")
    if t == "monitor.meta":
        th.prompt = _keep(obj.get("prompt"), th.prompt, scrub)
        th.label = _keep(obj.get("label"), th.label, scrub)
        th.cwd = _keep(obj.get("cwd"), th.cwd, scrub)
        th.model = _keep(obj.get("model"), th.model, scrub)
        st = obj.get("started_at")
        if isinstance(st, (int, float)):
            th.start_ts = float(st)
        return
    if t == "thread.started":
        th.tid = _keep_id(obj.get("thread_id"), th.tid)
        if th.start_ts is None:
            th.start_ts = now
        return
    if t == "turn.started":
        th.turns += 1
        return
    if t in ("item.started", "item.completed"):
        item = obj.get("item")
        it = item if isinstance(item, dict) else {}
        itype = it.get("type")
        iid = str(it.get("id", ""))
        if itype == "command_execution":
            cmd = scrub(str(it.get("command", "")))
            if t == "item.started" or it.get("status", "") == "in_progress":
                ev = ToolEvent("cmd", "command", cmd, "running", None, now)
                th._inflight[iid] = ev
                th.add_event(ev)
            else:  # completed
                code = it.get("exit_code")
                status = "ok" if code == 0 else ("error" if code else "ok")
                ev = th._inflight.pop(iid, None)
                if ev is not None:
                    ev.status = status
                    ev.detail = cmd
                else:
                    th.add_event(ToolEvent("cmd", "command", cmd, status, None, now))
        elif itype == "mcp_tool_call":
            server = it.get("server", "")
            tool = it.get("tool", it.get("name", ""))
            th.tool_kind = th.tool_kind or "mcp"
            th.add_event(
                ToolEvent("tool", scrub(f"mcp {server}/{tool}"), "", "ok", None, now)
            )
        elif itype == "file_change":
            files = it.get("changes") or it.get("files") or ""
            th.add_event(
                ToolEvent("patch", "patch", scrub(str(files)), "ok", None, now)
            )
        elif itype == "web_search":
            query = scrub(str(it.get("query", "")))
            th.add_event(ToolEvent("tool", "web_search", query, "ok", None, now))
        elif itype == "reasoning" and t == "item.completed":
            text = scrub(str(it.get("text", "")))
            th.add_event(ToolEvent("think", "reasoning", text, "", None, now))
        elif itype == "agent_message" and t == "item.completed":
            text = scrub(str(it.get("text", "")))
            th.add_event(ToolEvent("msg", "message", text, "", None, now))
        elif itype == "error" and t == "item.completed":
            message = scrub(str(it.get("message", "")))
            th.add_event(ToolEvent("msg", "error", message, "error", None, now))
        return
    if t == "turn.completed":
        usage = obj.get("usage")
        u = usage if isinstance(usage, dict) else {}
        inc = (u.get("input_tokens", 0) or 0) + (u.get("output_tokens", 0) or 0)
        # usage is per-turn totals; keep the max seen as the running total. The stream
        # schema carries no separate cumulative, so the per-turn total also serves as the
        # context-occupancy numerator (ctx_tokens) — already NOT a cumulative sum.
        th.tokens_total = max(th.tokens_total, int(inc))
        th.ctx_tokens = max(th.ctx_tokens, int(inc))
        th.completed = True
        return
    if t in ("turn.failed", "turn.aborted"):
        th.aborted = True


def parse_rollout_line(th: CodexThread, obj: dict, *, scrub: Scrub = _scrub) -> None:
    """Fold one persisted rollout line into ``th`` (scrubbing free text)."""
    ttl = obj.get("type")
    payload = obj.get("payload")
    p = payload if isinstance(payload, dict) else {}
    lts = parse_iso(obj.get("timestamp", ""))
    if lts:
        th.last_ts = max(th.last_ts, lts)

    # capture the model wherever it appears
    m = p.get("model")
    if isinstance(m, str) and m:
        th.model = scrub(m)

    if ttl == "session_meta":
        th.tid = _keep_id(p.get("session_id"), th.tid)
        th.cwd = _keep(p.get("cwd"), th.cwd, scrub)
        if th.start_ts is None:
            th.start_ts = parse_iso(p.get("timestamp", "")) or lts
        cw = p.get("context_window")
        if isinstance(cw, int):
            th.ctx_window = cw
        return

    if ttl == "turn_context":
        th.cwd = _keep(p.get("cwd"), th.cwd, scrub)
        return

    if ttl == "event_msg":
        pt = p.get("type")
        if pt == "task_started":
            th.turns += 1
            st = p.get("started_at")
            if isinstance(st, (int, float)) and th.start_ts is None:
                th.start_ts = float(st)
            cw = p.get("model_context_window")
            if isinstance(cw, int):
                th.ctx_window = cw
            th.completed = False
            th.aborted = False
        elif pt == "user_message":
            if not th.prompt:
                th.prompt = scrub(str(p.get("message", "")))
        elif pt == "agent_message":
            message = scrub(str(p.get("message", "")))
            th.add_event(
                ToolEvent("msg", "message", message, "", None, lts or th.last_ts)
            )
        elif pt == "token_count":
            info_raw = p.get("info")
            info = info_raw if isinstance(info_raw, dict) else {}
            usage_raw = info.get("total_token_usage")
            usage = usage_raw if isinstance(usage_raw, dict) else {}
            tot = usage.get("total_tokens")
            if isinstance(tot, int):
                th.tokens_total = tot
            # context occupancy is the LAST turn's usage, never the cumulative
            # ``total_token_usage`` (which inflates ctx% toward 100% over a session).
            last_raw = info.get("last_token_usage")
            last = last_raw if isinstance(last_raw, dict) else {}
            ctx_tok = last.get("total_tokens")
            if isinstance(ctx_tok, int):
                th.ctx_tokens = ctx_tok
            cw = info.get("model_context_window")
            if isinstance(cw, int):
                th.ctx_window = cw
        elif pt == "mcp_tool_call_end":
            inv_raw = p.get("invocation")
            inv = inv_raw if isinstance(inv_raw, dict) else {}
            label = scrub(f"mcp {inv.get('server', '')}/{inv.get('tool', '')}")
            dur_raw = p.get("duration")
            dur = dur_raw if isinstance(dur_raw, dict) else {}
            secs = dur.get("secs", 0) + dur.get("nanos", 0) / 1e9 if dur else None
            res = p.get("result")
            status = "error" if (isinstance(res, dict) and res.get("Err")) else "ok"
            th.tool_kind = th.tool_kind or "mcp"
            th.add_event(ToolEvent("tool", label, "", status, secs, lts or th.last_ts))
        elif pt == "patch_apply_end":
            changes_raw = p.get("changes")
            changes = changes_raw if isinstance(changes_raw, dict) else {}
            names = scrub(", ".join(Path(k).name for k in changes))
            status = "ok" if p.get("success") else "error"
            th.add_event(
                ToolEvent("patch", "patch", names, status, None, lts or th.last_ts)
            )
        elif pt == "task_complete":
            th.completed = True
        elif pt == "turn_aborted":
            th.aborted = True
        return

    if ttl == "response_item":
        pt = p.get("type")
        if pt == "custom_tool_call":
            name = scrub(str(p.get("name", "tool")))
            th.tool_kind = th.tool_kind or name
            code = scrub(str(p.get("input", "")))
            raw = str(p.get("status", ""))
            status = (
                "ok"
                if raw == "completed"
                else ("running" if raw in ("", "in_progress") else raw)
            )
            th.add_event(ToolEvent("cmd", name, code, status, None, lts or th.last_ts))
        elif pt == "function_call":
            name = scrub(str(p.get("name", "fn")))
            args = scrub(str(p.get("arguments", "")))
            th.add_event(ToolEvent("tool", name, args, "ok", None, lts or th.last_ts))
        # reasoning / message / *_output are noise for the board; skip
        return


# ---------------------------------------------------------------------------
# Discovery defaults + the cross-tick poller
# ---------------------------------------------------------------------------


def default_stream_dir() -> str:
    """``$CODEX_STREAM_DIR``, else ``%TEMP%/codex-streams`` (``/tmp`` fallback)."""
    env = os.environ.get("CODEX_STREAM_DIR")
    if env:
        return env
    tmp = os.environ.get("TEMP") or os.environ.get("TMP") or "/tmp"
    return str(Path(tmp) / "codex-streams")


def default_sessions_dir() -> str:
    """``$CODEX_HOME/sessions``, else ``~/.codex/sessions``."""
    home = os.environ.get("CODEX_HOME")
    if home:
        return str(Path(home) / "sessions")
    return str(Path.home() / ".codex" / "sessions")


def _mtime(fp: Path) -> float | None:
    """``st_mtime`` of ``fp``, ``None`` when it vanished mid-glob."""
    try:
        return fp.stat().st_mtime
    except OSError:
        return None


class Poller:
    """Holds the thread + tail maps ACROSS ticks; discover/ingest/prune are one tick.

    ``clock`` and ``scrub`` are injectable seams (tests pin time and assert the ingest
    redaction boundary); the defaults are always ``time.time`` and the real redactor.
    """

    def __init__(
        self,
        stream_dir: str,
        sessions_dir: str,
        *,
        since_min: float = 30.0,
        max_threads: int = 12,
        clock: Callable[[], float] = time.time,
        scrub: Scrub = _scrub,
    ) -> None:
        self.stream_dir = Path(stream_dir)
        self.sessions_dir = Path(sessions_dir)
        self.since_min = since_min
        self.max_threads = max_threads
        self._clock = clock
        self._scrub = scrub
        self.threads: dict[str, CodexThread] = {}
        self.tails: dict[str, Tail] = {}

    # ---- discovery -------------------------------------------------------
    def discover(self) -> None:
        """Register new stream files (always) + rollouts modified in-window (capped)."""
        cutoff = self._clock() - self.since_min * 60.0
        if self.stream_dir.is_dir():
            for fp in sorted(self.stream_dir.glob("*.jsonl")):
                key = "stream:" + fp.name
                if key in self.threads:
                    continue
                th = CodexThread(
                    key=key, source="stream", path=str(fp), label=self._scrub(fp.stem)
                )
                meta = load_stream_meta(str(fp))
                if meta:
                    th.prompt = _keep(meta.get("prompt"), th.prompt, self._scrub)
                    th.label = _keep(meta.get("label"), th.label, self._scrub)
                    th.cwd = _keep(meta.get("cwd"), th.cwd, self._scrub)
                    th.model = _keep(meta.get("model"), th.model, self._scrub)
                    st = meta.get("started_at")
                    if isinstance(st, (int, float)):
                        th.start_ts = float(st)
                self.threads[key] = th
                self.tails[key] = Tail(str(fp))
        if self.sessions_dir.is_dir():
            rollouts: list[tuple[float, str]] = []
            for fp in self.sessions_dir.glob("*/*/*/rollout-*.jsonl"):
                mt = _mtime(fp)
                if mt is None or mt < cutoff:
                    continue
                rollouts.append((mt, str(fp)))
            # newest first; path tiebreak keeps the cap deterministic across platforms
            rollouts.sort(key=lambda pair: (-pair[0], pair[1]))
            for _mt, path in rollouts[: self.max_threads]:
                key = "rollout:" + Path(path).name
                if key in self.threads:
                    continue
                self.threads[key] = CodexThread(key=key, source="rollout", path=path)
                self.tails[key] = Tail(path)

    # ---- ingest ----------------------------------------------------------
    def ingest(self) -> None:
        """Drain every tail; dispatch each JSON object line to its schema parser."""
        now = self._clock()
        for key, tail in self.tails.items():
            th = self.threads.get(key)
            if th is None:
                continue
            for line in tail.read_new():
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(obj, dict):
                    continue
                if th.source == "stream":
                    parse_stream_line(th, obj, now, scrub=self._scrub)
                    th.last_ts = now  # stream lines carry no ts; arrival == activity
                else:
                    parse_rollout_line(th, obj, scrub=self._scrub)

    def read_errors(self) -> tuple[tuple[str, str], ...]:
        """``(thread key, error text)`` for every tail whose LAST drain lost bytes.

        Empty when the last :meth:`ingest` reached every registered source. A non-empty
        result means the tick could not read known-pending bytes, so whatever the caller
        publishes is a PARTIAL measurement carrying retained last-good state for those
        threads — never a fresh one.
        """
        out: list[tuple[str, str]] = []
        for key, tail in self.tails.items():
            err = tail.read_error
            if err is not None:
                out.append((key, err))
        return tuple(out)

    # ---- prune -----------------------------------------------------------
    def prune(self) -> None:
        """Drop rollout threads quiet beyond the window (streams are kept forever)."""
        cutoff = self._clock() - self.since_min * 60.0
        dead = [
            key
            for key, th in self.threads.items()
            if th.source == "rollout" and th.last_ts and th.last_ts < cutoff
        ]
        for key in dead:
            self.threads.pop(key, None)
            self.tails.pop(key, None)


# ---------------------------------------------------------------------------
# Board rendering (ANSI-free; the colour table is separate, like agent_tail's)
# ---------------------------------------------------------------------------

_STATUS_ORDER = {"running": 0, "idle": 1, "aborted": 2, "done": 3}
_STATUS_GLYPH = {"running": "●", "idle": "○", "done": "✔", "aborted": "✘"}


def status_counts(threads: Iterable[CodexThread]) -> dict[str, int]:
    """Per-status thread counts (all four statuses always present)."""
    counts = {"running": 0, "idle": 0, "done": 0, "aborted": 0}
    for th in threads:
        counts[th.status] = counts.get(th.status, 0) + 1
    return counts


def board_line(th: CodexThread, now: float) -> str:
    """One ANSI-free board line: status, name, meta, timers, tokens/turns/tools."""
    glyph = _STATUS_GLYPH.get(th.status, "?")
    elapsed = (now - th.start_ts) if th.start_ts else None
    idle = (now - th.last_ts) if th.last_ts else None
    bits = " · ".join(b for b in (th.model, th.tool_kind, th.source) if b)
    label = ctx_label(ctx_gauge(th.ctx_tokens, th.ctx_window))
    ctx = f" {label}" if label else ""
    return (
        f"{glyph} [{th.status.upper()}] {th.name()}  {bits}  "
        f"{fmt_dur(elapsed)} elapsed · {fmt_dur(idle)} idle  "
        f"{fmt_tokens(th.tokens_total)} tok{ctx} · {th.turns} turns · {th.tool_count} tools"
    )


def frame_rows(
    threads: Iterable[CodexThread], now: float, width: int
) -> list[tuple[str, str]]:
    """``(line, status)`` rows — a board line + an indented prompt line per thread.

    Sorted running → idle → aborted → done, most-recent first within a status, with a
    ``key`` tiebreak for determinism. The status accompanies each row so the ANSI live
    view can ``paint`` it; the cockpit uses the plain lines as-is.
    """
    ordered = sorted(
        threads,
        key=lambda th: (_STATUS_ORDER.get(th.status, 4), -(th.last_ts or 0.0), th.key),
    )
    rows: list[tuple[str, str]] = []
    for th in ordered:
        rows.append((clip(board_line(th, now), width), th.status))
        prompt = th.prompt or "(prompt not captured)"
        rows.append(("    " + clip(prompt, max(0, width - 4)), "dim"))
    return rows


def render_frame(threads: Iterable[CodexThread], now: float, width: int) -> list[str]:
    """A full ANSI-free frame: summary header + the ``frame_rows`` lines."""
    threads = list(threads)
    counts = status_counts(threads)
    out = [
        f"CODEX THREADS  {counts['running']} run · {counts['idle']} idle · "
        f"{counts['done']} done · {counts['aborted']} aborted"
    ]
    if not threads:
        out.append("  (no codex threads: waiting for stream files / recent rollouts)")
        return out
    out.extend(row for row, _status in frame_rows(threads, now, width))
    return out


# ── ANSI table (separate from the pure renderers, like agent_tail's constants) ──
CSI = "\x1b["
RESET = CSI + "0m"
COL = {
    "running": CSI + "1;32m",
    "idle": CSI + "1;33m",
    "done": CSI + "1;36m",
    "aborted": CSI + "1;31m",
    "dim": CSI + "2;37m",
}


def paint(text: str, status: str) -> str:
    """Wrap ``text`` in the ANSI colour for ``status`` (dim for unknown/aux rows)."""
    return COL.get(status, COL["dim"]) + text + RESET


def _live_step(
    poller: Poller, now: float, width: int, *, idle_s: float = 12.0
) -> list[str]:
    """One fully-covered tick: discover → ingest → prune → recompute → frame."""
    poller.discover()
    poller.ingest()
    poller.prune()
    for th in poller.threads.values():
        th.recompute_status(now, idle_s)
    return render_frame(poller.threads.values(), now, width)


# ---------------------------------------------------------------------------
# Interactive shell + CLI
# ---------------------------------------------------------------------------


def run_live(  # pragma: no cover -- interactive ANSI full-screen loop (VT enable + q-poll + sleep)
    poller: Poller,
    *,
    idle_s: float,
    interval: float,
    width: int,
    clock: Callable[[], float] = time.time,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Full-screen ANSI redraw loop (q / Ctrl-C to quit). The ONLY uncovered shell."""

    def enable_vt() -> None:
        if os.name != "nt":
            return
        try:
            ctypes = importlib.import_module("ctypes")
            k = ctypes.windll.kernel32
            for handle_id in (-11, -12):  # stdout, stderr
                h = k.GetStdHandle(handle_id)
                mode = ctypes.c_uint32()
                if k.GetConsoleMode(h, ctypes.byref(mode)):
                    k.SetConsoleMode(h, mode.value | 0x0004)  # VT PROCESSING
        except Exception:
            pass

    def quit_pressed() -> bool:
        try:
            msvcrt = importlib.import_module("msvcrt")
            while msvcrt.kbhit():
                if msvcrt.getwch().lower() == "q":
                    return True
        except Exception:
            pass
        return False

    enable_vt()
    sys.stdout.write(CSI + "2J" + CSI + "?25l")  # clear + hide cursor
    try:
        while True:
            now = clock()
            frame = _live_step(poller, now, width, idle_s=idle_s)
            threads = list(poller.threads.values())
            lines = [paint(frame[0] + "  (q=quit)", "dim")]
            if threads:
                lines.extend(
                    paint(row, status)
                    for row, status in frame_rows(threads, now, width)
                )
            else:
                lines.extend(frame[1:])
            sys.stdout.write(CSI + "H")
            for line in lines:
                sys.stdout.write(CSI + "2K" + line + "\r\n")
            sys.stdout.write(CSI + "0J")  # clear below
            sys.stdout.flush()
            slept = 0.0
            while slept < interval:
                if quit_pressed():
                    return 0
                sleep(0.1)
                slept += 0.1
    except KeyboardInterrupt:
        return 0
    finally:
        sys.stdout.write(CSI + "?25h" + RESET + "\r\n")  # show cursor
        sys.stdout.flush()


def main(
    argv: list[str] | None = None,
    *,
    out: Callable[[str], None] = print,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.time,
    live: Callable[..., int] = run_live,
) -> int:
    """CLI: ``--once`` renders one frame through ``out``; otherwise hands off to ``live``.

    ``out`` / ``sleep`` / ``clock`` / ``live`` are injected seams so tests cover the
    argparse surface and both modes without a real terminal loop.
    """
    ap = argparse.ArgumentParser(
        description="Live board for OpenAI Codex threads (relay stream files + rollouts)."
    )
    ap.add_argument(
        "--stream-dir",
        default=None,
        help="codex exec --json stream dir (default: $CODEX_STREAM_DIR or %%TEMP%%/codex-streams)",
    )
    ap.add_argument(
        "--sessions-dir",
        default=None,
        help="codex rollout sessions dir (default: $CODEX_HOME/sessions or ~/.codex/sessions)",
    )
    ap.add_argument(
        "--since-min",
        type=float,
        default=30.0,
        help="only track rollouts modified within this many minutes",
    )
    ap.add_argument(
        "--idle",
        type=float,
        default=12.0,
        help="seconds of silence before a thread is 'idle'",
    )
    ap.add_argument(
        "--interval", type=float, default=1.0, help="refresh interval in seconds"
    )
    ap.add_argument(
        "--max-threads", type=int, default=12, help="max rollout threads to track"
    )
    ap.add_argument("--width", type=int, default=120, help="board width in columns")
    ap.add_argument(
        "--once", action="store_true", help="render a single frame and exit"
    )
    args = ap.parse_args(argv)
    poller = Poller(
        args.stream_dir or default_stream_dir(),
        args.sessions_dir or default_sessions_dir(),
        since_min=args.since_min,
        max_threads=args.max_threads,
        clock=clock,
    )
    if args.once:
        for line in _live_step(poller, clock(), args.width, idle_s=args.idle):
            out(line)
        return 0
    return live(
        poller,
        idle_s=args.idle,
        interval=args.interval,
        width=args.width,
        clock=clock,
        sleep=sleep,
    )


if __name__ == "__main__":  # pragma: no cover -- module CLI entrypoint
    raise SystemExit(main())
