"""Claude adapter — derives server universe + namespaced toggle IDs from
'claude mcp list' text output, and toggles enable/disable via set-membership
in ~/.claude.json projects[<abs_cwd>].disabledMcpServers.

Key design decisions:
- There is NO 'claude mcp enable/disable' verb.  Enable/disable = add/remove
  from projects[path].disabledMcpServers in ~/.claude.json.
- The namespaced toggle ID is the EXACT string that appears at the start of
  each output line of 'claude mcp list' (before the first colon-space pair
  that is followed by a URL/command).
- SAFE WRITES: ~/.claude.json is large and live-rewritten by Claude Code.
  Strategy: re-read → compare mtime → merge → timestamped backup before
  first write per process session.
- We never rely on --json output (it doesn't exist); we parse the text glyphs.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from .models import AuthStatus, ServerRow

# Matches a 'claude mcp list' output line:
#   <id>: <command_or_url> - <glyph> <status_text>
#
# Example lines:
#   claude.ai Tavily: https://mcp.tavily.com/mcp - ✔ Connected
#   plugin:semgrep:semgrep: semgrep mcp - ✔ Connected
#   plugin:local-mcp-bridge:sonarqube: docker run ... - ✘ Failed to connect
#
# The ID may contain spaces (e.g. "claude.ai Tavily") so we match everything
# up to the LAST ": " that is followed by non-whitespace (the transport part).
_LINE_RE = re.compile(
    r"^(?P<id>.+?):\s+(?P<command>.+?)\s+-\s+(?P<glyph>[✔✘!⚠x])\s+(?P<status>.+)$"
)

# Fallback: lines that just show an id with no transport (bare registrations)
_BARE_RE = re.compile(r"^(?P<id>[^\s].+?)\s*$")


def parse_mcp_list(output: str) -> list[ServerRow]:
    """Parse the text output of 'claude mcp list' into ServerRow objects.

    Lines that don't match the expected format are silently skipped
    (e.g. the "Checking MCP server health..." header line).
    """
    rows: list[ServerRow] = []
    seen: set[str] = set()
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = _LINE_RE.match(line)
        if not m:
            continue
        server_id = m.group("id").strip()
        if server_id in seen:
            continue
        seen.add(server_id)
        glyph = m.group("glyph")
        status = AuthStatus.from_glyph(glyph)
        # Derive a short human-readable name from the id
        # plugin:namespace:name -> name; "claude.ai Foo" -> "Foo"
        parts = server_id.split(":")
        if len(parts) >= 3:
            short_name = parts[-1]
        elif server_id.startswith("claude.ai "):
            short_name = server_id[len("claude.ai "):]
        else:
            short_name = server_id

        rows.append(ServerRow(
            id=server_id,
            name=short_name,
            planes=["claude"],
            enabled=True,       # will be reconciled with disabledMcpServers below
            status=status,
            auth=m.group("status").strip(),
            command=m.group("command").strip(),
        ))
    return rows


def _run_mcp_list(timeout: int = 60) -> str:
    """Shell out to 'claude mcp list' and return stdout as a string."""
    result = subprocess.run(
        ["claude", "mcp", "list"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    return result.stdout


def _load_claude_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _save_claude_json(path: Path, data: dict[str, Any], *,
                      backup_dir: Path | None = None) -> None:
    """Write ~/.claude.json safely with a timestamped backup."""
    if backup_dir is None:
        backup_dir = path.parent / ".mcp-manager-backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    bak = backup_dir / f"claude.json.{ts}.bak"
    if path.exists():
        shutil.copy2(path, bak)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def get_disabled_ids(claude_json: Path, project_path: str) -> set[str]:
    """Return the set of disabled server IDs for project_path."""
    data = _load_claude_json(claude_json)
    projects = data.get("projects") or {}
    block = projects.get(project_path, {})
    return set(block.get("disabledMcpServers") or [])


def reconcile_enabled(rows: list[ServerRow], disabled_ids: set[str]) -> None:
    """Mutate rows in-place to reflect whether each server is disabled."""
    for row in rows:
        row.enabled = row.id not in disabled_ids


def get_server_universe(
    claude_json: Path,
    project_path: str,
    *,
    mcp_list_output: str | None = None,
    timeout: int = 60,
) -> list[ServerRow]:
    """Full server list with enabled/disabled state resolved.

    Args:
        claude_json: path to ~/.claude.json
        project_path: absolute cwd path (used as projects[key] in ~/.claude.json)
        mcp_list_output: if provided, use this string instead of running the CLI
        timeout: CLI subprocess timeout in seconds
    """
    raw = mcp_list_output if mcp_list_output is not None else _run_mcp_list(timeout)
    rows = parse_mcp_list(raw)
    disabled = get_disabled_ids(claude_json, project_path)
    reconcile_enabled(rows, disabled)
    return rows


def set_server_disabled(
    claude_json: Path,
    project_path: str,
    server_id: str,
    disabled: bool,
    *,
    backup_dir: Path | None = None,
    _mtime_check: bool = True,
) -> bool:
    """Add/remove server_id in projects[project_path].disabledMcpServers.

    Implements a read-compare-mtime-merge-retry safe-write:
    1. Read file + record mtime.
    2. Mutate in-memory.
    3. Re-read mtime before writing; if changed, reload + re-apply + retry once.
    4. Write with backup.

    Returns True if a change was written, False if already in target state.
    """
    def _apply(data: dict[str, Any]) -> bool:
        projects = data.setdefault("projects", {})
        block = projects.setdefault(project_path, {})
        arr: list[str] = block.setdefault("disabledMcpServers", [])
        present = server_id in arr
        if disabled and not present:
            arr.append(server_id)
            return True
        if not disabled and present:
            block["disabledMcpServers"] = [x for x in arr if x != server_id]
            return True
        return False  # no-op

    mtime_before = _mtime(claude_json) if _mtime_check else 0.0
    data = _load_claude_json(claude_json)
    changed = _apply(data)
    if not changed:
        return False

    if _mtime_check:
        mtime_after = _mtime(claude_json)
        if mtime_after != mtime_before:
            # File was rewritten externally — reload and re-apply
            data = _load_claude_json(claude_json)
            _apply(data)  # re-apply; if now no-op that is safe

    _save_claude_json(claude_json, data, backup_dir=backup_dir)
    return True
