"""Build loaded (accumulated harness) vs fresh (empty) isolated homes."""
from __future__ import annotations

import json
import os
import shutil
import stat
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOMES = HERE / "run-homes"
DEFAULT_PATH = "/usr/bin:/bin:/usr/local/bin"


def rel_files(root: Path) -> list[str]:
    if not root.is_dir():
        return []
    out: list[str] = []
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out.append(p.relative_to(root).as_posix())
    return out


def profile_env(home: Path, *, extra_bin: bool) -> dict[str, str]:
    import sys

    py_dir = str(Path(sys.executable).resolve().parent)
    path = py_dir + ":" + DEFAULT_PATH
    if extra_bin:
        path = str(home / ".local" / "bin") + ":" + path
    env = {
        "HOME": str(home),
        "USERPROFILE": str(home),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "PATH": path,
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_SYSTEM": "/dev/null",
    }
    gitcfg = home / ".gitconfig"
    if gitcfg.is_file():
        env["GIT_CONFIG_GLOBAL"] = str(gitcfg)
    return env


def _write(path: Path, text: str, *, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if mode is not None:
        path.chmod(mode)


def plant_loaded(home: Path) -> None:
    _write(
        home / ".gitconfig",
        "[core]\n\tautocrlf = true\n[user]\n\tname = cnf-0017-loaded\n"
        "\temail = cnf-0017-loaded@local\n",
    )
    _write(
        home / ".claude" / "plugins" / "accumulated" / "plugin.json",
        json.dumps({"name": "accumulated-debug", "version": "0.0.1"}) + "\n",
    )
    _write(
        home / ".claude" / "skills" / "stale" / "SKILL.md",
        "# stale accumulated skill\nThis skill exists only in the loaded profile.\n",
    )
    _write(
        home / ".cursor" / "mcp.json",
        json.dumps({"mcpServers": {"local-debug": {"command": "false"}}}) + "\n",
    )
    shim = home / ".local" / "bin" / "cnf0017-shim"
    _write(shim, "#!/bin/sh\nexit 1\n", mode=stat.S_IRWXU)


def host_harness_presence() -> dict[str, bool]:
    """Record whether the host has harness dirs. Do not copy them (secrets/chats)."""
    host = Path.home()
    return {
        ".claude": (host / ".claude").is_dir(),
        ".cursor": (host / ".cursor").is_dir(),
        ".codex": (host / ".codex").is_dir(),
        ".gitconfig": (host / ".gitconfig").is_file(),
    }


def build_homes() -> dict:
    if HOMES.exists():
        shutil.rmtree(HOMES)
    fresh = HOMES / "fresh"
    loaded = HOMES / "loaded"
    fresh.mkdir(parents=True)
    loaded.mkdir(parents=True)
    fresh_listing_start = rel_files(fresh)
    plant_loaded(loaded)
    return {
        "fresh": {
            "id": "fresh",
            "path": str(fresh),
            "kind": "fresh",
            "listing_at_start": fresh_listing_start,
            "empty_at_start": fresh_listing_start == [],
        },
        "loaded": {
            "id": "loaded",
            "path": str(loaded),
            "kind": "loaded",
            "listing": rel_files(loaded),
            "host_harness_copied": [],
            "host_harness_present": host_harness_presence(),
        },
    }
