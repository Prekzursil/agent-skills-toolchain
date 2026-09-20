"""Snapshot engine — poll every registered task and assemble its view.

This is the thin I/O seam between the declarative registry and the pure
:mod:`cli.status` assembly: it builds each spec's adapter (:func:`core.adapters.adapter_from_spec`),
runs one ``poll()``, resolves the probe, and folds the result into a
:class:`~cli.status.TaskView`. Every real dependency (``fs``/``http_get``/
``pid_alive``/``clock``) is injected, so the whole engine reaches 100% branch
coverage with fakes and no real network/process/clock.

Stall detection here is the single-poll universal-liveness heuristic: a source
whose newest ``mtime`` has not advanced for ``stall_after_s`` is STALLED — never
silently "done" (grill S7). A blind poll suppresses the stall flag (the current
sample can't be trusted) while keeping the last frontier.
"""

from __future__ import annotations

import re
import sys
import time
from collections.abc import Mapping, Sequence

from core.adapters import (
    Clock,
    FileSystem,
    HttpGetter,
    PidProbe,
    adapter_from_spec,
)
from core.models import PollResult, TaskSpec
from probes.base import Probe, ProbeReading
from probes.generic import GenericLogfileProbe
from probes.registry import probe_for

from .status import TaskView, assemble_view

# A source untouched for this many seconds is treated as stalled (grill S7).
DEFAULT_STALL_AFTER_S = 300.0

# Shared stateless fallback probe when a spec names no (or an unknown) parser.
_GENERIC_PROBE: Probe = GenericLogfileProbe()


def resolve_probe(parser: str) -> Probe:
    """Return the probe a spec's ``parser`` selects, or the generic fallback."""
    probe = probe_for(parser)
    if probe is not None:
        return probe
    return _GENERIC_PROBE


def stall_flag(poll: PollResult, *, now: float, stall_after_s: float) -> bool:
    """True when the source's newest mtime is older than ``stall_after_s``.

    A blind poll or a source with no mtime signal is never flagged stalled — the
    absence of a change signal is not proof of a stall (grill S7).
    """
    if poll.blind:
        return False
    if poll.mtime is None:
        return False
    return (now - poll.mtime) >= stall_after_s


def _stall_after_for(spec: TaskSpec, default: float) -> float:
    """Per-task ``config.stall_after_s`` override, else the caller default."""
    value = spec.config.get("stall_after_s")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return float(value)


def _terminal_pattern_kwargs(spec: TaskSpec, probe: Probe) -> dict[str, str]:
    """Per-task ``config.terminal_pattern`` → generic-probe override kwarg.

    Only the generic probe accepts the override; other parsers get ``{}``.
    An unparseable pattern is dropped loudly (stderr note) rather than
    crashing the watch loop for every registered task.
    """
    if not isinstance(probe, GenericLogfileProbe):
        return {}
    pattern = spec.config.get("terminal_pattern")
    if not isinstance(pattern, str) or not pattern:
        return {}
    try:
        re.compile(pattern)
    except re.error as exc:
        print(
            f"taskwatch: invalid terminal_pattern for '{spec.id}' ({exc}); ignoring",
            file=sys.stderr,
        )
        return {}
    return {"terminal_pattern": pattern}


def poll_spec(
    spec: TaskSpec,
    *,
    fs: FileSystem | None = None,
    http_get: HttpGetter | None = None,
    pid_alive: PidProbe | None = None,
    clock: Clock = time.time,
) -> tuple[PollResult, ProbeReading]:
    """Poll one spec's source and lift its lines into a probe reading."""
    adapter = adapter_from_spec(
        spec, fs=fs, http_get=http_get, pid_alive=pid_alive, clock=clock
    )
    poll = adapter.poll()
    probe = resolve_probe(spec.parser)
    reading = probe.parse(poll.lines, **_terminal_pattern_kwargs(spec, probe))
    return poll, reading


def snapshot(
    specs: Sequence[TaskSpec],
    *,
    fs: FileSystem | None = None,
    http_get: HttpGetter | None = None,
    pid_alive: PidProbe | None = None,
    clock: Clock = time.time,
    now: float | None = None,
    started: Mapping[str, float] | None = None,
    priors: Mapping[str, float] | None = None,
    stall_after_s: float = DEFAULT_STALL_AFTER_S,
) -> list[TaskView]:
    """Poll every spec once and return one :class:`TaskView` per task.

    ``started`` maps a task id to its start epoch (for the elapsed-time ETA);
    ``priors`` maps a task-type (``spec.history_key``) to a prior duration in
    seconds. Both are optional — a task with neither yields an honest
    not-estimable ETA rather than a fabricated countdown (grill S8).
    """
    now_ts = clock() if now is None else now
    started_map = started or {}
    priors_map = priors or {}
    views: list[TaskView] = []
    for spec in specs:
        poll, reading = poll_spec(
            spec, fs=fs, http_get=http_get, pid_alive=pid_alive, clock=clock
        )
        stalled = not reading.terminal and stall_flag(
            poll, now=now_ts, stall_after_s=_stall_after_for(spec, stall_after_s)
        )
        progressing = poll.liveness and not poll.blind and not stalled
        start = started_map.get(spec.id)
        elapsed = None if start is None else now_ts - start
        prior = priors_map.get(spec.history_key)
        views.append(
            assemble_view(
                spec,
                poll,
                reading,
                progressing=progressing,
                stalled=stalled,
                elapsed_s=elapsed,
                prior_duration_s=prior,
            )
        )
    return views
