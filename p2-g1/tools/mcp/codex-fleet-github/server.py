#!/usr/bin/env python3
"""codex-fleet-github MCP server -- drive the private Codex runner fleet over stdio.

Thin FastMCP wrappers over ``fleet_core``. See fleet_core.py for the security
model: this server NEVER touches the runner's auth.json; it only *triggers* runs
with a scoped dispatch token (CODEX_DISPATCH_PAT / GH_TOKEN / keyring, or gh's
own ambient auth). Every tool is propose-only -- the runner opens DRAFT PRs and
nothing here merges.

Run: ``python server.py`` (stdio MCP; what ~/.mcp.json / ~/.codex/config.toml run).
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import fleet_core as core  # noqa: E402
from mcp.server.fastmcp import FastMCP  # noqa: E402

mcp = FastMCP("codex-fleet-github")


@mcp.tool()
def fleet_dispatch(
    repo: str,
    task: str,
    model: str = "",
    effort: str = "",
    max_changed_files: int = 0,
) -> dict:
    """Trigger ONE Codex-runner run against ``repo`` (owner/name) with ``task``.

    Dispatches the private runner (codex-runner.yml) which opens a propose-only
    DRAFT PR on the target -- nothing is auto-merged. Optional: ``model``
    (default gpt-5.6-sol), ``effort`` (minimal|low|medium|high|xhigh|max|ultra;
    default max), ``max_changed_files`` (default 40; the runner aborts past it).
    Auth is a scoped dispatch token from CODEX_DISPATCH_PAT / GH_TOKEN / keyring
    (or gh's own login) -- this tool NEVER handles the runner's auth.json.
    Returns the run URL (best-effort) plus the Actions URL.
    """
    try:
        return core.dispatch_one(
            repo,
            task,
            model=model,
            effort=effort,
            max_changed_files=max_changed_files or None,
        )
    except core.FleetError as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool()
def fleet_sweep(
    task: str,
    repos: list[str] | None = None,
    model: str = "",
    effort: str = "",
    max_changed_files: int = 0,
) -> dict:
    """Dispatch the SAME ``task`` to many repos.

    Default target set = every enabled repo in codex-targets.yml (the QZT
    control-plane file). FAIL-CLOSED: if that file can't load or has zero enabled
    targets and no ``repos`` are given, this returns an error instead of fanning
    out (set CODEX_FLEET_ALLOW_FALLBACK to opt into the curated 4-public-repo
    fallback). Pass ``repos`` (["owner/name", ...]) for an explicit set. Each run
    is propose-only (DRAFT PR); the private runner serializes all runs via its
    'codex-runner' concurrency group, so a big sweep drains one run at a time.
    Then call fleet_status for the resulting run/PR links.
    """
    try:
        return core.sweep(
            task,
            repos,
            model=model,
            effort=effort,
            max_changed_files=max_changed_files or None,
        )
    except core.FleetError as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool()
def fleet_status(limit: int = 15) -> dict:
    """List recent codex-runner runs + open codex-runner DRAFT PRs across the fleet.

    Runs come from the runner repo's workflow; PRs are matched across the owner's
    repos by the 'codex-runner' label or the runner's PR title. Read-only.
    ``limit`` caps the run list (1..50).
    """
    return core.status(limit)


@mcp.tool()
def fleet_orchestrate(
    plan: str,
    repos: list[str] | None = None,
    dispatch: bool = False,
    model: str = "",
    effort: str = "",
    max_changed_files: int = 0,
) -> dict:
    """Decompose a high-level ``plan`` into one concrete task per repo.

    RETURNS the structured per-repo plan WITHOUT dispatching (safe default).
    Repos default to the enabled codex-targets.yml set (FAIL-CLOSED if it can't
    load or is empty and no ``repos`` are given -- pass explicit repos or set
    CODEX_FLEET_ALLOW_FALLBACK for the curated 4-public-repo fallback).
    Set ``dispatch=true`` to then fire fleet_dispatch for each item (propose-only
    DRAFT PRs, serialized by the runner). Decomposition is currently a
    deterministic template (plan + repo -> task); a smarter per-repo
    decomposition is a follow-up.
    """
    try:
        return core.orchestrate(
            plan,
            repos,
            dispatch=dispatch,
            model=model,
            effort=effort,
            max_changed_files=max_changed_files or None,
        )
    except core.FleetError as exc:
        return {"ok": False, "error": str(exc)}


def main() -> None:  # pragma: no cover -- module entrypoint
    mcp.run()


if __name__ == "__main__":  # pragma: no cover -- module entrypoint
    main()
