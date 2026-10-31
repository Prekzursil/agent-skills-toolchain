#!/usr/bin/env python3
"""Enumerate harness load-set (skills, hooks, rules, plugins, MCP) for a HOME + repo.

Does not launch a host process. Observes the documented on-disk load surfaces.
Never stores MCP/env values or auth files — names and relative paths only.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

SKIP_DIR_NAMES = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "chats",
    "ai-tracking",
    "projects",
    "debug",
    "todos",
    "shell-snapshots",
    "file-history",
    "statsig",
    ".cache",
    ".local",
    ".ssh",
}

# Paths under HOME that can contribute user-profile loadables.
USER_LOAD_ROOTS = (
    ".claude/skills",
    ".claude/commands",
    ".claude/agents",
    ".claude/hooks",
    ".claude/rules",
    ".claude/plugins",
    ".claude/settings.json",
    ".claude.json",
    ".mcp.json",
    ".agents/skills",
    ".agents/hooks",
    ".codex/skills",
    ".cursor/skills-cursor",
    ".cursor/skills",
    ".cursor/hooks",
    ".cursor/hooks.json",
    ".cursor/rules",
    ".cursor/plugins",
    ".cursor/mcp.json",
    ".cursor/managed",
    "AppData/Roaming/Claude",
    "AppData/Roaming/Cursor",
    "AppData/Roaming/npm",
)

REPO_LOAD_ROOTS = (
    ".claude",
    ".claude-plugin",
    ".cursor",
    "skills",
    "hooks",
    "rules",
    "plugins",
    ".agents/skills",
    ".agents/hooks",
    "CLAUDE.md",
    "AGENTS.md",
    ".mcp.json",
    "plugin.json",
)

HARNESS_DOT_DIRS = {".claude", ".cursor", ".agents", ".codex"}


def _is_harness_kind_dir(rel: str, kind_dir: str) -> bool:
    """True only for documented harness roots, not any path containing /hooks/."""
    parts = rel.replace("\\", "/").lstrip("/").split("/")
    if not parts or not parts[0]:
        return False
    if parts[0] == kind_dir:
        return True
    return (
        len(parts) >= 2
        and parts[0] in HARNESS_DOT_DIRS
        and parts[1] == kind_dir
    )


SECRET_NAME_MARKERS = (
    "auth.json",
    "cli-config.json",
    "credentials",
    "secret",
    "token",
    ".netrc",
)


def _is_secret_name(name: str) -> bool:
    lower = name.lower()
    return any(m in lower for m in SECRET_NAME_MARKERS)


def _walk_files(root: Path, *, limit: int = 8000) -> list[Path]:
    out: list[Path] = []
    if not root.exists():
        return out
    if root.is_file():
        return [root]
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [
            d
            for d in dirnames
            if d not in SKIP_DIR_NAMES and not d.startswith(".git")
        ]
        base = Path(dirpath)
        for name in filenames:
            if _is_secret_name(name):
                continue
            out.append(base / name)
            if len(out) >= limit:
                return out
    return out


def _load_json_object(path: Path) -> dict[str, Any] | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _mcp_names(path: Path) -> list[str]:
    data = _load_json_object(path)
    if not data:
        return []
    names: list[str] = []
    for key in ("mcpServers", "servers"):
        block = data.get(key)
        if isinstance(block, dict):
            names.extend(str(k) for k in block.keys() if str(k))
    nested = data.get("mcp")
    if isinstance(nested, dict) and isinstance(nested.get("servers"), dict):
        names.extend(str(k) for k in nested["servers"].keys() if str(k))
    return sorted(set(names))


def _hook_entries_from_settings(path: Path) -> list[str]:
    data = _load_json_object(path)
    if not data:
        return []
    hooks = data.get("hooks")
    names: list[str] = []
    if isinstance(hooks, dict):
        names.extend(str(k) for k in hooks.keys() if str(k))
    elif isinstance(hooks, list):
        for item in hooks:
            if isinstance(item, dict) and item.get("command"):
                names.append(str(item.get("matcher") or item.get("command")))
            elif isinstance(item, str):
                names.append(item)
    return sorted(set(names))


def _plugin_ids(path: Path) -> list[str]:
    data = _load_json_object(path)
    if not data:
        return []
    names: list[str] = []
    if path.name == "plugin.json" and data.get("name"):
        names.append(str(data["name"]))
    for key in ("enabledPlugins", "plugins"):
        block = data.get(key)
        if isinstance(block, dict):
            names.extend(str(k) for k in block.keys() if str(k))
        elif isinstance(block, list):
            for item in block:
                if isinstance(item, str):
                    names.append(item)
                elif isinstance(item, dict) and item.get("name"):
                    names.append(str(item["name"]))
    return sorted(set(names))


def _item(kind: str, scope: str, ident: str, rel: str) -> dict[str, str]:
    return {
        "kind": kind,
        "scope": scope,
        "id": ident,
        "path": rel.replace("\\", "/"),
        "key": f"{kind}:{scope}:{ident}",
    }


def _rel(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def classify_file(path: Path, *, scope: str, root: Path) -> list[dict[str, str]]:
    rel = _rel(root, path)
    name = path.name
    parent = path.parent.name
    items: list[dict[str, str]] = []
    lower_rel = rel.lower()

    if name == "SKILL.md":
        items.append(_item("skill", scope, parent or rel, rel))
    elif name == "plugin.json":
        for pid in _plugin_ids(path) or [parent or "unnamed-plugin"]:
            items.append(_item("plugin", scope, pid, rel))
    elif name in {"mcp.json", ".mcp.json", "claude_desktop_config.json"}:
        for srv in _mcp_names(path):
            items.append(_item("mcp", scope, srv, rel))
        if name == "claude_desktop_config.json" and not _mcp_names(path):
            # File present but no servers: still a load surface, not a server.
            pass
    elif name in {"settings.json", ".claude.json"}:
        for srv in _mcp_names(path):
            items.append(_item("mcp", scope, srv, rel))
        for hook in _hook_entries_from_settings(path):
            items.append(_item("hook", scope, hook, rel))
        for pid in _plugin_ids(path):
            items.append(_item("plugin", scope, pid, rel))
    elif name == "hooks.json":
        data = _load_json_object(path) or {}
        hooks = data.get("hooks")
        if isinstance(hooks, list):
            for i, h in enumerate(hooks):
                if isinstance(h, dict):
                    ident = str(h.get("command") or h.get("matcher") or f"hook-{i}")
                    items.append(_item("hook", scope, ident, rel))
        elif path.stat().st_size > 0:
            items.append(_item("hook", scope, rel, rel))
    elif _is_harness_kind_dir(lower_rel, "hooks"):
        if path.suffix.lower() in {".json", ".py", ".sh", ".ps1", ".js", ".mjs", ".ts"}:
            items.append(_item("hook", scope, rel, rel))
    elif _is_harness_kind_dir(lower_rel, "rules"):
        if path.suffix.lower() in {".md", ".mdc", ".txt"}:
            ident = path.stem
            items.append(_item("rule", scope, ident, rel))
    elif name in {"CLAUDE.md", "AGENTS.md"} and scope == "project":
        # Instruction files, not skills/hooks/rules/plugins/MCP. Skip.
        pass
    return items


def collect_from_roots(
    base: Path, roots: tuple[str, ...], *, scope: str
) -> list[dict[str, str]]:
    found: dict[str, dict[str, str]] = {}
    for rel in roots:
        loc = base / rel
        for path in _walk_files(loc):
            for item in classify_file(path, scope=scope, root=base):
                found[item["key"]] = item
    return [found[k] for k in sorted(found)]


def harness_load_roots_status(home: Path) -> dict[str, Any]:
    """Prove whether user-profile harness load roots are absent or empty."""
    rows = []
    dirty = False
    for rel in USER_LOAD_ROOTS:
        loc = home / rel
        exists = loc.exists()
        files = _walk_files(loc) if exists else []
        loadables = []
        for path in files:
            loadables.extend(classify_file(path, scope="user", root=home))
        empty = (not exists) or (len(files) == 0 and loc.is_dir()) or (
            loc.is_file() and loc.stat().st_size == 0
        )
        has_load = bool(loadables)
        if has_load:
            dirty = True
            empty = False
        elif exists and loc.is_file() and loc.stat().st_size > 0:
            # Non-loadable but non-empty config still counts as harness state
            # only when it is a dedicated load-root file (mcp/settings).
            if loc.suffix.lower() == ".json":
                dirty = True
                empty = False
        rows.append(
            {
                "path": rel.replace("\\", "/"),
                "exists": exists,
                "empty_or_absent": empty and not has_load,
                "file_count": len(files),
                "loadable_count": len(loadables),
            }
        )
    return {
        "clean": not dirty,
        "dirty": dirty,
        "roots": rows,
        "home": str(home),
    }


def measure(home: Path, repo: Path) -> dict[str, Any]:
    home = Path(home)
    repo = Path(repo)
    user_items = collect_from_roots(home, USER_LOAD_ROOTS, scope="user")
    project_items = collect_from_roots(repo, REPO_LOAD_ROOTS, scope="project")
    items = user_items + project_items
    counts = {
        "skill": 0,
        "hook": 0,
        "rule": 0,
        "plugin": 0,
        "mcp": 0,
        "user": len(user_items),
        "project": len(project_items),
        "total": len(items),
    }
    for it in items:
        counts[it["kind"]] = counts.get(it["kind"], 0) + 1
    cleanliness = harness_load_roots_status(home)
    return {
        "home": str(home),
        "repo": str(repo),
        "cleanliness": cleanliness,
        "counts": counts,
        "items": items,
        "user_keys": [i["key"] for i in user_items],
        "project_keys": [i["key"] for i in project_items],
        "all_keys": [i["key"] for i in items],
    }


def diff_sets(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    a = set(left.get("all_keys") or [])
    b = set(right.get("all_keys") or [])
    only_left = sorted(a - b)
    only_right = sorted(b - a)
    shared = sorted(a & b)
    return {
        "only_left": only_left,
        "only_right": only_right,
        "shared": shared,
        "only_left_count": len(only_left),
        "only_right_count": len(only_right),
        "shared_count": len(shared),
        "identical": a == b,
        "left_counts": left.get("counts"),
        "right_counts": right.get("counts"),
    }


def make_empty_home() -> tempfile.TemporaryDirectory:
    return tempfile.TemporaryDirectory(prefix="aud0096-clean-")


def plant_skill(home: Path, *, name: str = "planted-leak-control") -> Path:
    dest = home / ".cursor" / "skills-cursor" / name
    dest.mkdir(parents=True, exist_ok=True)
    skill = dest / "SKILL.md"
    skill.write_text(
        "---\nname: planted-leak-control\ndescription: AUD-0096 cleanliness mutant\n---\n"
        "# planted\nNot a real skill. Control fixture.\n",
        encoding="utf-8",
    )
    return skill


def copy_user_skills_into(src_home: Path, dest_home: Path) -> int:
    """Copy documented user-profile load roots (not just SKILL.md). No auth files."""
    copied = 0
    for rel in USER_LOAD_ROOTS:
        src = src_home / rel
        if not src.exists():
            continue
        if src.is_file():
            if _is_secret_name(src.name):
                continue
            dest = dest_home / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            copied += 1
            continue
        for path in _walk_files(src):
            if _is_secret_name(path.name):
                continue
            rel_path = path.relative_to(src_home)
            dest = dest_home / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            copied += 1
    return copied


def both_states_cleanliness_control(repo: Path) -> dict[str, Any]:
    """Empty sandbox must be clean; planted skill must make cleanliness fail."""
    with make_empty_home() as empty_s:
        empty = Path(empty_s)
        good = harness_load_roots_status(empty)
        meas_good = measure(empty, repo)
        plant_skill(empty)
        bad = harness_load_roots_status(empty)
        meas_bad = measure(empty, repo)
        planted_keys = [k for k in meas_bad["user_keys"] if "planted-leak-control" in k]
        return {
            "empty_clean": good["clean"] is True,
            "planted_dirty": bad["clean"] is False,
            "empty_user_loadables": meas_good["counts"]["user"],
            "planted_user_loadables": meas_bad["counts"]["user"],
            "planted_skill_observed": len(planted_keys) == 1,
            "pass": (
                good["clean"] is True
                and bad["clean"] is False
                and meas_good["counts"]["user"] == 0
                and meas_bad["counts"]["user"] >= 1
                and len(planted_keys) == 1
            ),
        }


def leak_identity_control(current_home: Path, repo: Path) -> dict[str, Any]:
    """A sandbox that inherits current user skills must match current user keys.

    This is the catalog control: a leaked profile makes the two runs identical
    by construction. The empty sandbox must NOT match if current is dirty.
    """
    current = measure(current_home, repo)
    with make_empty_home() as empty_s:
        empty = Path(empty_s)
        clean_m = measure(empty, repo)
        copied = copy_user_skills_into(current_home, empty)
        leaked = measure(empty, repo)
    current_user = set(current["user_keys"])
    leaked_user = set(leaked["user_keys"])
    clean_user = set(clean_m["user_keys"])
    current_dirty = current["cleanliness"]["clean"] is False
    identical_when_leaked = current_user == leaked_user
    empty_diverges = (not current_dirty) or (current_user != clean_user)
    return {
        "copied_skill_files": copied,
        "current_user_count": len(current_user),
        "clean_user_count": len(clean_user),
        "leaked_user_count": len(leaked_user),
        "current_dirty": current_dirty,
        "identical_when_leaked": identical_when_leaked,
        "empty_diverges_when_current_dirty": empty_diverges,
        "pass": identical_when_leaked and empty_diverges,
    }
