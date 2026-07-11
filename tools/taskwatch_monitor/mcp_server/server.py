"""MCP server exposing taskwatch_monitor over stdio (FastMCP).

Five tools mirror the CLI surface but for an agent host:

* ``register_task`` — stamp a task from a template into the registry,
* ``list_tasks``    — enumerate the declarative registry,
* ``status``        — one-shot poll → status view(s) (optionally one task),
* ``attach_watch``  — attach a live watch (optionally flip the remediate opt-in),
* ``set_notify``    — set a task's notify channels.

Each wrapper is a one-liner that delegates to :mod:`mcp_server.logic`; the
delegation is the only thing tested here (logic is mocked), exactly like the
scholarly-access-mcp template. The tools never raise: ``logic`` returns a
terminal-state ``{"ok": ...}`` envelope for every path.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from cli import engine

from . import logic

mcp = FastMCP("taskwatch-monitor")


@mcp.tool()
def register_task(
    template: str,
    task_id: str,
    config: dict[str, object] | None = None,
    remediate: bool = False,
    registry: str = logic.DEFAULT_REGISTRY,
) -> dict[str, object]:
    """Register a task from a named template (see probes.templates) into the
    registry TOML. ``config`` supplies the template's required keys (e.g.
    ``{"path": "/logs/run.log"}``); ``remediate`` opts the task into tier-2
    remediation. Spec: register_task."""
    return logic.register_task(
        template, task_id, config, remediate=remediate, registry=registry
    )


@mcp.tool()
def list_tasks(registry: str = logic.DEFAULT_REGISTRY) -> dict[str, object]:
    """List every registered task's declarative spec from the registry TOML.
    Spec: list."""
    return logic.list_tasks(registry)


@mcp.tool()
def status(
    registry: str = logic.DEFAULT_REGISTRY,
    task_id: str = "",
    history: str = "",
    stall_after_s: float = engine.DEFAULT_STALL_AFTER_S,
) -> dict[str, object]:
    """Poll the registry once and return a status view per task (BLIND-aware,
    honest p50/p90 ETA). An empty ``task_id`` reports all tasks; a non-empty one
    filters to that task. ``history`` is a sqlite priors DB path. Spec: status."""
    return logic.status(
        registry, task_id=task_id, history=history, stall_after_s=stall_after_s
    )


@mcp.tool()
def attach_watch(
    task_id: str,
    remediate: bool | None = None,
    registry: str = logic.DEFAULT_REGISTRY,
    history: str = "",
    stall_after_s: float = engine.DEFAULT_STALL_AFTER_S,
) -> dict[str, object]:
    """Attach a live watch to a registered task and return its current status
    view. Passing ``remediate`` flips the per-task tier-2 opt-in and persists it;
    omitting it leaves the registry untouched. Spec: attach_watch."""
    return logic.attach_watch(
        task_id,
        remediate=remediate,
        registry=registry,
        history=history,
        stall_after_s=stall_after_s,
    )


@mcp.tool()
def set_notify(
    task_id: str,
    channels: list[str],
    registry: str = logic.DEFAULT_REGISTRY,
) -> dict[str, object]:
    """Set a task's notify channels (e.g. ``["terminal", "first-progress",
    "stall"]``), replacing any existing set. Spec: set_notify."""
    return logic.set_notify(task_id, channels, registry=registry)


def main() -> None:
    mcp.run()


if __name__ == "__main__":  # pragma: no cover -- module entrypoint
    main()
