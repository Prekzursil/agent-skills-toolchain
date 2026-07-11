"""Orchestration behind the MCP tools — pure ``args → dict`` over the core.

Every function reuses the SAME building blocks the CLI does:

* :func:`probes.templates.build_from_template` to stamp a :class:`TaskSpec`,
* :func:`cli.store.load_specs` / :func:`cli.store.save_specs` for registry I/O,
* :func:`cli.engine.snapshot` for the one-shot poll → :class:`TaskView` fold,
* :class:`core.history.HistoryStore` for the task-type priors.

Results are terminal-state dicts (``{"ok": True, ...}`` or ``{"ok": False,
"error": ...}``) so the server layer never has to interpret exceptions. The
filesystem seam is a registry *path* (tests point it at ``tmp_path``); the poll
seam is the injectable ``snapshot_fn`` (default :func:`cli.engine.snapshot`), so
100 % branch coverage is reachable without real logs, network, or clocks.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Protocol

from core.history import HistoryStore
from core.models import TaskSpec
from core.registry import RegistryError
from probes.templates import TemplateError, build_from_template

from cli import engine, store
from cli.status import TaskView

DEFAULT_REGISTRY = "taskwatch.toml"


class SnapshotFn(Protocol):
    """The subset of :func:`cli.engine.snapshot` these tools depend on."""

    def __call__(
        self,
        specs: Sequence[TaskSpec],
        *,
        priors: Mapping[str, float] | None = ...,
        stall_after_s: float = ...,
    ) -> list[TaskView]: ...


def _err(message: str) -> dict[str, object]:
    """A uniform failure envelope (never raises out of a tool)."""
    return {"ok": False, "error": message}


def _find(specs: list[TaskSpec], task_id: str) -> TaskSpec | None:
    """Return the spec whose id matches ``task_id``, or ``None``."""
    for spec in specs:
        if spec.id == task_id:
            return spec
    return None


def _load_priors(history: str, specs: Sequence[TaskSpec]) -> dict[str, float]:
    """Build a task-type → prior-p50 map from the sqlite history (if given)."""
    if not history:
        return {}
    priors: dict[str, float] = {}
    with HistoryStore(history) as hist:
        for spec in specs:
            prior = hist.prior(spec.history_key)
            if prior is not None:
                priors[spec.history_key] = prior.p50
    return priors


def register_task(
    template: str,
    task_id: str,
    config: dict[str, object] | None = None,
    *,
    remediate: bool = False,
    registry: str = DEFAULT_REGISTRY,
) -> dict[str, object]:
    """Stamp a :class:`TaskSpec` from a template and append it to the registry.

    ``remediate`` is the two-tier opt-in (grill S3): a task is observe-only
    unless this is explicitly set. Returns ``ok: False`` for an unknown template,
    missing required config, a malformed registry, or a duplicate id.
    """
    try:
        spec = build_from_template(template, task_id, config, remediate=remediate)
    except TemplateError as exc:
        return _err(str(exc))
    path = Path(registry)
    try:
        specs = store.load_specs(path)
        specs = store.append_spec(specs, spec)
    except RegistryError as exc:
        return _err(str(exc))
    store.save_specs(path, specs)
    return {"ok": True, "task": spec.to_dict(), "registry": str(path)}


def list_tasks(registry: str = DEFAULT_REGISTRY) -> dict[str, object]:
    """Return every registered task's declarative spec (empty list if none)."""
    try:
        specs = store.load_specs(Path(registry))
    except RegistryError as exc:
        return _err(str(exc))
    return {"ok": True, "tasks": [spec.to_dict() for spec in specs]}


def status(
    registry: str = DEFAULT_REGISTRY,
    *,
    task_id: str = "",
    history: str = "",
    stall_after_s: float = engine.DEFAULT_STALL_AFTER_S,
    snapshot_fn: SnapshotFn = engine.snapshot,
) -> dict[str, object]:
    """Poll the registry once and return one status view per task.

    An empty ``task_id`` reports every task; a non-empty one filters to that
    task (and reports ``ok: False`` if it is not registered). ``history`` points
    at the sqlite priors DB so a not-yet-measurable ETA can fall back to a PRIOR.
    """
    try:
        specs = store.load_specs(Path(registry))
    except RegistryError as exc:
        return _err(str(exc))
    if task_id:
        specs = [spec for spec in specs if spec.id == task_id]
        if not specs:
            return _err(f"unknown task id '{task_id}'")
    priors = _load_priors(history, specs)
    views = snapshot_fn(specs, priors=priors, stall_after_s=stall_after_s)
    return {"ok": True, "tasks": [view.to_dict() for view in views]}


def attach_watch(
    task_id: str,
    *,
    remediate: bool | None = None,
    registry: str = DEFAULT_REGISTRY,
    history: str = "",
    stall_after_s: float = engine.DEFAULT_STALL_AFTER_S,
    snapshot_fn: SnapshotFn = engine.snapshot,
) -> dict[str, object]:
    """Attach an active watch to a registered task and return its current view.

    When ``remediate`` is provided it flips the per-task tier-2 opt-in and
    persists it (grill S3); when ``None`` the registry is left untouched. Either
    way the task is polled once so the caller starts watching immediately.
    """
    path = Path(registry)
    try:
        specs = store.load_specs(path)
    except RegistryError as exc:
        return _err(str(exc))
    target = _find(specs, task_id)
    if target is None:
        return _err(f"unknown task id '{task_id}'")
    if remediate is not None:
        target.remediate = remediate
        store.save_specs(path, specs)
    priors = _load_priors(history, [target])
    views = snapshot_fn([target], priors=priors, stall_after_s=stall_after_s)
    return {
        "ok": True,
        "task_id": task_id,
        "watching": True,
        "remediate": target.remediate,
        "status": views[0].to_dict(),
    }


def set_notify(
    task_id: str,
    channels: list[str],
    *,
    registry: str = DEFAULT_REGISTRY,
) -> dict[str, object]:
    """Replace a task's notify channels (e.g. ``["terminal", "stall"]``).

    Reports ``ok: False`` for a malformed registry or an unknown task id.
    """
    path = Path(registry)
    try:
        specs = store.load_specs(path)
    except RegistryError as exc:
        return _err(str(exc))
    target = _find(specs, task_id)
    if target is None:
        return _err(f"unknown task id '{task_id}'")
    target.notify = list(channels)
    store.save_specs(path, specs)
    return {"ok": True, "task": target.to_dict()}
