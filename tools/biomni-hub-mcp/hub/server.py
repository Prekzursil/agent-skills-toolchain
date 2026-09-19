#!/usr/bin/env python3
"""biomni-hub — the unified Biomni MCP: 10 canonical tools + a backend catalog.

One MCP registration fronts BOTH Biomni backends behind the canonical 10-tool
surface (authored once in ``schema.py``). Each tool resolves a backend
out-of-band — env ``BIOMNI_BACKEND`` (default) plus an optional per-call
``backend`` argument — and dispatches to that backend's adapter
(``online_adapter`` / ``databricks_adapter``). Selection fails closed to
``online`` so existing callers that pass no ``backend`` keep working.

This module (component A1) wires the surface and the selector; it does NOT
implement backend internals — the adapters (A2 online, B1 databricks) do, to the
contract in ``INTERFACE.md``.

Modes::

    python server.py          # runtime stdio MCP (what ~/.mcp.json would run)

Tool names are PRE-NAMESPACED at the Biomni-Lab canonical names (no ``bm_``
prefix) so this hub can be mounted directly or behind cloud-hub without a
collision rename.
"""

from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from mcp.server.fastmcp import FastMCP  # noqa: E402

import backends  # noqa: E402
from schema import (  # noqa: E402
    BACKEND_NAMES,
    DEFAULT_BACKEND,
    BackendDescriptor,
    ToolEnvelope,
)

mcp = FastMCP("biomni-hub")


def _json(payload: object) -> str:
    """Serialize a ToolEnvelope / catalog payload to a JSON string."""
    if isinstance(payload, ToolEnvelope):
        return payload.model_dump_json()
    return json.dumps(payload, ensure_ascii=False, default=str)


def _dispatch(tool: str, backend_arg: str, call):
    """Resolve the backend, invoke ``call(backend)``, wrap failures as an envelope.

    ``call`` receives the resolved :class:`backends.BiomniBackend` and returns a
    :class:`ToolEnvelope`. Selection failures (adapter unavailable) and unhandled
    adapter exceptions are converted into an error envelope naming the *selected*
    backend, so the caller always gets a terminal-state JSON result.
    """
    selected = backends.select_backend_name(backend_arg)
    try:
        backend = backends.load_backend(selected)
        result = call(backend)
    except backends.AdapterUnavailable as exc:
        return _json(ToolEnvelope.failure(selected, tool, str(exc)))
    except Exception as exc:  # noqa: BLE001 - terminal-state error, never crash
        return _json(
            ToolEnvelope.failure(
                selected, tool, f"{type(exc).__name__}: {exc}"
            )
        )
    return _json(result)


# --------------------------------------------------------------------------- #
# The 10 canonical Biomni Lab tools (each dispatches through the selector)
# --------------------------------------------------------------------------- #
@mcp.tool()
def create_project(name: str, description: str = "", backend: str = "") -> str:
    """Create a Biomni project to group tasks and files.

    ``backend`` selects online | databricks (default: env ``BIOMNI_BACKEND``,
    else online). Returns a ToolEnvelope JSON with the created project in ``data``.
    """
    return _dispatch(
        "create_project", backend, lambda b: b.create_project(name, description)
    )


@mcp.tool()
def list_projects(backend: str = "") -> str:
    """List the projects in the active workspace (ToolEnvelope JSON)."""
    return _dispatch("list_projects", backend, lambda b: b.list_projects())


@mcp.tool()
def list_workspaces(backend: str = "") -> str:
    """List the workspaces available to the account (ToolEnvelope JSON)."""
    return _dispatch("list_workspaces", backend, lambda b: b.list_workspaces())


@mcp.tool()
def switch_workspace(workspace_id: str, backend: str = "") -> str:
    """Make a different workspace the active one (ToolEnvelope JSON)."""
    return _dispatch(
        "switch_workspace", backend, lambda b: b.switch_workspace(workspace_id)
    )


@mcp.tool()
def upload_file(
    local_path: str,
    project_id: str = "",
    destination: str = "",
    backend: str = "",
) -> str:
    """Upload a local file into a project's workspace (ToolEnvelope JSON).

    ``project_id`` defaults to the active project; ``destination`` is an optional
    backend-side name/subpath.
    """
    return _dispatch(
        "upload_file",
        backend,
        lambda b: b.upload_file(local_path, project_id, destination),
    )


