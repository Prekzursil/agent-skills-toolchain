"""Funnel adapter — manages the mcp-profile switcher.

The funnel uses two files:
  ~/.mcp-funnel-profiles.json   — named profile definitions (read here; DO NOT reinvent)
  ~/.mcp-funnel.json            — active funnel config (managed by the profile script)

Toggle / profile-switch: shells out to:
    C:/Users/Prekzursil/scripts/mcp-profile.ps1 <profile_name>

Server universe: read from ~/.mcp-funnel-profiles.json.  The "default" profile
maps to "*ALL*" (all servers); other profiles list explicit names.

We do NOT reinvent the switcher — all profile write operations go through the
mcp-profile.ps1 script, which owns the active funnel config.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from .models import AuthStatus, ServerRow

# Default path to the profile-switch script
_DEFAULT_SCRIPT = Path("C:/Users/Prekzursil/scripts/mcp-profile.ps1")

# Default path to the profiles registry
_DEFAULT_PROFILES = Path("C:/Users/Prekzursil/.mcp-funnel-profiles.json")

# Sentinel used in the profiles file to mean "every server"
_ALL_SENTINEL = "*ALL*"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def load_profiles(profiles_json: Path = _DEFAULT_PROFILES) -> dict[str, Any]:
    """Return the raw profiles dict from ~/.mcp-funnel-profiles.json."""
    data = _load_json(profiles_json)
    return data.get("profiles") or {}


def get_profile_servers(
    profile_name: str,
    profiles_json: Path = _DEFAULT_PROFILES,
) -> list[str] | None:
    """Return the server list for a named profile.

    Returns None if the profile doesn't exist.
    Returns the sentinel string '*ALL*' (as a single-element list ["*ALL*"])
    if the profile maps to the ALL sentinel.
    """
    profiles = load_profiles(profiles_json)
    if profile_name not in profiles:
        return None
    value = profiles[profile_name]
    if value == _ALL_SENTINEL:
        return [_ALL_SENTINEL]
    if isinstance(value, list):
        return list(value)
    return [str(value)]


def get_server_universe(
    profiles_json: Path = _DEFAULT_PROFILES,
) -> list[ServerRow]:
    """Return all funnel servers as ServerRow objects.

    Derives the universe from the union of all named profiles.
    The 'default' profile maps to *ALL* so we include servers from all profiles.
    """
    profiles = load_profiles(profiles_json)
    all_names: set[str] = set()
    for value in profiles.values():
        if value == _ALL_SENTINEL:
            continue
        if isinstance(value, list):
            all_names.update(value)
    rows = [
        ServerRow(
            id=name,
            name=name,
            planes=["funnel"],
            enabled=True,
            status=AuthStatus.UNKNOWN,
            auth="",
            command="",
        )
        for name in sorted(all_names)
    ]
    return rows


def list_profiles(profiles_json: Path = _DEFAULT_PROFILES) -> list[str]:
    """Return the list of defined profile names."""
    return sorted(load_profiles(profiles_json).keys())


def switch_profile(
    profile_name: str,
    *,
    script_path: Path = _DEFAULT_SCRIPT,
    profiles_json: Path = _DEFAULT_PROFILES,
    timeout: int = 30,
    dry_run: bool = False,
) -> tuple[bool, str]:
    """Switch the active funnel profile by calling mcp-profile.ps1 <name>.

    Returns (success: bool, message: str).
    Validates the profile exists before calling the script.

    If dry_run=True, validates but does not execute the script.
    """
    profiles = load_profiles(profiles_json)
    if profile_name not in profiles:
        available = ", ".join(sorted(profiles.keys()))
        return False, f"Unknown profile {profile_name!r}. Available: {available}"

    if dry_run:
        return True, f"[dry-run] would run: {script_path} {profile_name}"

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-File", str(script_path), profile_name],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return (
            False,
            result.stderr.strip()
            or result.stdout.strip()
            or f"exit {result.returncode}",
        )
    except subprocess.TimeoutExpired:
        return False, f"mcp-profile.ps1 timed out after {timeout}s"
    except (subprocess.SubprocessError, FileNotFoundError, OSError) as exc:
        return False, f"failed to run mcp-profile.ps1: {exc}"
