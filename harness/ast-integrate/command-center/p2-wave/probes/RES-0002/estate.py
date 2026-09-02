"""Estate census: live Claude hooks, settings, and the 05-ECO source."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from constants import HOOK_SUFFIXES, REPO

WINDOWS_ECO = (
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
    "05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md"
)
ECO_NAMES = ("05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md",)
REGISTER_REL = "command-center/sources/REGISTER.md"


def _try_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _list_scripts(root: Path, limit: int = 80) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not root.is_dir():
        return out
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in HOOK_SUFFIXES and "sentinel" not in path.name.lower():
            continue
        rec = {
            "path": str(path),
            "name": path.name,
            "bytes": path.stat().st_size,
            "suffix": path.suffix.lower(),
        }
        out.append(rec)
        if len(out) >= limit:
            break
    return out


def _settings_post_tool_use(doc: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if not isinstance(doc, dict):
        return found
    hooks = doc.get("hooks")
    if not isinstance(hooks, dict):
        return found
    for key in ("PostToolUse", "postToolUse", "post_tool_use"):
        entries = hooks.get(key)
        if isinstance(entries, list):
            for item in entries:
                if isinstance(item, dict):
                    found.append(
                        {
                            "event_key": key,
                            "matcher": item.get("matcher"),
                            "command": (item.get("hooks") or [{}])[0].get("command")
                            if isinstance(item.get("hooks"), list) and item.get("hooks")
                            else item.get("command"),
                        }
                    )
    return found


def candidate_roots() -> list[Path]:
    home = Path.home()
    env = os.environ.get("HARVEST_RESTORE")
    roots = [
        home / ".claude" / "hooks",
        home / ".config" / "claude" / "hooks",
        REPO / ".claude" / "hooks",
        Path("/opt/p2/harness-restore-20260806"),
        home / ".claude" / "harness-restore-20260806",
        Path("/mnt/c/Users/Prekzursil/.claude/hooks"),
        Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806"),
        Path("/c/Users/Prekzursil/.claude/hooks"),
        Path(r"C:/Users/Prekzursil/.claude/hooks"),
        Path(WINDOWS_ECO).parent,
    ]
    if env:
        roots.append(Path(env))
        roots.append(Path(env) / "hooks")
    # unique while preserving order
    seen: set[str] = set()
    out: list[Path] = []
    for path in roots:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
    return out


def locate_eco() -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    seen: set[str] = set()
    extra = [
        Path(WINDOWS_ECO),
        Path.home() / ".claude" / "harness-restore-20260806" / ECO_NAMES[0],
        Path("/opt/p2/harness-restore-20260806") / ECO_NAMES[0],
        REPO / "command-center" / "sources" / ECO_NAMES[0],
        REPO / ECO_NAMES[0],
    ]
    for path in extra:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        hits.append(
            {
                "path": key,
                "exists": path.is_file(),
                "bytes": path.stat().st_size if path.is_file() else 0,
            }
        )
    return hits


def census() -> dict[str, Any]:
    home = Path.home()
    settings_paths = [
        home / ".claude" / "settings.json",
        home / ".claude" / "settings.local.json",
        REPO / ".claude" / "settings.json",
        REPO / ".claude" / "settings.local.json",
    ]
    settings_rows = []
    post_tool: list[dict[str, Any]] = []
    for path in settings_paths:
        exists = path.is_file()
        row: dict[str, Any] = {"path": str(path), "exists": exists}
        if exists:
            doc = _try_json(path)
            row["parseable"] = isinstance(doc, dict)
            found = _settings_post_tool_use(doc)
            row["post_tool_use_entries"] = len(found)
            post_tool.extend(found)
        else:
            row["parseable"] = False
            row["post_tool_use_entries"] = 0
        settings_rows.append(row)

    hook_dirs = []
    scripts: list[dict[str, Any]] = []
    for root in candidate_roots():
        present = root.exists()
        hook_dirs.append(
            {
                "path": str(root),
                "exists": present,
                "is_dir": root.is_dir(),
            }
        )
        if root.is_dir():
            scripts.extend(_list_scripts(root))

    register = REPO / REGISTER_REL
    return {
        "platform": os.uname().sysname,
        "home": str(home),
        "claude_binary": shutil.which("claude"),
        "register_md_present": register.is_file(),
        "register_md": REGISTER_REL,
        "windows_eco": WINDOWS_ECO,
        "eco_hits": locate_eco(),
        "eco_present": any(h["exists"] for h in locate_eco()),
        "hook_dirs": hook_dirs,
        "hook_scripts": scripts,
        "hook_script_count": len(scripts),
        "settings": settings_rows,
        "post_tool_use_from_settings": post_tool,
        "live_post_tool_use_configured": bool(post_tool) or bool(scripts),
        "live_tool_sentinel_present": any(
            "sentinel" in (s.get("name") or "").lower() for s in scripts
        ),
    }
