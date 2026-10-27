"""Async status refresh — merges plane results into a unified ServerRow list.

Runs all three plane adapters concurrently and merges by server ID.
Falls back gracefully if any plane is unavailable (missing file, CLI error, etc.).

Usage (async context):
    from core.status import refresh
    rows = await refresh()

Usage (sync context):
    from core.status import refresh_sync
    rows = refresh_sync()
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from .models import AuthStatus, ServerRow

# Default config paths
_CLAUDE_JSON = Path.home() / ".claude.json"
_CODEX_TOML = Path.home() / ".codex" / "config.toml"
_FUNNEL_PROFILES = Path.home() / ".mcp-funnel-profiles.json"


def _merge_rows(all_rows: list[list[ServerRow]]) -> list[ServerRow]:
    """Merge per-plane ServerRow lists into one list by ID.

    When the same ID appears in multiple planes the first entry's metadata
    (status, auth, command) is kept and planes lists are combined.
    """
    merged: dict[str, ServerRow] = {}
    for plane_rows in all_rows:
        for row in plane_rows:
            if row.id not in merged:
                merged[row.id] = ServerRow(
                    id=row.id,
                    name=row.name,
                    planes=list(row.planes),
                    enabled=row.enabled,
                    status=row.status,
                    auth=row.auth,
                    command=row.command,
                )
            else:
                existing = merged[row.id]
                existing.planes.extend(row.planes)
                # Upgrade status if existing is UNKNOWN
                if (
                    existing.status == AuthStatus.UNKNOWN
                    and row.status != AuthStatus.UNKNOWN
                ):
                    existing.status = row.status
                # If planes disagree on enabled, mark disabled if ANY plane disables it
                if not row.enabled:
                    existing.enabled = False
    return sorted(merged.values(), key=lambda r: r.id)


async def _fetch_claude(
    claude_json: Path,
    project_path: str,
    *,
    mcp_list_output: str | None = None,
) -> list[ServerRow]:
    """Async wrapper around claude_adapter.get_server_universe."""
    from . import claude_adapter  # deferred

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: claude_adapter.get_server_universe(
            claude_json,
            project_path,
            mcp_list_output=mcp_list_output,
        ),
    )


async def _fetch_codex(
    config_toml: Path,
    *,
    json_output: str | None = None,
) -> list[ServerRow]:
    """Async wrapper around codex_adapter.get_server_universe."""
    from . import codex_adapter  # deferred

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: codex_adapter.get_server_universe(
            config_toml,
            json_output=json_output,
        ),
    )


async def _fetch_funnel(profiles_json: Path) -> list[ServerRow]:
    """Async wrapper around funnel_adapter.get_server_universe."""
    from . import funnel_adapter  # deferred

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: funnel_adapter.get_server_universe(profiles_json),
    )


async def refresh(
    *,
    claude_json: Path = _CLAUDE_JSON,
    codex_toml: Path = _CODEX_TOML,
    funnel_profiles: Path = _FUNNEL_PROFILES,
    project_path: str | None = None,
    # allow injecting pre-captured CLI output for testing / offline use
    mcp_list_output: str | None = None,
    codex_json_output: str | None = None,
) -> list[ServerRow]:
    """Async: fetch all three planes concurrently and merge.

    Args:
        claude_json: path to ~/.claude.json
        codex_toml: path to ~/.codex/config.toml
        funnel_profiles: path to ~/.mcp-funnel-profiles.json
        project_path: project path to use for Claude disabled-servers lookup;
                      defaults to str(Path.home())
        mcp_list_output: inject mock 'claude mcp list' output (for tests)
        codex_json_output: inject mock 'codex mcp list --json' output (for tests)
    """
    if project_path is None:
        project_path = str(Path.home()).replace("\\", "/")

    async def _safe_fetch_claude() -> list[ServerRow]:
        try:
            return await _fetch_claude(
                claude_json, project_path, mcp_list_output=mcp_list_output
            )
        except Exception:  # noqa: BLE001 - never fail the whole refresh
            return []

    async def _safe_fetch_codex() -> list[ServerRow]:
        try:
            return await _fetch_codex(codex_toml, json_output=codex_json_output)
        except Exception:  # noqa: BLE001
            return []

    async def _safe_fetch_funnel() -> list[ServerRow]:
        try:
            return await _fetch_funnel(funnel_profiles)
        except Exception:  # noqa: BLE001
            return []

    claude_rows, codex_rows, funnel_rows = await asyncio.gather(
        _safe_fetch_claude(),
        _safe_fetch_codex(),
        _safe_fetch_funnel(),
    )
    return _merge_rows([claude_rows, codex_rows, funnel_rows])


def refresh_sync(
    *,
    claude_json: Path = _CLAUDE_JSON,
    codex_toml: Path = _CODEX_TOML,
    funnel_profiles: Path = _FUNNEL_PROFILES,
    project_path: str | None = None,
    mcp_list_output: str | None = None,
    codex_json_output: str | None = None,
) -> list[ServerRow]:
    """Synchronous wrapper around refresh() — for CLI / non-async callers."""
    return asyncio.run(
        refresh(
            claude_json=claude_json,
            codex_toml=codex_toml,
            funnel_profiles=funnel_profiles,
            project_path=project_path,
            mcp_list_output=mcp_list_output,
            codex_json_output=codex_json_output,
        )
    )
