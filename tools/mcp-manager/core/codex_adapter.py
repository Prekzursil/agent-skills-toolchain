"""Codex adapter — manages MCP servers in ~/.codex/config.toml.

Codex stores each MCP server as a [mcp_servers.<name>] table.
The 'enabled' key (bool, default true when absent) controls
whether Codex loads it.

Toggle: mutate via tomlkit (preserves comments + formatting),
        validate the result with tomllib before writing,
        take a timestamped backup before first write.

Status discovery: 'codex mcp list --json' returns a JSON array
of objects with .name + .enabled fields.  We use that if available
and fall back to parsing config.toml directly.
"""

from __future__ import annotations
from typing import cast
import json
import shutil
import subprocess
import time
from pathlib import Path

from .models import AuthStatus, ServerRow

try:
    import tomllib  # py3.11+
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]


# ── helpers ──────────────────────────────────────────────────────────────────


def _backup(path: Path) -> Path:
    bak_dir = path.parent / ".mcp-manager-backups"
    bak_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    bak = bak_dir / f"{path.name}.{ts}.bak"
    _ = shutil.copy2(path, bak)
    return bak


def _read_toml_raw(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return ""


def _toml_servers(path: Path) -> dict[str, object]:
    """Return the [mcp_servers.*] tables from config.toml as a plain dict."""
    if tomllib is None:
        return {}
    raw = _read_toml_raw(path)
    if not raw:
        return {}
    try:
        data = cast("dict[str, object]", tomllib.loads(raw))
    except Exception:  # noqa: BLE001
        return {}
    return dict(cast("dict[str, object]", data.get("mcp_servers") or {}))


# ── public API ────────────────────────────────────────────────────────────────


def parse_codex_mcp_list(json_output: str) -> list[ServerRow]:
    """Parse 'codex mcp list --json' output into ServerRow objects."""
    rows: list[ServerRow] = []
    try:
        parsed = cast("object", json.loads(json_output))
    except json.JSONDecodeError:
        return rows
    if not isinstance(parsed, list):
        return rows
    for item in cast("list[object]", parsed):
        if not isinstance(item, dict):
            continue
        entry = cast("dict[str, object]", item)
        name = entry.get("name")
        if not name:
            continue
        name_str = str(name)
        enabled = bool(entry.get("enabled", True))
        # Codex status field isn't a glyph; use auth_status if present
        auth_raw = str(entry.get("auth_status") or "")
        status = AuthStatus.UNKNOWN
        if not enabled:
            status = AuthStatus.UNKNOWN
        rows.append(
            ServerRow(
                id=name_str,
                name=name_str,
                planes=["codex"],
                enabled=enabled,
                status=status,
                auth=auth_raw,
                command="",
            )
        )
    return rows


def get_server_universe(
    config_toml: Path,
    *,
    json_output: str | None = None,
    timeout: int = 30,
) -> list[ServerRow]:
    """Return Codex MCP servers as ServerRow list.

    If json_output is provided, parse that; otherwise run 'codex mcp list --json'.
    Falls back to reading config.toml directly if the CLI isn't available.
    """
    if json_output is not None:
        rows = parse_codex_mcp_list(json_output)
        if rows:
            return rows

    if json_output is None:
        # Try the CLI
        try:
            result = subprocess.run(
                ["codex", "mcp", "list", "--json"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
            cli_rows = parse_codex_mcp_list(result.stdout)
            if cli_rows:
                return cli_rows
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            pass

    # Fallback: read config.toml directly
    servers = _toml_servers(config_toml)
    rows: list[ServerRow] = []
    for name, spec in servers.items():
        enabled = (
            bool(cast("dict[str, object]", spec).get("enabled", True))
            if isinstance(spec, dict)
            else True
        )
        rows.append(
            ServerRow(
                id=name,
                name=name,
                planes=["codex"],
                enabled=enabled,
                status=AuthStatus.UNKNOWN,
                auth="",
                command="",
            )
        )
    return rows


def set_server_enabled(
    config_toml: Path,
    server_name: str,
    enabled: bool,
    *,
    backup: bool = True,
) -> bool:
    """Toggle [mcp_servers.<server_name>].enabled via tomlkit.

    Preserves all formatting, comments, and whitespace.
    Validates the output with tomllib before writing.

    Returns True if a change was written, False if already in target state.
    Raises KeyError if the server doesn't exist.
    Raises ImportError if tomlkit is not installed.
    Raises ValueError if the resulting TOML is invalid (defensive).
    """
    import tomlkit  # deferred; callers can pytest.importorskip("tomlkit")

    raw = _read_toml_raw(config_toml)
    if not raw:
        raise KeyError(f"codex config not found or empty: {config_toml}")

    doc = tomlkit.parse(raw)
    servers = cast(
        "dict[str, object] | None", cast("dict[str, object]", doc).get("mcp_servers")
    )
    if servers is None or server_name not in servers:
        raise KeyError(f"codex server not found: {server_name!r}")

    table = cast("dict[str, object]", servers[server_name])
    current = table.get("enabled", True)
    if bool(current) == enabled:
        return False  # no-op

    table["enabled"] = enabled

    out = tomlkit.dumps(doc)

    # Validate before committing
    if tomllib is not None:
        try:
            _ = tomllib.loads(out)
        except Exception as exc:  # pragma: no cover
            raise ValueError(f"refusing to write invalid TOML: {exc}") from exc

    if backup and config_toml.exists():
        _ = _backup(config_toml)

    _ = config_toml.write_text(out, encoding="utf-8")
    return True
