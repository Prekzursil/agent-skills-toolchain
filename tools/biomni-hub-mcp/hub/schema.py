#!/usr/bin/env python3
"""biomni-hub — the CANONICAL shared tool schema (single source of truth).

This module is authored ONCE and imported by BOTH backend adapters (the online
proxy in ``online_adapter.py`` and the Databricks adapter in
``databricks_adapter.py``). Neither adapter re-declares tool names, parameters,
or result shapes — they import the models and the ``CANONICAL_TOOLS`` registry
from here so the two backends stay wire-identical.

The surface mirrors the online claude.ai **Biomni Lab** connector's 10 tools:

    create_project · list_projects · list_workspaces · switch_workspace ·
    upload_file · start_new_task · send_message · wait_for_next_update ·
    list_tasks · list_result_files

Async task model
----------------
A Biomni "task" is a long-running agent run (30s to 10min+). ``start_new_task``
and ``send_message`` return QUICKLY with a ``task_id`` and the current status;
callers then poll ``wait_for_next_update`` until the task reaches a terminal
state. Result artifacts are surfaced by ``list_result_files`` as name + size
only (the sandbox bytes are not directly fetchable over this surface).

display_instruction / biomni_url protocol
------------------------------------------
Any tool result MAY carry two optional client-facing hints on the envelope:

* ``display_instruction`` — a short natural-language instruction telling the
  calling client how to present the result (e.g. "Open the notebook to view the
  plot").
* ``biomni_url`` — a deep link into the hosted Biomni web app for the richer
  view (notebook, file previews, reasoning trace).

Both are advisory and backend-agnostic; the Databricks adapter populates them
with its own equivalents (a job-run URL, a Volume path hint) or leaves them null.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0.0"


# --------------------------------------------------------------------------- #
# Backend identity
# --------------------------------------------------------------------------- #
class Backend(StrEnum):
    """The two compute backends this hub fronts.

    ``ONLINE`` is the hosted Biomni Lab (via the ``bm_*`` REST proxy) and is the
    fail-closed default. ``DATABRICKS`` is the self-hosted Biomni OSS agent on
    the authorized ``bolt-datascience`` workspace.
    """

    ONLINE = "online"
    DATABRICKS = "databricks"


#: The fail-closed default backend when nothing else selects one.
DEFAULT_BACKEND: str = Backend.ONLINE.value

#: All backend names the selector recognizes (order = catalog display order).
BACKEND_NAMES: tuple[str, ...] = tuple(b.value for b in Backend)


# --------------------------------------------------------------------------- #
# Result envelope (every adapter method returns one of these)
# --------------------------------------------------------------------------- #
class ResultFile(BaseModel):
    """A result artifact surfaced by ``list_result_files`` — name + size only."""

    model_config = ConfigDict(extra="allow")

    name: str = Field(..., description="File name (basename) of the artifact.")
    size: int = Field(..., ge=0, description="Size in bytes.")
    task_id: str | None = Field(
        default=None, description="Owning task id, when known."
    )
    path: str | None = Field(
        default=None, description="Backend-relative path hint, when available."
    )


class ToolEnvelope(BaseModel):
    """The canonical result both adapters return for every tool call.

    ``data`` holds the tool-specific payload (a project dict, a list of tasks,
    a task-update object, etc.). ``display_instruction`` and ``biomni_url``
    carry the optional client-presentation protocol described in the module
    docstring.
    """

    model_config = ConfigDict(extra="allow")

    ok: bool = Field(..., description="True on success, False on a handled error.")
    backend: str = Field(..., description="Backend that served the call.")
    tool: str = Field(..., description="Canonical tool name that was invoked.")
    data: Any = Field(default=None, description="Tool-specific success payload.")
    error: str | None = Field(
        default=None, description="Human-readable error message when ok is False."
    )
    display_instruction: str | None = Field(
        default=None, description="Optional client-presentation instruction."
    )
    biomni_url: str | None = Field(
        default=None, description="Optional deep link into the Biomni web app."
    )

    @classmethod
    def success(
        cls,
        backend: str,
        tool: str,
        data: Any = None,
        *,
        display_instruction: str | None = None,
        biomni_url: str | None = None,
    ) -> ToolEnvelope:
        return cls(
            ok=True,
            backend=backend,
            tool=tool,
            data=data,
            error=None,
            display_instruction=display_instruction,
            biomni_url=biomni_url,
        )

    @classmethod
    def failure(cls, backend: str, tool: str, error: str) -> ToolEnvelope:
        return cls(ok=False, backend=backend, tool=tool, data=None, error=error)


class BackendDescriptor(BaseModel):
    """One row of the ``biomni_backends`` catalog (mirrors compute_catalog)."""

    name: str = Field(..., description="Backend name (online | databricks).")
    available: bool = Field(
        ..., description="True if the adapter loaded and is ready to serve calls."
    )
    is_default: bool = Field(
        ..., description="True if this is the fail-closed default backend."
    )
    status: str = Field(
        ..., description="Short status string (e.g. 'ready', 'unconfigured')."
    )
    cost: str = Field(
        ..., description="Cost model summary (e.g. 'hosted usage credits')."
    )
    detail: str = Field(
        default="", description="Free-text detail: auth state, endpoint, notes."
    )


# --------------------------------------------------------------------------- #
# Per-tool request parameter models (typed; imported by the server + adapters)
# --------------------------------------------------------------------------- #
class CreateProjectParams(BaseModel):
    name: str = Field(..., description="Project display name.")
    description: str = Field(default="", description="Optional project description.")


class ListProjectsParams(BaseModel):
    """``list_projects`` takes no arguments."""


class ListWorkspacesParams(BaseModel):
    """``list_workspaces`` takes no arguments."""


class SwitchWorkspaceParams(BaseModel):
    workspace_id: str = Field(..., description="Id of the workspace to make active.")


class UploadFileParams(BaseModel):
    local_path: str = Field(..., description="Absolute path of the local file.")
    project_id: str = Field(
        default="", description="Target project id (default: active project)."
    )
    destination: str = Field(
        default="", description="Optional backend destination name/subpath."
    )


class StartNewTaskParams(BaseModel):
    project_id: str = Field(..., description="Project the task is created under.")
    prompt: str = Field(..., description="The initial user prompt for the agent.")
    model_profile: str = Field(
        default="standard",
        description="Effort tier: standard | fast | premium.",
    )


class SendMessageParams(BaseModel):
    task_id: str = Field(..., description="Existing task (session) id.")
    content: str = Field(..., description="User message to send into the task.")


class WaitForNextUpdateParams(BaseModel):
    task_id: str = Field(..., description="Task to poll for its next update.")
    timeout_seconds: float = Field(
        default=60.0,
        gt=0,
        le=600.0,
        description="Max seconds to wait for the next update before returning.",
    )
    since: int | None = Field(
        default=None,
        ge=0,
        description="Optional resume cursor: return only updates after this "
        "message index (pass the ``cursor`` from the previous update).",
    )


class ListTasksParams(BaseModel):
    project_id: str = Field(
        default="", description="Project to list tasks for (default: active/all)."
    )


class ListResultFilesParams(BaseModel):
    task_id: str = Field(
        default="", description="Task to list result files for (default: all)."
    )


# --------------------------------------------------------------------------- #
# Canonical tool registry — the ONE source of truth for both adapters
# --------------------------------------------------------------------------- #
class ToolSpec(BaseModel):
    """Metadata for one canonical tool: name, one-line summary, param model."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    summary: str
    params_model: type[BaseModel]


