"""Codex rollout adapter for the generic :mod:`monitorcore` contract.

``CodexSource`` materializes the newest ``rollout-*.jsonl`` beneath the Codex session date
tree into one typed :class:`CodexPayload`, then exposes it through the same non-throwing
``MonitorSource`` surface as ``WfmonSource``.  It intentionally does not port the standalone
monitor's stream relay, incremental tail map, pruning, terminal sizing, or key loop; the shared
:mod:`monitorcore.live` runner now owns the launchable poll/render lifecycle.

The rollout event mapping is ported from ``parse_rollout_line`` in the preserved standalone
monitor at ``C:/Users/Prekzursil/.local/opt/mingle/monitor/codex_monitor.py``.  Adapter changes
are deliberate: an aborted turn has native status ``failed`` and coarse ``SourceState.ERROR``;
cumulative token display stays separate from context occupancy, whose numerator is strictly
``last_token_usage.total_tokens`` (never cumulative ``total_token_usage``).
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

from .contract import Alert, Snapshot, SourceState
from .live import run
from .redact import redact
from .report_doc import ReportDoc, Section, Table

__all__ = [
    "CodexPayload",
    "CodexSource",
    "CodexToolCall",
    "default_sessions_dir",
    "latest_rollout_path",
    "main",
    "parse_rollout_line",
    "read_latest_rollout",
    "read_rollout",
]

_ID = "codex"


@dataclass(frozen=True)
class CodexToolCall:
    """One Codex command/tool/patch event retained in rollout order."""

    kind: str
    label: str
    detail: str = ""
    status: str = ""
    duration_s: float | None = None
    ts: float | None = None


@dataclass(frozen=True)
class CodexPayload:
    """Typed native model for one fully materialized Codex rollout."""

    path: str = ""
    session_id: str = ""
    cwd: str = ""
    model: str = ""
    prompt: str = ""
    last_message: str = ""
    started_at: float | None = None
    last_activity_at: float | None = None
    total_tokens: int = 0
    context_tokens: int = 0
    context_window: int = 0
    turns: int = 0
    tool_calls: tuple[CodexToolCall, ...] = ()
    status: str = "idle"

    @property
    def context_percent(self) -> int | None:
        """Current context occupancy, never cumulative session usage."""
        if not self.context_window:
            return None
        percent = int(self.context_tokens * 100 / self.context_window)
        return min(100, max(0, percent))


@dataclass
class _RolloutState:
    path: str
    session_id: str = ""
    cwd: str = ""
    model: str = ""
    prompt: str = ""
    last_message: str = ""
    started_at: float | None = None
    last_activity_at: float | None = None
    total_tokens: int = 0
    context_tokens: int = 0
    context_window: int = 0
    turns: int = 0
    active: bool = False
    completed: bool = False
    aborted: bool = False
    tool_calls: list[CodexToolCall] = field(default_factory=list)

    def payload(self) -> CodexPayload:
        if self.aborted:
            status = "failed"
        elif self.completed:
            status = "done"
        elif self.active:
            status = "running"
        else:
            status = "idle"
        return CodexPayload(
            path=self.path,
            session_id=self.session_id,
            cwd=self.cwd,
            model=self.model,
            prompt=self.prompt,
            last_message=self.last_message,
            started_at=self.started_at,
            last_activity_at=self.last_activity_at,
            total_tokens=self.total_tokens,
            context_tokens=self.context_tokens,
            context_window=self.context_window,
            turns=self.turns,
            tool_calls=tuple(self.tool_calls),
            status=status,
        )


Reader = Callable[[Path], CodexPayload]


def _as_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _parse_iso(value: object) -> float | None:
    """Parse an ISO-8601 timestamp, returning ``None`` for every invalid shape."""
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError, OverflowError):
        return None


def _set_int(state: _RolloutState, name: str, value: object) -> None:
    if isinstance(value, int):
        setattr(state, name, value)


def _custom_status(value: object) -> str:
    if value == "completed":
        return "ok"
    if value in (None, "", "in_progress"):
        return "running"
    return str(value)


def parse_rollout_line(state: _RolloutState, obj: dict[str, object]) -> None:
    """Apply one persisted Codex rollout record to ``state``.

    Unknown outer records and subtypes are harmless no-ops, matching the standalone parser's
    forward-compatible behavior while keeping the adapter materialization deterministic.
    """
    outer = obj.get("type")
    payload = _as_dict(obj.get("payload"))
    line_ts = _parse_iso(obj.get("timestamp"))
    if line_ts is not None:
        state.last_activity_at = max(state.last_activity_at or line_ts, line_ts)

    model = payload.get("model")
    if isinstance(model, str) and model:
        state.model = model

    if outer == "session_meta":
        session_id = payload.get("session_id") or payload.get("id")
        if isinstance(session_id, str) and session_id:
            state.session_id = session_id
        cwd = payload.get("cwd")
        if isinstance(cwd, str) and cwd:
            state.cwd = cwd
        if state.started_at is None:
            state.started_at = _parse_iso(payload.get("timestamp")) or line_ts
        _set_int(state, "context_window", payload.get("context_window"))
        return

    if outer == "turn_context":
        cwd = payload.get("cwd")
        if isinstance(cwd, str) and cwd:
            state.cwd = cwd
        return

    if outer == "event_msg":
        event_type = payload.get("type")
        if event_type == "task_started":
            state.turns += 1
            started_at = payload.get("started_at")
            if state.started_at is None and isinstance(started_at, (int, float)):
                state.started_at = float(started_at)
            _set_int(state, "context_window", payload.get("model_context_window"))
            state.active = True
            state.completed = False
            state.aborted = False
        elif event_type == "user_message":
            message = payload.get("message")
            if not state.prompt and isinstance(message, str):
                state.prompt = message
        elif event_type == "agent_message":
            message = payload.get("message")
            if isinstance(message, str):
                state.last_message = message
        elif event_type == "token_count":
            info = _as_dict(payload.get("info"))
            total = _as_dict(info.get("total_token_usage")).get("total_tokens")
            context = _as_dict(info.get("last_token_usage")).get("total_tokens")
            _set_int(state, "total_tokens", total)
            _set_int(state, "context_tokens", context)
            _set_int(state, "context_window", info.get("model_context_window"))
        elif event_type == "mcp_tool_call_end":
            invocation = _as_dict(payload.get("invocation"))
            server = str(invocation.get("server") or "")
            tool = str(invocation.get("tool") or "")
            duration = _as_dict(payload.get("duration"))
            seconds = duration.get("secs")
            nanos = duration.get("nanos")
            duration_s = (
                float(seconds) + float(nanos) / 1e9
                if isinstance(seconds, (int, float)) and isinstance(nanos, (int, float))
                else None
            )
            result = _as_dict(payload.get("result"))
            status = "error" if result.get("Err") else "ok"
            state.tool_calls.append(
                CodexToolCall(
                    kind="tool",
                    label=f"mcp {server}/{tool}",
                    status=status,
                    duration_s=duration_s,
                    ts=line_ts,
                )
            )
        elif event_type == "patch_apply_end":
            changes = payload.get("changes")
            names = (
                ", ".join(Path(str(name)).name for name in changes)
                if isinstance(changes, dict)
                else ""
            )
            state.tool_calls.append(
                CodexToolCall(
                    kind="patch",
                    label="patch",
                    detail=names,
                    status="ok" if payload.get("success") else "error",
                    ts=line_ts,
                )
            )
        elif event_type == "task_complete":
            state.active = False
            state.completed = True
        elif event_type == "turn_aborted":
            state.active = False
            state.aborted = True
        return

    if outer == "response_item":
        item_type = payload.get("type")
        if item_type == "custom_tool_call":
            state.tool_calls.append(
                CodexToolCall(
                    kind="command",
                    label=str(payload.get("name") or "tool"),
                    detail=str(payload.get("input") or ""),
                    status=_custom_status(payload.get("status")),
                    ts=line_ts,
                )
            )
        elif item_type == "function_call":
            state.tool_calls.append(
                CodexToolCall(
                    kind="tool",
                    label=str(payload.get("name") or "fn"),
                    detail=str(payload.get("arguments") or ""),
                    status="ok",
                    ts=line_ts,
                )
            )


def read_rollout(path: str | os.PathLike[str]) -> CodexPayload:
    """Materialize one rollout file, tolerating blank/malformed active-write lines."""
    rollout = Path(path)
    state = _RolloutState(path=str(rollout))
    with rollout.open("r", encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                parse_rollout_line(state, obj)
    return state.payload()


def latest_rollout_path(sessions_dir: str | os.PathLike[str]) -> Path:
    """Return the deterministic newest readable ``rollout-*.jsonl`` in the date tree."""
    candidates: list[tuple[float, str, Path]] = []
    for path in Path(sessions_dir).glob("*/*/*/rollout-*.jsonl"):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        candidates.append((mtime, str(path), path))
    if not candidates:
        raise FileNotFoundError(f"no rollout-*.jsonl files under {sessions_dir}")
    return max(candidates)[2]


def read_latest_rollout(sessions_dir: Path) -> CodexPayload:
    """Select and materialize the newest rollout beneath ``sessions_dir``."""
    return read_rollout(latest_rollout_path(sessions_dir))


def default_sessions_dir() -> Path:
    """Codex session root, honoring ``CODEX_HOME`` like the standalone monitor."""
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        return Path(codex_home) / "sessions"
    return Path.home() / ".codex" / "sessions"


def _redact(text: str) -> str:
    return redact(text, enabled=True)[0]


def _source_state(status: str) -> SourceState:
    return {
        "running": SourceState.RUNNING,
        "done": SourceState.DONE,
        "failed": SourceState.ERROR,
    }.get(status, SourceState.IDLE)


class CodexSource:
    """A ``MonitorSource`` over the single newest persisted Codex rollout."""

    id = _ID

    def __init__(
        self,
        sessions_dir: str | os.PathLike[str] | None = None,
        *,
        idle_s: float = 12.0,
        reader: Reader = read_latest_rollout,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._sessions_dir = (
            default_sessions_dir() if sessions_dir is None else Path(sessions_dir)
        )
        self._idle_s = idle_s
        self._reader = reader
        self._clock = clock
        self._last: Snapshot[CodexPayload] | None = None

    def poll(self) -> Snapshot[CodexPayload]:
        """Read one snapshot; ordinary failures become stale/unreachable and never escape."""
        ts = self._clock()
        try:
            payload = self._reader(self._sessions_dir)
        except Exception as exc:
            retained = self._last.payload if self._last is not None else CodexPayload()
            return Snapshot(
                source_id=self.id,
                ts=ts,
                reachable=False,
                stale=True,
                state=SourceState.UNREACHABLE,
                headline=self._headline(retained, SourceState.UNREACHABLE, str(exc)),
                payload=retained,
                age_s=None,
                error=str(exc),
            )
        age_s = (
            None
            if payload.last_activity_at is None
            else max(0.0, ts - payload.last_activity_at)
        )
        if payload.status == "running" and age_s is not None and age_s >= self._idle_s:
            payload = replace(payload, status="idle")
        state = _source_state(payload.status)
        snap = Snapshot(
            source_id=self.id,
            ts=ts,
            reachable=True,
            stale=False,
            state=state,
            headline=self._headline(payload, state, None),
            payload=payload,
            age_s=age_s,
            error=None,
        )
        self._last = snap
        return snap

    def _headline(
        self, payload: CodexPayload, state: SourceState, error: str | None
    ) -> str:
        if state == SourceState.UNREACHABLE:
            return _redact(f"codex unreachable: {error}")
        session = payload.session_id or Path(payload.path).stem or "thread"
        return _redact(
            f"codex {session} [{payload.status}] {payload.turns} turns / "
            f"{len(payload.tool_calls)} tools / {payload.total_tokens} tokens"
        )

    def render_native(self, snap: Snapshot[CodexPayload]) -> object:
        """Render one deterministic Codex-native text frame for the shared live loop."""
        payload = snap.payload
        if not payload.path:
            return snap.headline
        session = payload.session_id or Path(payload.path).stem
        display_status = (
            snap.state.value
            if snap.state in (SourceState.UNREACHABLE, SourceState.STALLED)
            else payload.status
        )
        context = (
            f"  ctx {payload.context_percent}%"
            if payload.context_percent is not None
            else ""
        )
        lines = [
            f"CODEX THREAD [{display_status}] {session}",
            f"prompt: {payload.prompt or '(not captured)'}",
            f"tokens: {payload.total_tokens}{context}  turns: {payload.turns}  "
            f"tools: {len(payload.tool_calls)}",
        ]
        if payload.last_message:
            lines.append(f"message: {payload.last_message}")
        for call in payload.tool_calls[-6:]:
            duration = "" if call.duration_s is None else f" {call.duration_s:.1f}s"
            detail = "" if not call.detail else f" {call.detail}"
            lines.append(f"{call.kind}: {call.label} [{call.status}]{duration}{detail}")
        return _redact("\n".join(lines))

    def export_model(self, snap: Snapshot[CodexPayload]) -> ReportDoc:
        """Map the native Codex thread onto the shared generic report document."""
        payload = snap.payload
        if not payload.path:
            return ReportDoc(title=_ID, generated_at="", subtitle=snap.headline)
        session = payload.session_id or Path(payload.path).stem
        context = (
            f" · ctx {payload.context_percent}%"
            if payload.context_percent is not None
            else ""
        )
        duration_ms = (
            max(0, int((payload.last_activity_at - payload.started_at) * 1000))
            if payload.started_at is not None and payload.last_activity_at is not None
            else 0
        )
        card = Section(
            title=session,
            anchor="codex-thread",
            card=True,
            badge=snap.state.value,
            model=payload.model,
            tokens=payload.total_tokens,
            tool_calls=len(payload.tool_calls),
            duration_ms=duration_ms,
            lead=f"{payload.turns} turns{context} · native {payload.status}",
            task=payload.prompt,
            output=payload.last_message,
        )
        table = Table(
            headers=("Kind", "Tool", "Status", "Detail"),
            rows=tuple(
                (call.kind, _redact(call.label), call.status, _redact(call.detail))
                for call in payload.tool_calls
            ),
        )
        generated_at = datetime.fromtimestamp(snap.ts, tz=timezone.utc).isoformat()
        return ReportDoc(
            title=f"Codex session {session}",
            generated_at=generated_at,
            subtitle=snap.headline,
            meta=(("Session", session), ("Path", _redact(payload.path))),
            active=snap.state in (SourceState.RUNNING, SourceState.IDLE),
            blocks=(
                Section(title="Thread", anchor="thread", index=1, children=(card,)),
                Section(title="Tool calls", anchor="tools", index=2, children=(table,)),
            ),
        )

    def headline(self, snap: Snapshot[CodexPayload]) -> str:
        return snap.headline

    def alert(self, snap: Snapshot[CodexPayload]) -> Alert | None:
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
                detail=_redact(snap.error or snap.payload.status),
                ts=snap.ts,
            )
        return None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Monitor the newest Codex rollout through monitorcore."
    )
    parser.add_argument(
        "--sessions-dir",
        default=str(default_sessions_dir()),
        help="Codex sessions root (default: CODEX_HOME/sessions or ~/.codex/sessions)",
    )
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument(
        "--idle",
        type=float,
        default=12.0,
        help="seconds of silence before a nonterminal turn is idle",
    )
    parser.add_argument("--once", action="store_true")
    return parser


def main(argv: list[str] | None = None, *, out: TextIO | None = None) -> int:
    """Thin ``mon codex`` composition: parse options, construct the adapter, run shared live."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.interval <= 0:
        parser.error("--interval must be greater than zero")
    if args.idle <= 0:
        parser.error("--idle must be greater than zero")
    source = CodexSource(sessions_dir=args.sessions_dir, idle_s=args.idle)
    return run(source, interval=args.interval, once=args.once, out=out)
