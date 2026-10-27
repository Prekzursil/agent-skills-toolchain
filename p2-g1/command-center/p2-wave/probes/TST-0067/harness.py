#!/usr/bin/env python3
"""TST-0067 harness: scope vs observation on this live machine.

Persistent-store analog: a JSON store write that the setter can self-read
but that never mutates the already-running session environment. Session
injection: the parent spawns the consumer child with the value in the child
env. Scope files: root/settings.json vs project/settings.json.
Windows note: the recorded receipt ran on Linux with /proc/<pid>/environ as
the second signal; this live re-run uses kernel32 GetEnvironmentVariableW.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONSUMER = HERE / "consumer.py"

try:  # scenario.py is the constants SSOT when present
    from scenario import (  # noqa: F401
        CONFIG_KEY, ENV_KEY, NEW, OLD, PROJECT_WRITE, ROOT_WRITE,
    )
except ImportError:  # pragma: no cover - fallback keeps the harness standalone
    ENV_KEY = "TST0067_CONSUMER_VAR"
    CONFIG_KEY = "planted.mcp.enabled"
    OLD = "session-old-value"
    NEW = "session-new-value"
    ROOT_WRITE = "root-scope-write-inert"
    PROJECT_WRITE = "project-scope-write-live"


def spawn_consumer(args: list[str], extra_env: dict | None = None) -> dict:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", str(CONSUMER)] + args,
        capture_output=True, text=True, timeout=60, env=env)
    if proc.returncode != 0:
        raise RuntimeError(f"consumer rc={proc.returncode}: {proc.stderr[-300:]}")
    return json.loads(proc.stdout.strip().splitlines()[-1])


def observe_env_child(extra_env: dict | None = None) -> dict:
    return spawn_consumer(["--mode", "env", "--key", ENV_KEY], extra_env)


def observe_settings_child(scope_file: Path) -> dict:
    return spawn_consumer(["--mode", "settings", "--key", CONFIG_KEY,
                           "--scope-file", str(scope_file)])


class PersistentStore:
    """JSON store the setter writes and self-reads; sessions never reload it."""

    def __init__(self, path: Path):
        self.path = path

    def write(self, key: str, value: str) -> None:
        doc = {}
        if self.path.is_file():
            doc = json.loads(self.path.read_text(encoding="utf-8"))
        doc[key] = value
        self.path.write_text(json.dumps(doc), encoding="utf-8")

    def self_read(self, key: str):
        if not self.path.is_file():
            return None
        return json.loads(self.path.read_text(encoding="utf-8")).get(key)


class ScopedSettings:
    def __init__(self, root: Path, project: Path):
        self.root = root
        self.project = project
        root.parent.mkdir(parents=True, exist_ok=True)
        project.parent.mkdir(parents=True, exist_ok=True)
        root.write_text(json.dumps({CONFIG_KEY: OLD}), encoding="utf-8")
        project.write_text(json.dumps({CONFIG_KEY: OLD}), encoding="utf-8")

    def write_root(self, value: str) -> None:
        doc = json.loads(self.root.read_text(encoding="utf-8"))
        doc[CONFIG_KEY] = value
        self.root.write_text(json.dumps(doc), encoding="utf-8")

    def write_project(self, value: str) -> None:
        doc = json.loads(self.project.read_text(encoding="utf-8"))
        doc[CONFIG_KEY] = value
        self.project.write_text(json.dumps(doc), encoding="utf-8")

    def self_read_root(self):
        return json.loads(self.root.read_text(encoding="utf-8")).get(CONFIG_KEY)

    def self_read_project(self):
        return json.loads(self.project.read_text(encoding="utf-8")).get(CONFIG_KEY)
