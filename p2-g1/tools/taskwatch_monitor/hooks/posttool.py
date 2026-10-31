"""Thin PostToolUse / longrun hook shell — registers a watch for a long op.

This is the harness-facing half of the auto-attach feature (grill G-4). A
PostToolUse hook (or the ``longrun`` wrapper) pipes a JSON event to this
module's :func:`main` on stdin; the module decides — via the *pure*
:mod:`hooks.attach` logic — whether the op is worth watching and, if so,
auto-registers a taskwatch task pointing at the op's log.

Everything that can go wrong is caught: a malformed event, a missing field, a
registration error, or any unexpected exception all resolve to exit 0 so the
hook is **fail-open** (AGENTS.md §6) — it can never block the tool it follows.
Dedup is persisted as a small JSON set (:func:`load_seen` / :func:`save_seen`)
so a re-fired event for an already-attached op is a no-op.

The I/O seams (stdin, env, clock, the register call) are all injected, so
:func:`run_hook` and :func:`main` reach 100 % branch coverage without a real
hook harness.
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from mcp_server import logic

from .attach import ATTACH_THRESHOLD_S, DEFAULT_WHITELIST, AttachOp, decide

# The template every auto-attached op is registered under: a generic logfile
# tail is the safe default for an arbitrary background op's log.
DEFAULT_TEMPLATE = "generic-logfile"

# Env knobs read by :func:`main` (the operator's control surface).
ENV_KILLSWITCH = "TASKWATCH_ATTACH_DISABLED"  # any truthy value hard-disables
ENV_REGISTRY = "TASKWATCH_REGISTRY"  # registry TOML the watch lands in
ENV_STATE = "TASKWATCH_ATTACH_STATE"  # dedup set path

# Where the dedup set lives when the operator does not override ENV_STATE.
DEFAULT_STATE_PATH = str(Path.home() / ".taskwatch" / "attached.json")

_TRUTHY = frozenset({"1", "true", "yes", "on"})


class _Readable(Protocol):
    """A text stream ``json.load`` can read (``sys.stdin`` / ``io.StringIO``)."""

    def read(self, size: int = ..., /) -> str: ...


class RegisterFn(Protocol):
    """The subset of :func:`mcp_server.logic.register_task` the shell calls."""

    def __call__(
        self,
        template: str,
        task_id: str,
        config: dict[str, object] | None = ...,
        *,
        registry: str = ...,
    ) -> dict[str, object]: ...


def _env_flag(env: Mapping[str, str], name: str) -> bool:
    """True when env var ``name`` holds a truthy string (``1``/``true``/…)."""
    return env.get(name, "").strip().lower() in _TRUTHY


def _elapsed(event: Mapping[str, object], now: float | None) -> float:
    """Resolve the op's elapsed seconds from the event.

    Prefers an explicit ``elapsed_s``; else derives it from ``started_at`` and
    ``now`` (the longrun wrapper supplies the former, a bare PostToolUse the
    latter). Falls back to ``0.0`` — which reads as below-threshold, so an event
    with no timing never auto-attaches.
    """
    raw = event.get("elapsed_s")
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)
    started = event.get("started_at")
    if (
        now is not None
        and isinstance(started, (int, float))
        and not isinstance(started, bool)
    ):
        return float(now) - float(started)
    return 0.0


def classify_kind(event: Mapping[str, object]) -> str:
    """Determine the op-kind for whitelist matching.

    An explicit ``op_kind`` (from the longrun wrapper) wins. Otherwise a
    background Bash call is mapped to ``bash-background``; anything else falls
    back to the lowercased tool name (which is not whitelisted, so it is
    rejected downstream rather than silently attached).
    """
    kind = event.get("op_kind")
    if kind:
        return str(kind)
    tool = str(event.get("tool_name", ""))
    tool_input = event.get("tool_input")
    if (
        tool == "Bash"
        and isinstance(tool_input, Mapping)
        and tool_input.get("run_in_background")
    ):
        return "bash-background"
    return tool.lower()


def extract_op(
    event: Mapping[str, object], *, now: float | None = None
) -> AttachOp | None:
    """Lift a PostToolUse event into an :class:`AttachOp`, or ``None``.

    Returns ``None`` when the event lacks the two things a watch needs — an
    ``op_id`` and a ``log_path`` — so an un-watchable op is skipped cleanly.
    """
    op_id = str(event.get("op_id") or "").strip()
    log_path = str(event.get("log_path") or "").strip()
    if not op_id or not log_path:
        return None
    return AttachOp(
        op_id=op_id,
        op_kind=classify_kind(event),
        elapsed_s=_elapsed(event, now),
        log_path=log_path,
    )


def load_seen(path: str) -> set[str]:
    """Load the dedup set; a missing or malformed file is an empty set."""
    file = Path(path)
    if not file.exists():
        return set()
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return set()
    if isinstance(data, list):
        return {str(item) for item in data}
    return set()


def save_seen(path: str, seen: set[str]) -> None:
    """Persist the dedup set (sorted, for a stable diff) to ``path``."""
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(sorted(seen)), encoding="utf-8")


def run_hook(
    event: Mapping[str, object],
    *,
    seen: set[str],
    register_fn: RegisterFn = logic.register_task,
    template: str = DEFAULT_TEMPLATE,
    registry: str = logic.DEFAULT_REGISTRY,
    whitelist: frozenset[str] = DEFAULT_WHITELIST,
    killswitch: bool = False,
    threshold_s: float = ATTACH_THRESHOLD_S,
    now: float | None = None,
) -> dict[str, object]:
    """Decide + (maybe) register for one event; mutates ``seen`` on attach.

    Returns a terminal-state dict: ``{"attached": bool, "reason": ...}``. On the
    attach path it registers the task and records the dedup key so a repeat event
    is a no-op.
    """
    op = extract_op(event, now=now)
    if op is None:
        return {"attached": False, "reason": "not-attachable"}
    verdict = decide(
        op,
        whitelist=whitelist,
        killswitch=killswitch,
        seen=seen,
        threshold_s=threshold_s,
    )
    if not verdict.attach:
        return {"attached": False, "reason": verdict.reason, "op_id": op.op_id}
    registered = register_fn(
        template, op.op_id, {"path": op.log_path}, registry=registry
    )
    seen.add(verdict.key)
    return {
        "attached": True,
        "reason": verdict.reason,
        "op_id": op.op_id,
        "registered": registered,
    }


def _run(stream: _Readable, env: Mapping[str, str], now: float | None) -> int:
    """Parse the event stream, run the hook, persist dedup — always exit 0."""
    try:
        event = json.load(stream)
    except (ValueError, OSError):
        return 0  # unparseable event never blocks the tool (fail-open)
    if not isinstance(event, Mapping):
        return 0
    now_ts = time.time() if now is None else now
    killswitch = _env_flag(env, ENV_KILLSWITCH)
    registry = env.get(ENV_REGISTRY, logic.DEFAULT_REGISTRY)
    seen_path = env.get(ENV_STATE, DEFAULT_STATE_PATH)
    seen = load_seen(seen_path)
    result = run_hook(
        event, seen=seen, registry=registry, killswitch=killswitch, now=now_ts
    )
    if result["attached"]:
        save_seen(seen_path, seen)
    return 0


def main(
    *,
    stdin: _Readable | None = None,
    env: Mapping[str, str] | None = None,
    now: float | None = None,
) -> int:
    """Hook entrypoint: read the JSON event on stdin, dispatch, exit 0.

    The whole body is wrapped so ANY error resolves to exit 0 — a hook must
    never block the tool it follows (AGENTS.md §6, fail-open).
    """
    stream = sys.stdin if stdin is None else stdin
    environ = os.environ if env is None else env
    try:
        return _run(stream, environ, now)
    except Exception:  # noqa: BLE001 - fail-open: a hook error must never block
        return 0


if __name__ == "__main__":  # pragma: no cover - module entrypoint guard
    raise SystemExit(main())
