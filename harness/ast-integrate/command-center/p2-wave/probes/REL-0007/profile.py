"""Disposable canary profile: seed owner files, install, uninstall variants.

Never touches the live user profile. Inverses obey the REL-0002 invariants:
an inverse may not remove a path the installer did not create, and may not
remove a command, skill or setting that pre-dated the install.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from surfaces import (
    DETECTOR_HOOK_ID,
    OWNER_HOOK_ID,
    OWNER_MIRROR,
    OWNER_MCP_ID,
    OWNER_SETTING,
    OWNER_SHIM,
    OWNER_SKILL,
    OWNER_TASK,
    PACKAGE_HOOK_ID,
    PACKAGE_ID,
    PACKAGE_MIRROR,
    PACKAGE_MCP_ID,
    PACKAGE_SETTING,
    PACKAGE_SHIM,
    PACKAGE_SKILL,
    PACKAGE_TASK,
)


def _dump(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def snapshot_owner(root: Path) -> dict[str, str]:
    """sha256 of every owner-authored file that must survive uninstall."""
    import hashlib

    out: dict[str, str] = {}
    for rel in (
        "hooks.json",
        ".mcp.json",
        "settings.json",
        f"skills/{OWNER_SKILL}/SKILL.md",
        f"bin/{OWNER_SHIM}",
        "mirror/index.json",
        "scheduled-tasks.json",
        "path.env",
        "owner-authored/notes.txt",
    ):
        p = root / rel
        raw = p.read_bytes().replace(b"\r\n", b"\n")
        out[rel] = hashlib.sha256(raw).hexdigest()
    return out


def seed_preexisting(root: Path) -> None:
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    _dump(
        root / "hooks.json",
        {"hooks": [{"id": OWNER_HOOK_ID, "event": "PreToolUse", "command": "owner-hook"}]},
    )
    _dump(
        root / ".mcp.json",
        {"mcpServers": {OWNER_MCP_ID: {"command": "owner-mcp", "args": ["--notes"]}}},
    )
    _dump(
        root / "settings.json",
        {OWNER_SETTING: "solarized", "enabledPlugins": {OWNER_MCP_ID: True}},
    )
    skill = root / "skills" / OWNER_SKILL / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("# owner notes\npre-dated skill; uninstall must keep this.\n", encoding="utf-8")
    shim = root / "bin" / OWNER_SHIM
    shim.parent.mkdir(parents=True)
    shim.write_text("#!/bin/sh\necho owner-tool\n", encoding="utf-8")
    shim.chmod(0o755)
    _dump(
        root / "mirror" / "index.json",
        {"entries": [{"id": OWNER_MIRROR, "sha256": "owner"}]},
    )
    _dump(
        root / "scheduled-tasks.json",
        {"tasks": [{"name": OWNER_TASK, "schedule": "daily"}]},
    )
    (root / "path.env").write_text(str((root / "bin").resolve()) + "\n", encoding="utf-8")
    notes = root / "owner-authored" / "notes.txt"
    notes.parent.mkdir(parents=True)
    notes.write_text("owner data; uninstall must not delete this.\n", encoding="utf-8")


def _register_package(root: Path) -> None:
    hooks = _load(root / "hooks.json")
    ids = {h["id"] for h in hooks["hooks"]}
    if PACKAGE_HOOK_ID not in ids:
        hooks["hooks"].append(
            {"id": PACKAGE_HOOK_ID, "event": "PreToolUse", "command": PACKAGE_ID}
        )
    _dump(root / "hooks.json", hooks)

    mcp = _load(root / ".mcp.json")
    mcp["mcpServers"][PACKAGE_MCP_ID] = {"command": PACKAGE_ID, "args": ["--mcp"]}
    _dump(root / ".mcp.json", mcp)

    settings = _load(root / "settings.json")
    settings[PACKAGE_SETTING] = {"installed": True}
    settings.setdefault("enabledPlugins", {})[PACKAGE_ID] = True
    _dump(root / "settings.json", settings)

    sk = root / "skills" / PACKAGE_SKILL / "SKILL.md"
    sk.parent.mkdir(parents=True, exist_ok=True)
    sk.write_text(f"# {PACKAGE_ID}\ncanary skill\n", encoding="utf-8")

    shim = root / "bin" / PACKAGE_SHIM
    shim.write_text(f"#!/bin/sh\necho {PACKAGE_ID}\n", encoding="utf-8")
    shim.chmod(0o755)

    mirror = _load(root / "mirror" / "index.json")
    ids = {e["id"] for e in mirror["entries"]}
    if PACKAGE_MIRROR not in ids:
        mirror["entries"].append({"id": PACKAGE_MIRROR, "sha256": "canary"})
    _dump(root / "mirror" / "index.json", mirror)

    tasks = _load(root / "scheduled-tasks.json")
    names = {t["name"] for t in tasks["tasks"]}
    if PACKAGE_TASK not in names:
        tasks["tasks"].append({"name": PACKAGE_TASK, "schedule": "hourly"})
    _dump(root / "scheduled-tasks.json", tasks)

    payload = root / "opt" / PACKAGE_ID / "payload.txt"
    payload.parent.mkdir(parents=True, exist_ok=True)
    payload.write_text("canary payload\n", encoding="utf-8")


def install(root: Path) -> None:
    _register_package(root)


def _unregister_our_hook(root: Path, hook_id: str) -> None:
    hooks = _load(root / "hooks.json")
    hooks["hooks"] = [h for h in hooks["hooks"] if h.get("id") != hook_id]
    _dump(root / "hooks.json", hooks)


def uninstall_clean(root: Path) -> None:
    """Typed inverses of install. Must not touch owner pre-dated files."""
    _unregister_our_hook(root, PACKAGE_HOOK_ID)
    _unregister_our_hook(root, DETECTOR_HOOK_ID)

    mcp = _load(root / ".mcp.json")
    mcp["mcpServers"].pop(PACKAGE_MCP_ID, None)
    _dump(root / ".mcp.json", mcp)

    settings = _load(root / "settings.json")
    settings.pop(PACKAGE_SETTING, None)
    plugins = settings.get("enabledPlugins") or {}
    plugins.pop(PACKAGE_ID, None)
    settings["enabledPlugins"] = plugins
    _dump(root / "settings.json", settings)

    sk = root / "skills" / PACKAGE_SKILL
    if sk.exists():
        shutil.rmtree(sk)

    shim = root / "bin" / PACKAGE_SHIM
    if shim.exists():
        shim.unlink()

    mirror = _load(root / "mirror" / "index.json")
    mirror["entries"] = [e for e in mirror["entries"] if e.get("id") != PACKAGE_MIRROR]
    _dump(root / "mirror" / "index.json", mirror)

    tasks = _load(root / "scheduled-tasks.json")
    tasks["tasks"] = [t for t in tasks["tasks"] if t.get("name") != PACKAGE_TASK]
    _dump(root / "scheduled-tasks.json", tasks)

    payload = root / "opt" / PACKAGE_ID
    if payload.exists():
        shutil.rmtree(payload)


def uninstall_payload_only(root: Path) -> None:
    """The lie the unit forbids: deleting the payload folder is not deregistration."""
    payload = root / "opt" / PACKAGE_ID
    if payload.exists():
        shutil.rmtree(payload)


def uninstall_leave_hook(root: Path) -> None:
    uninstall_clean(root)
    hooks = _load(root / "hooks.json")
    hooks["hooks"].append(
        {"id": PACKAGE_HOOK_ID, "event": "PreToolUse", "command": PACKAGE_ID}
    )
    _dump(root / "hooks.json", hooks)


def plant_detector_hook(root: Path) -> None:
    hooks = _load(root / "hooks.json")
    ids = {h["id"] for h in hooks["hooks"]}
    if DETECTOR_HOOK_ID not in ids:
        hooks["hooks"].append(
            {
                "id": DETECTOR_HOOK_ID,
                "event": "PreToolUse",
                "command": f"{PACKAGE_ID}-detector",
            }
        )
    _dump(root / "hooks.json", hooks)


def unplant_detector_hook(root: Path) -> None:
    _unregister_our_hook(root, DETECTOR_HOOK_ID)