CANONICAL_TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="create_project",
        summary="Create a Biomni project to group tasks and files.",
        params_model=CreateProjectParams,
    ),
    ToolSpec(
        name="list_projects",
        summary="List the projects in the active workspace.",
        params_model=ListProjectsParams,
    ),
    ToolSpec(
        name="list_workspaces",
        summary="List the workspaces available to the account.",
        params_model=ListWorkspacesParams,
    ),
    ToolSpec(
        name="switch_workspace",
        summary="Make a different workspace the active one.",
        params_model=SwitchWorkspaceParams,
    ),
    ToolSpec(
        name="upload_file",
        summary="Upload a local file into a project's workspace.",
        params_model=UploadFileParams,
    ),
    ToolSpec(
        name="start_new_task",
        summary="Start a new async agent task from a prompt (returns a task_id).",
        params_model=StartNewTaskParams,
    ),
    ToolSpec(
        name="send_message",
        summary="Send a follow-up message into an existing task.",
        params_model=SendMessageParams,
    ),
    ToolSpec(
        name="wait_for_next_update",
        summary="Block until the task produces its next update or times out.",
        params_model=WaitForNextUpdateParams,
    ),
    ToolSpec(
        name="list_tasks",
        summary="List tasks (agent sessions), optionally scoped to a project.",
        params_model=ListTasksParams,
    ),
    ToolSpec(
        name="list_result_files",
        summary="List result files (name + size) produced by tasks.",
        params_model=ListResultFilesParams,
    ),
)

#: Just the names, in canonical order — used for registration assertions.
CANONICAL_TOOL_NAMES: tuple[str, ...] = tuple(t.name for t in CANONICAL_TOOLS)

#: The catalog tool is a hub control-plane tool, not part of the Biomni surface.
CATALOG_TOOL_NAME = "biomni_backends"


def tool_spec(name: str) -> ToolSpec:
    """Return the ToolSpec for ``name`` (raises KeyError if unknown)."""
    for spec in CANONICAL_TOOLS:
        if spec.name == name:
            return spec
    raise KeyError(f"unknown canonical tool: {name!r}")