@mcp.tool()
def start_new_task(
    project_id: str,
    prompt: str,
    model_profile: str = "standard",
    backend: str = "",
) -> str:
    """Start a new ASYNC agent task from a prompt; returns a task_id quickly.

    The task runs 30s to 10min+; poll ``wait_for_next_update`` until it reaches a
    terminal state. ``model_profile`` is the effort tier (standard | fast |
    premium). ToolEnvelope JSON; ``display_instruction`` / ``biomni_url`` may be set.
    """
    return _dispatch(
        "start_new_task",
        backend,
        lambda b: b.start_new_task(project_id, prompt, model_profile),
    )


@mcp.tool()
def send_message(task_id: str, content: str, backend: str = "") -> str:
    """Send a follow-up message into an existing task (ToolEnvelope JSON)."""
    return _dispatch(
        "send_message", backend, lambda b: b.send_message(task_id, content)
    )


@mcp.tool()
def wait_for_next_update(
    task_id: str,
    timeout_seconds: float = 60.0,
    since: int | None = None,
    backend: str = "",
) -> str:
    """Block until the task produces its next update or ``timeout_seconds`` elapses.

    The reliable poll for an async task — returns the newest status / messages in
    ``data`` and may carry ``display_instruction`` / ``biomni_url``. ``since`` is
    the optional resume cursor (pass the ``cursor`` from the previous update) so
    incremental polling never re-reads messages already seen.
    """
    return _dispatch(
        "wait_for_next_update",
        backend,
        lambda b: b.wait_for_next_update(task_id, timeout_seconds, since=since),
    )


@mcp.tool()
def list_tasks(project_id: str = "", backend: str = "") -> str:
    """List tasks (agent sessions), optionally project-scoped (ToolEnvelope JSON)."""
    return _dispatch("list_tasks", backend, lambda b: b.list_tasks(project_id))


@mcp.tool()
def list_result_files(task_id: str = "", backend: str = "") -> str:
    """List result files (name + size) produced by tasks (ToolEnvelope JSON)."""
    return _dispatch(
        "list_result_files", backend, lambda b: b.list_result_files(task_id)
    )


# --------------------------------------------------------------------------- #
# Control-plane: the backend catalog (mirrors cloud-hub compute_catalog)
# --------------------------------------------------------------------------- #
@mcp.tool()
def biomni_backends() -> str:
    """List each Biomni backend with its availability / status / cost.

    Mirrors cloud-hub's ``compute_catalog``: for every known backend, load its
    adapter and report ``describe()``; a backend whose adapter is not yet
    installed / configured shows ``available: false`` with the reason. Use this
    to decide which ``backend`` to pass to the other tools. The default backend
    (fail-closed target) is flagged.
    """
    rows: list[dict] = []
    for name in BACKEND_NAMES:
        is_default = name == DEFAULT_BACKEND
        try:
            backend = backends.load_backend(name)
            desc = backend.describe()
            desc.is_default = is_default
            rows.append(desc.model_dump())
        except backends.AdapterUnavailable as exc:
            rows.append(
                BackendDescriptor(
                    name=name,
                    available=False,
                    is_default=is_default,
                    status="unavailable",
                    cost="unknown",
                    detail=str(exc),
                ).model_dump()
            )
    return _json({"default": DEFAULT_BACKEND, "backends": rows})


# --------------------------------------------------------------------------- #
# A3 feature tools (component A3) — wired in at server startup (R8)
# --------------------------------------------------------------------------- #
def _build_hub_context():
    """Build the A3 HubContext, bridging every loadable backend adapter.

    Each canonical :class:`backends.BiomniBackend` adapter is wrapped by
    ``features.bridge.bridge_adapter`` into the async ``BackendClient`` the A3
    feature tools consume, then registered on the context's ``BackendRegistry``.
    A backend whose adapter cannot load is simply skipped (its feature calls fall
    back to the registry default), never crashing startup.
    """
    from features import bridge_adapter, build_default_context

    ctx = build_default_context()
    for name in BACKEND_NAMES:
        try:
            adapter = backends.load_backend(name)
        except backends.AdapterUnavailable:
            continue
        ctx.backends.register(name, bridge_adapter(adapter))
    return ctx


def register_features(target=None) -> list[str]:
    """Register the 5 additive A3 feature tools on ``target`` (default: ``mcp``).

    Called before :func:`mcp.run` so the hub exposes the canonical 10 tools +
    ``biomni_backends`` + the 5 A3 tools. Kept out of module import so importing
    ``server`` (e.g. in tests) leaves the base 11-tool surface untouched; pass a
    fresh FastMCP as ``target`` to register without mutating the module ``mcp``.
    """
    from features import register_all

    return register_all(target if target is not None else mcp, _build_hub_context())


if __name__ == "__main__":
    register_features()
    mcp.run()
