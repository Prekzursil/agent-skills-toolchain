#!/usr/bin/env python3
"""Throwaway-profile install/uninstall lab for TST-0073.

Never touches the operator HOME, crontab, systemd --user, or live ~/.mcp.json.
Scheduled-task, hook, and MCP surfaces are files inside the disposable profile.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
# Append so probe-local scenario.py stays ahead of tools/plugin/scenario.py.
if str(PLUGIN) not in sys.path:
    sys.path.append(str(PLUGIN))

from hash_census import census_diff, file_digest, hash_census  # noqa: E402

PACKAGE_ID = "ast-plugin"
HOOK_ID = "ast-plugin-hook"
MCP_ID = "ast-plugin-mcp"
TASK_ID = "ast-plugin.timer"
UNRELATED_HOOK = "unrelated-lint"
UNRELATED_MCP = "unrelated-mail"
UNRELATED_TASK = "unrelated.timer"

USER_KEEP = "user-data/keep-me.txt"
USER_NOTES = "user-data/notes.md"
USER_SESSION = "user-data/install-created-session.json"
DOCUMENTED_USER_DATA = (USER_KEEP, USER_NOTES, USER_SESSION)
INSTALL_CREATED_USER_DATA = (USER_SESSION,)

PROJECTION_REL = ".ast-plugin-projection.json"
HOOKS_REL = "hooks/hooks.json"
MCP_REL = ".mcp.json"
SETTINGS_REL = "settings.json"
TASKS_DIR = "scheduled-tasks"
CACHE_REL = ".local/share/ast-plugin/cache.db"

OWNED_FILES = (
    "package/bin/plugin",
    "package/lib/payload.py",
    "package/hooks/on-start.py",
    "package/mcp/server.py",
    CACHE_REL,
    f"{TASKS_DIR}/{TASK_ID}",
    PROJECTION_REL,
)

OWNED_DIRS = (
    "package",
    "package/bin",
    "package/lib",
    "package/hooks",
    "package/mcp",
    ".local/share/ast-plugin",
    ".local/share",
    ".local",
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _dump(path: Path, doc: Any) -> None:
    _write(path, json.dumps(doc, indent=2, sort_keys=True) + "\n")


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def seed_pre_install(root: Path) -> Path:
    """Fresh profile with user data and unrelated registrations already present."""
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    _write(root / USER_KEEP, "owner notebook — must survive uninstall\n")
    _write(root / USER_NOTES, "custom entries the upgrade/uninstall must not wipe\n")
    _dump(
        root / HOOKS_REL,
        {
            "registrations": [
                {
                    "id": UNRELATED_HOOK,
                    "event": "PreToolUse",
                    "command": "echo unrelated-lint",
                }
            ]
        },
    )
    _dump(
        root / MCP_REL,
        {
            "mcpServers": {
                UNRELATED_MCP: {"command": "node", "args": ["mail.js"]},
            }
        },
    )
    _write(
        root / TASKS_DIR / UNRELATED_TASK,
        "[Timer]\nOnCalendar=hourly\nUnit=unrelated.service\n",
    )
    _dump(
        root / SETTINGS_REL,
        {
            "theme": "dark",
            "enabledMcpServers": [UNRELATED_MCP],
            "userFlag": True,
        },
    )
    return root


def list_hook_ids(root: Path) -> list[str]:
    path = root / HOOKS_REL
    if not path.is_file():
        return []
    regs = (_load(path) or {}).get("registrations") or []
    return [str(r.get("id")) for r in regs if isinstance(r, dict) and r.get("id")]


def list_mcp_ids(root: Path) -> list[str]:
    path = root / MCP_REL
    if not path.is_file():
        return []
    servers = (_load(path) or {}).get("mcpServers") or {}
    return sorted(str(k) for k in servers.keys())


def list_task_ids(root: Path) -> list[str]:
    d = root / TASKS_DIR
    if not d.is_dir():
        return []
    return sorted(p.name for p in d.iterdir() if p.is_file())


def list_settings_keys(root: Path) -> list[str]:
    path = root / SETTINGS_REL
    if not path.is_file():
        return []
    doc = _load(path)
    return sorted(doc.keys()) if isinstance(doc, dict) else []


def snapshot(root: Path) -> dict[str, Any]:
    return {
        "census": hash_census(root),
        "hooks": list_hook_ids(root),
        "mcp": list_mcp_ids(root),
        "tasks": list_task_ids(root),
        "settings_keys": list_settings_keys(root),
    }


def package_orphans(snap: dict[str, Any]) -> dict[str, list[str]]:
    return {
        "hooks": [h for h in snap.get("hooks") or [] if h == HOOK_ID],
        "mcp": [m for m in snap.get("mcp") or [] if m == MCP_ID],
        "tasks": [t for t in snap.get("tasks") or [] if t == TASK_ID],
        "settings": [
            k for k in snap.get("settings_keys") or [] if k == "astPluginInstalled"
        ],
    }


def orphan_count(orphans: dict[str, list[str]]) -> int:
    return sum(len(v) for v in orphans.values())


def activate(root: Path) -> dict[str, list[str]]:
    """In-process host load: which registrations would still fire."""
    return {
        "hooks": list_hook_ids(root),
        "mcp": list_mcp_ids(root),
        "tasks": list_task_ids(root),
    }


def install(root: Path) -> dict[str, Any]:
    """Install package-owned payload + registrations into the throwaway profile."""
    _write(root / "package/bin/plugin", "#!/bin/sh\necho ast-plugin\n")
    _write(root / "package/lib/payload.py", "PACKAGE = 'ast-plugin'\n")
    _write(root / "package/hooks/on-start.py", "print('ast-plugin hook')\n")
    _write(root / "package/mcp/server.py", "print('ast-plugin mcp')\n")
    _write(root / CACHE_REL, "cache-v1\n")
    _write(
        root / TASKS_DIR / TASK_ID,
        "[Timer]\nOnCalendar=*:0/15\nUnit=ast-plugin.service\n",
    )
    _write(
        root / USER_SESSION,
        json.dumps({"created_by": "install", "keep": True}, indent=2) + "\n",
    )

    hooks = _load(root / HOOKS_REL)
    hooks.setdefault("registrations", []).append(
        {
            "id": HOOK_ID,
            "event": "SessionStart",
            "command": "python3 package/hooks/on-start.py",
        }
    )
    _dump(root / HOOKS_REL, hooks)

    mcp = _load(root / MCP_REL)
    mcp.setdefault("mcpServers", {})[MCP_ID] = {
        "command": "python3",
        "args": ["package/mcp/server.py"],
    }
    _dump(root / MCP_REL, mcp)

    settings = _load(root / SETTINGS_REL)
    settings["astPluginInstalled"] = True
    enabled = list(settings.get("enabledMcpServers") or [])
    if MCP_ID not in enabled:
        enabled.append(MCP_ID)
    settings["enabledMcpServers"] = enabled
    _dump(root / SETTINGS_REL, settings)

    projection = {
        "package_id": PACKAGE_ID,
        "owned_files": list(OWNED_FILES),
        "owned_dirs": list(OWNED_DIRS),
        "hook_ids": [HOOK_ID],
        "mcp_ids": [MCP_ID],
        "task_ids": [TASK_ID],
        "settings_keys": ["astPluginInstalled"],
        "settings_list_entries": {"enabledMcpServers": [MCP_ID]},
        "documented_user_data": list(DOCUMENTED_USER_DATA),
        "install_created_user_data": list(INSTALL_CREATED_USER_DATA),
    }
    _dump(root / PROJECTION_REL, projection)
    return {"projection": projection, "snapshot": snapshot(root)}


def _remove_hook_ids(root: Path, ids: Iterable[str]) -> None:
    path = root / HOOKS_REL
    if not path.is_file():
        return
    drop = set(ids)
    doc = _load(path)
    doc["registrations"] = [
        r
        for r in (doc.get("registrations") or [])
        if not (isinstance(r, dict) and r.get("id") in drop)
    ]
    _dump(path, doc)


def _remove_mcp_ids(root: Path, ids: Iterable[str]) -> None:
    path = root / MCP_REL
    if not path.is_file():
        return
    drop = set(ids)
    doc = _load(path)
    servers = doc.get("mcpServers") or {}
    for k in list(servers):
        if k in drop:
            del servers[k]
    doc["mcpServers"] = servers
    _dump(path, doc)


def _remove_tasks(root: Path, ids: Iterable[str]) -> None:
    for name in ids:
        path = root / TASKS_DIR / name
        if path.is_file():
            path.unlink()


def _restore_settings(root: Path, projection: dict[str, Any]) -> None:
    path = root / SETTINGS_REL
    if not path.is_file():
        return
    doc = _load(path)
    for key in projection.get("settings_keys") or []:
        doc.pop(key, None)
    for list_key, values in (projection.get("settings_list_entries") or {}).items():
        cur = doc.get(list_key)
        if isinstance(cur, list):
            drop = set(values)
            doc[list_key] = [x for x in cur if x not in drop]
    _dump(path, doc)


def _delete_owned_files(root: Path, projection: dict[str, Any], retain: set[str]) -> None:
    for rel in projection.get("owned_files") or []:
        if rel in retain:
            continue
        path = root / rel
        if path.is_file():
            path.unlink()
    dirs = sorted(projection.get("owned_dirs") or [], key=lambda s: s.count("/"), reverse=True)
    for rel in dirs:
        path = root / rel
        if path.is_dir():
            try:
                path.rmdir()
            except OSError:
                pass


def uninstall(
    root: Path,
    projection: dict[str, Any] | None = None,
    *,
    mode: str = "complete",
    retain_user_data: bool = True,
) -> dict[str, Any]:
    """Remove package-owned payload and registrations.

    mode:
      complete     — deregister hooks/MCP/tasks and delete owned files; retain user data
      payload_only — delete package/ tree only (the green-not-live failure: folder gone, regs stay)
      scorched     — delete everything under the profile (passes 'no orphans', kills user data)
    """
    proj_path = root / PROJECTION_REL
    if projection is None:
        if not proj_path.is_file():
            raise FileNotFoundError("projection map missing; cannot uninstall")
        projection = _load(proj_path)

    retain: set[str] = set()
    if retain_user_data:
        retain.update(projection.get("documented_user_data") or [])
        retain.update(projection.get("install_created_user_data") or [])

    if mode == "scorched":
        for child in list(root.iterdir()):
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        return {"mode": mode, "retain_user_data": False}

    if mode == "payload_only":
        pkg = root / "package"
        if pkg.is_dir():
            shutil.rmtree(pkg)
        return {"mode": mode, "retain_user_data": retain_user_data}

    _remove_hook_ids(root, projection.get("hook_ids") or [])
    _remove_mcp_ids(root, projection.get("mcp_ids") or [])
    _remove_tasks(root, projection.get("task_ids") or [])
    _restore_settings(root, projection)
    _delete_owned_files(root, projection, retain)
    return {"mode": mode, "retain_user_data": retain_user_data}


def classify_diff(
    pre: dict[str, str],
    post: dict[str, str],
    documented_extra: Iterable[str],
) -> dict[str, Any]:
    raw = census_diff(pre, post)
    allowed = set(documented_extra)
    extras = []
    for rel in raw["extra"]:
        kind = "documented-intentional" if rel in allowed else "defect"
        extras.append({"path": rel, "kind": kind})
    missing = [{"path": rel, "kind": "defect"} for rel in raw["missing"]]
    changed = [{"path": rel, "kind": "defect"} for rel in raw["changed"]]
    defects = [
        row
        for row in extras + missing + changed
        if row["kind"] == "defect"
    ]
    documented = [row for row in extras if row["kind"] == "documented-intentional"]
    return {
        "equal_except_documented": not defects,
        "extra": extras,
        "missing": missing,
        "changed": changed,
        "defects": defects,
        "documented_residuals": documented,
        "unchanged_count": (
            len(pre) - len(raw["missing"]) - len(raw["changed"])
        ),
        "pre_count": len(pre),
        "post_count": len(post),
    }


def user_data_survival(root: Path, pre_census: dict[str, str]) -> dict[str, Any]:
    rows = []
    ok = True
    for rel in DOCUMENTED_USER_DATA:
        path = root / rel
        present = path.is_file()
        pre_hash = pre_census.get(rel)
        post_hash = None
        if present:
            post_hash = file_digest(path.read_bytes())
        identical = bool(present and pre_hash and post_hash == pre_hash)
        created_at_install = rel in INSTALL_CREATED_USER_DATA
        if created_at_install:
            # Did not exist pre-install; survival = still present after uninstall.
            row_ok = present
        else:
            row_ok = identical
        ok = ok and row_ok
        rows.append(
            {
                "path": rel,
                "present": present,
                "pre_hash": pre_hash,
                "post_hash": post_hash,
                "byte_identical_to_pre": identical,
                "created_at_install": created_at_install,
                "ok": row_ok,
            }
        )
    return {"ok": ok, "rows": rows}
