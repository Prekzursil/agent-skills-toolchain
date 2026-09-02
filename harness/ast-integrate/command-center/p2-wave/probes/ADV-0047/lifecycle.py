"""Disposable profile, three-point snapshots, install and uninstall.

Uninstall follows the IMP-0027 projection-map contract: delete owned plugin
paths only; retain user-authored data by default. Caches, logs, transcripts,
credentials, registry analog keys, scheduled tasks and MCP registrations are
outside that map unless listed. This unit measures what that contract leaves.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from common import (
    HOOK_ID,
    PACKAGE_ID,
    PROFILE_USER,
    REGISTRY_KEY,
    SYNTHETIC_TOKEN,
    TASK_ID,
    UNRELATED_MCP,
    USER_NOTE,
)

HERE = Path(__file__).resolve().parent
HOST_APP = HERE / "host_application.py"

HOOK_BODY = '''#!/usr/bin/env python3
from __future__ import annotations
import json, os
from pathlib import Path
effect = Path(os.environ["ADV0047_EFFECT_DIR"])
effect.mkdir(parents=True, exist_ok=True)
payload = {
    "kind": "hook",
    "id": os.environ.get("ADV0047_HOOK_ID", ""),
    "pid": os.getpid(),
    "ppid": os.getppid(),
}
(effect / "hook.json").write_text(json.dumps(payload) + "\\n", encoding="utf-8")
'''

KEEPALIVE_BODY = '''#!/usr/bin/env python3
from __future__ import annotations
import json, os, sys
from pathlib import Path
effect = Path(os.environ["ADV0047_EFFECT_DIR"])
effect.mkdir(parents=True, exist_ok=True)
kind = sys.argv[1] if len(sys.argv) > 1 else "keepalive"
payload = {"kind": kind, "pid": os.getpid(), "ppid": os.getppid()}
(effect / (kind + ".json")).write_text(json.dumps(payload) + "\\n", encoding="utf-8")
'''


def win_join(*parts: str) -> str:
    return "\\".join(parts)


class Profile:
    """Windows-layout isolated USERPROFILE on this Linux host."""

    def __init__(self, root: Path) -> None:
        self.host_root = root
        self.userprofile = root / "Users" / PROFILE_USER
        self.appdata = self.userprofile / "AppData" / "Roaming"
        self.localappdata = self.userprofile / "AppData" / "Local"
        self.harness = self.appdata / "harness"
        self.plugin_root = self.harness / "plugins" / PACKAGE_ID
        self.cache_dir = self.harness / "cache" / PACKAGE_ID
        self.logs_dir = self.harness / "logs"
        self.transcripts_dir = self.harness / "transcripts"
        self.cred_dir = self.harness / "credentials"
        self.tasks_dir = self.harness / "tasks"
        self.mcp_dir = self.appdata / "mcp"
        self.docs = self.userprofile / "Documents"
        self.effect_dir = self.harness / "activations"
        self.registry_path = self.harness / "registry.json"
        self.mcp_path = self.mcp_dir / "mcp.json"
        self.user_note = self.docs / "owner-notes.txt"
        self.token_path = self.cred_dir / "plugin.token"
        self.task_path = self.tasks_dir / f"{TASK_ID}.json"
        self.keepalive = self.cache_dir / "keepalive.py"
        self.win_userprofile = win_join("C:", "Users", PROFILE_USER)

    def materialize_empty(self) -> None:
        self.userprofile.mkdir(parents=True, exist_ok=True)
        self.appdata.mkdir(parents=True, exist_ok=True)
        self.localappdata.mkdir(parents=True, exist_ok=True)
        self.docs.mkdir(parents=True, exist_ok=True)

    def env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["USERPROFILE"] = str(self.userprofile)
        env["HOME"] = str(self.userprofile)
        env["APPDATA"] = str(self.appdata)
        env["LOCALAPPDATA"] = str(self.localappdata)
        env["ADV0047_PROFILE"] = str(self.userprofile)
        env["ADV0047_EFFECT_DIR"] = str(self.effect_dir)
        env["ADV0047_HOOK_ID"] = HOOK_ID
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return env


def _file_digest(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def snapshot(profile: Profile) -> dict[str, Any]:
    files: dict[str, Any] = {}
    if profile.userprofile.is_dir():
        for p in sorted(profile.userprofile.rglob("*")):
            if p.is_file():
                rel = p.relative_to(profile.userprofile).as_posix()
                files[rel] = _file_digest(p)
    registry: dict[str, Any] = {}
    if profile.registry_path.is_file():
        try:
            registry = json.loads(profile.registry_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            registry = {"_unreadable": True}
    tasks: dict[str, Any] = {}
    if profile.tasks_dir.is_dir():
        for p in sorted(profile.tasks_dir.glob("*.json")):
            try:
                tasks[p.stem] = json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                tasks[p.stem] = {"_unreadable": True}
    mcp: dict[str, Any] = {}
    if profile.mcp_path.is_file():
        try:
            body = json.loads(profile.mcp_path.read_text(encoding="utf-8"))
            servers = body.get("mcpServers") or {}
            if isinstance(servers, dict):
                mcp = {k: {"present": True} for k in servers}
        except json.JSONDecodeError:
            mcp = {"_unreadable": True}
    return {
        "files": files,
        "registry_keys": sorted(registry.keys()) if isinstance(registry, dict) else [],
        "registry": registry,
        "tasks": sorted(tasks.keys()),
        "task_bodies": tasks,
        "mcp_servers": sorted(k for k in mcp if not str(k).startswith("_")),
        "mcp": mcp,
    }


def install_package(profile: Profile) -> dict[str, Any]:
    profile.plugin_root.mkdir(parents=True, exist_ok=True)
    profile.cache_dir.mkdir(parents=True, exist_ok=True)
    profile.logs_dir.mkdir(parents=True, exist_ok=True)
    profile.transcripts_dir.mkdir(parents=True, exist_ok=True)
    profile.cred_dir.mkdir(parents=True, exist_ok=True)
    profile.tasks_dir.mkdir(parents=True, exist_ok=True)
    profile.mcp_dir.mkdir(parents=True, exist_ok=True)
    profile.docs.mkdir(parents=True, exist_ok=True)

    hook = profile.plugin_root / "hooks" / "session-start.py"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(HOOK_BODY, encoding="utf-8")
    hook.chmod(0o755)
    (profile.plugin_root / "plugin.json").write_text(
        json.dumps(
            {
                "id": PACKAGE_ID,
                "hooks": [{"id": HOOK_ID, "script": "hooks/session-start.py"}],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (profile.plugin_root / "hooks.json").write_text(
        json.dumps(
            {
                "hooks": [
                    {
                        "id": HOOK_ID,
                        "event": "SessionStart",
                        "script": "hooks/session-start.py",
                        "enabled": True,
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    profile.keepalive.write_text(KEEPALIVE_BODY, encoding="utf-8")
    profile.keepalive.chmod(0o755)
    (profile.cache_dir / "index.bin").write_bytes(b"ADV0047-CACHE-BLOB\n")
    (profile.logs_dir / f"{PACKAGE_ID}.log").write_text(
        "session opened path=/Users/" + PROFILE_USER + "/secret-project\n",
        encoding="utf-8",
    )
    (profile.transcripts_dir / f"{PACKAGE_ID}.jsonl").write_text(
        json.dumps({"role": "user", "text": "private owner utterance"}) + "\n",
        encoding="utf-8",
    )
    profile.token_path.write_text(SYNTHETIC_TOKEN + "\n", encoding="utf-8")
    profile.registry_path.write_text(
        json.dumps(
            {
                REGISTRY_KEY: {
                    "InstallDir": str(profile.plugin_root),
                    "ApiTokenRef": "credentials/plugin.token",
                    "Keepalive": str(profile.keepalive),
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    profile.task_path.write_text(
        json.dumps(
            {
                "id": TASK_ID,
                "enabled": True,
                "command": str(profile.keepalive),
                "args": ["task"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    profile.mcp_path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    PACKAGE_ID: {
                        "command": str(profile.keepalive),
                        "args": ["mcp"],
                    },
                    UNRELATED_MCP: {
                        "command": "true",
                        "args": [],
                    },
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    # Seed owner-authored user data after the package lands (not package-owned).
    profile.user_note.write_text(USER_NOTE + "\n", encoding="utf-8")
    projection = {
        "owned_prefixes": [
            Path("AppData/Roaming/harness/plugins") / PACKAGE_ID
        ]
    }
    (profile.plugin_root / "projection-map.json").write_text(
        json.dumps(
            {"owned_prefixes": [str(p).replace("\\", "/") for p in projection["owned_prefixes"]]},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "ok": profile.plugin_root.is_dir() and profile.keepalive.is_file(),
        "plugin_root": str(profile.plugin_root),
        "owned_prefixes": [str(p).replace("\\", "/") for p in projection["owned_prefixes"]],
        "user_note": str(profile.user_note),
    }


def owned_relpaths(profile: Profile) -> list[str]:
    prefix = f"AppData/Roaming/harness/plugins/{PACKAGE_ID}"
    return [prefix, prefix + "/"]


def uninstall_package(profile: Profile, *, purge_user_data: bool = False) -> dict[str, Any]:
    """Remove projection-map owned paths only. Default retains user data."""
    removed: list[str] = []
    if profile.plugin_root.exists():
        shutil.rmtree(profile.plugin_root)
        removed.append(
            (Path("AppData/Roaming/harness/plugins") / PACKAGE_ID).as_posix()
        )
    user_deleted = False
    if purge_user_data and profile.user_note.is_file():
        profile.user_note.unlink()
        user_deleted = True
    native_reg = _native_registry_probe()
    return {
        "ok": not profile.plugin_root.exists(),
        "purge_user_data": purge_user_data,
        "removed_owned": removed,
        "user_data_deleted": user_deleted,
        "native_registry": native_reg,
        "contract": "projection-map-owned-paths-only; user data retained unless --purge-user-data",
    }


def _native_registry_probe() -> dict[str, Any]:
    """Windows `reg.exe` is not present on this Linux host."""
    exe = shutil.which("reg") or shutil.which("reg.exe")
    # WSL's /mnt/c/WINDOWS/system32/reg.exe hangs from Linux subprocesses.
    if not exe or "/mnt/" in exe.replace("\\", "/") or exe.lower().endswith("\\reg.exe"):
        return {
            "available": False,
            "reason": "linux-host-no-reg.exe",
            "checked": True,
        }
    try:
        proc = subprocess.run(
            [exe, "query", REGISTRY_KEY],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except OSError as exc:
        return {"available": False, "reason": str(exc), "checked": True}
    return {
        "available": True,
        "exit_code": proc.returncode,
        "stdout_tail": (proc.stdout or "")[-500:],
        "checked": True,
    }


def launch_host(profile: Profile) -> dict[str, Any]:
    if profile.effect_dir.exists():
        shutil.rmtree(profile.effect_dir)
    profile.effect_dir.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [sys.executable, "-B", str(HOST_APP)],
        cwd=str(HERE),
        env=profile.env(),
        capture_output=True,
        text=True,
        timeout=30,
    )
    parsed: dict[str, Any] | None = None
    stdout = proc.stdout or ""
    try:
        parsed = json.loads(stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError, ValueError):
        parsed = None
    return {
        "exit_code": proc.returncode,
        "stdout": stdout[-4000:],
        "stderr": (proc.stderr or "")[-1000:],
        "activations": parsed if isinstance(parsed, dict) else {},
        "host": str(HOST_APP.relative_to(HERE.parents[3]).as_posix())
        if HERE.parents[3] in HOST_APP.parents or HOST_APP.is_relative_to(HERE.parents[3])
        else str(HOST_APP),
    }


def classify_residue(
    pre: dict[str, Any],
    post_install: dict[str, Any],
    post_uninstall: dict[str, Any],
    profile: Profile,
) -> dict[str, Any]:
    pre_files = set(pre["files"])
    post_i = set(post_install["files"])
    post_u = set(post_uninstall["files"])
    install_created = sorted(post_i - pre_files)
    still = sorted(set(install_created) & post_u)
    removed = sorted(set(install_created) - post_u)
    user_note_rel = profile.user_note.relative_to(profile.userprofile).as_posix()
    user_data_rels = {user_note_rel}
    intentional = [p for p in still if p in user_data_rels or p.startswith("Documents/")]
    unintentional = [p for p in still if p not in set(intentional)]
    privacy_suffixes = (
        "/credentials/",
        "/transcripts/",
        "/logs/",
        "/cache/",
        "plugin.token",
        "registry.json",
        "owner-notes.txt",
    )
    privacy_relevant = [
        p
        for p in still
        if any(s in p or p.endswith(s.lstrip("/")) for s in privacy_suffixes)
        or "credentials" in p
        or "transcripts" in p
        or p.endswith(".token")
        or p.endswith(".log")
        or p.endswith(".jsonl")
    ]
    reg_pre = set(pre.get("registry_keys") or [])
    reg_i = set(post_install.get("registry_keys") or [])
    reg_u = set(post_uninstall.get("registry_keys") or [])
    reg_created = sorted(reg_i - reg_pre)
    reg_residue = sorted(set(reg_created) & reg_u)
    task_pre = set(pre.get("tasks") or [])
    task_i = set(post_install.get("tasks") or [])
    task_u = set(post_uninstall.get("tasks") or [])
    task_created = sorted(task_i - task_pre)
    task_residue = sorted(set(task_created) & task_u)
    mcp_pre = set(pre.get("mcp_servers") or [])
    mcp_i = set(post_install.get("mcp_servers") or [])
    mcp_u = set(post_uninstall.get("mcp_servers") or [])
    mcp_created = sorted(mcp_i - mcp_pre)
    mcp_residue = sorted(set(mcp_created) & mcp_u)
    user_kept = user_note_rel in post_u and profile.user_note.is_file()
    user_bytes_ok = False
    if user_kept:
        user_bytes_ok = profile.user_note.read_text(encoding="utf-8") == USER_NOTE + "\n"
    return {
        "install_created_files": install_created,
        "install_created_count": len(install_created),
        "removed_files": removed,
        "residue_files": still,
        "intentional_retention": intentional,
        "unintentional_residue": unintentional,
        "privacy_relevant": privacy_relevant,
        "registry_created": reg_created,
        "registry_residue": reg_residue,
        "tasks_created": task_created,
        "tasks_residue": task_residue,
        "mcp_created": mcp_created,
        "mcp_residue": mcp_residue,
        "user_data_kept": user_kept,
        "user_data_byte_identical": user_bytes_ok,
        "user_data_deleted": (not user_kept),
        "control_install_created_nonempty": len(install_created) > 0,
    }
