"""Hermetic install/uninstall subject for CNF-0107.

This sparse worktree does not vendor tools/plugin. The subject implements the
catalogued IMP-0027 contract: remove exactly the projection-map owned paths;
retain user-authored data unless --purge-user-data; never touch out-of-scope
host files. Broken modes exist only so the detector control can fire.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

HERE = Path(__file__).resolve().parent
SEED = HERE / "fixtures" / "seed"
OOS = HERE / "fixtures" / "out-of-scope"

UninstallMode = Literal["healthy", "leave_orphan", "scorch", "poison"]

PLUGIN_ROOT = ".ast-plugin"
OWNED = (
    f"{PLUGIN_ROOT}/bin/plugin",
    f"{PLUGIN_ROOT}/lib/runtime.py",
    f"{PLUGIN_ROOT}/hooks/pre-tool.json",
    f"{PLUGIN_ROOT}/mcp/server.json",
    f"{PLUGIN_ROOT}/cache/index.json",
    f"{PLUGIN_ROOT}/install-marker.json",
)
USER_DATA = (
    f"{PLUGIN_ROOT}/user-data/notes.md",
    f"{PLUGIN_ROOT}/user-data/settings.json",
)
OUT_OF_SCOPE = (
    "host-app/unrelated-skill.md",
    "host-app/shared-settings.json",
)
OOS_CONTROL = OUT_OF_SCOPE[0]
MARKER = f"{PLUGIN_ROOT}/install-marker.json"
ORPHAN_LEFT = f"{PLUGIN_ROOT}/cache/index.json"


@dataclass(frozen=True)
class Scope:
    owned: frozenset[str]
    user_data: frozenset[str]
    out_of_scope: frozenset[str]


SCOPE = Scope(
    owned=frozenset(OWNED),
    user_data=frozenset(USER_DATA),
    out_of_scope=frozenset(OUT_OF_SCOPE),
)


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def snapshot(root: Path) -> dict:
    files: list[dict] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        raw = p.read_bytes()
        files.append(
            {
                "path": rel,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
            }
        )
    blob = json.dumps(files, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "files": files,
        "file_count": len(files),
        "digest": hashlib.sha256(blob).hexdigest(),
    }


def seed_host(root: Path) -> None:
    skill = (OOS / "unrelated-skill.md").read_bytes()
    _write(root / OUT_OF_SCOPE[0], skill)
    _write(
        root / OUT_OF_SCOPE[1],
        b'{"host":"untouched","canary":"CNF-0107-OOS-SETTINGS"}\n',
    )


def install(root: Path) -> None:
    payload = {
        f"{PLUGIN_ROOT}/bin/plugin": b"#!/usr/bin/env python3\nprint('plugin-ok')\n",
        f"{PLUGIN_ROOT}/lib/runtime.py": b"VERSION = '1.0.0'\n",
        f"{PLUGIN_ROOT}/hooks/pre-tool.json": b'{"hook":"pre-tool","enabled":true}\n',
        f"{PLUGIN_ROOT}/mcp/server.json": b'{"mcp":"fixture","port":0}\n',
        f"{PLUGIN_ROOT}/cache/index.json": b'{"entries":[]}\n',
        MARKER: b'{"status":"installed","version":"1.0.0"}\n',
    }
    for rel, data in payload.items():
        _write(root / rel, data)


def seed_user_data(root: Path) -> None:
    _write(root / USER_DATA[0], (SEED / "notes.md").read_bytes())
    _write(root / USER_DATA[1], (SEED / "settings.json").read_bytes())


def _unlink(path: Path) -> None:
    if path.is_file():
        path.unlink()


def _prune_empty(root: Path, rel_file: str) -> None:
    parent = (root / rel_file).parent
    while parent != root and parent.is_dir() and not any(parent.iterdir()):
        parent.rmdir()
        parent = parent.parent


def uninstall(
    root: Path,
    *,
    mode: UninstallMode = "healthy",
    purge_user_data: bool = False,
) -> None:
    if mode == "scorch":
        for p in sorted(root.rglob("*"), reverse=True):
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                p.rmdir()
        return

    skip = {ORPHAN_LEFT} if mode == "leave_orphan" else set()
    for rel in OWNED:
        if rel in skip:
            continue
        if mode == "poison" and rel == MARKER:
            _write(root / MARKER, b'{"status":"corrupt","version":"1.0.0"}\n')
            continue
        _unlink(root / rel)
        _prune_empty(root, rel)

    if purge_user_data:
        for rel in USER_DATA:
            _unlink(root / rel)
            _prune_empty(root, rel)


def reinstall(root: Path) -> dict:
    marker = root / MARKER
    if marker.is_file():
        try:
            doc = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            doc = {"status": "unreadable"}
        if doc.get("status") != "installed":
            return {
                "attempted": True,
                "succeeded": False,
                "poisoned": True,
                "exit_code": 2,
                "detail": f"poisoned marker status={doc.get('status')!r}",
                "owned_paths_restored": [],
            }
    try:
        install(root)
    except OSError as exc:
        return {
            "attempted": True,
            "succeeded": False,
            "poisoned": False,
            "exit_code": 1,
            "detail": str(exc),
            "owned_paths_restored": [],
        }
    restored = [rel for rel in OWNED if (root / rel).is_file()]
    ok = set(restored) == set(OWNED)
    return {
        "attempted": True,
        "succeeded": ok,
        "poisoned": False,
        "exit_code": 0 if ok else 1,
        "detail": "reinstall restored owned projection" if ok else "owned path missing after reinstall",
        "owned_paths_restored": restored,
    }


def run_cycle(root: Path, *, mode: UninstallMode = "healthy", purge_user_data: bool = False) -> dict:
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    seed_host(root)
    pre = snapshot(root)
    pre["label"] = "pre-install"
    install(root)
    seed_user_data(root)
    post_install = snapshot(root)
    post_install["label"] = "post-install"
    uninstall(root, mode=mode, purge_user_data=purge_user_data)
    post_uninstall = snapshot(root)
    post_uninstall["label"] = "post-uninstall"
    reinstall_result = reinstall(root)
    return {
        "pre": pre,
        "post_install": post_install,
        "post_uninstall": post_uninstall,
        "reinstall": reinstall_result,
        "scope": {
            "owned": sorted(SCOPE.owned),
            "user_data": sorted(SCOPE.user_data),
            "out_of_scope": sorted(SCOPE.out_of_scope),
        },
        "mode": mode,
        "purge_user_data": purge_user_data,
    }
