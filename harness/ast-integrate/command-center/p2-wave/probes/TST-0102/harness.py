#!/usr/bin/env python3
"""Sandboxed MCP-style session spawn for TST-0102.

Does not read or write live Cursor/Claude MCP config. Supervisors spawn real
OS children whose argv carries --mcp-worker plus a unique token; census is
taken from /proc cmdline, never from the in-memory Popen list.

Designed policy: one shared worker per enabled server (count == M).
Eager/fault policy: one worker per (session, server) (count == N*M).

Enablement is resolved only at the effective scope (user). A disable written
at project or session is inert: the config file can look correct while the
process table still shows the server.
"""
from __future__ import annotations

import copy
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
WORKER = HERE / "worker.py"
WORKER_MARK = "--mcp-worker"
EFFECTIVE_SCOPE = "user"
INERT_SCOPES = ("project", "session")
SCOPES = ("user", "project", "session")
SERVERS = ("alpha", "bravo", "charlie", "delta")
TARGET_SERVER = "charlie"
PROC = Path("/proc")


def make_token(label: str) -> str:
    return f"mcp-spawn-{label}-{uuid.uuid4().hex[:12]}"


def new_config(servers: tuple[str, ...] = SERVERS, enabled: bool = True) -> dict:
    scopes: dict[str, Any] = {}
    for scope in SCOPES:
        scopes[scope] = {
            "servers": {name: {"enabled": enabled if scope == EFFECTIVE_SCOPE else True} for name in servers}
        }
    return {
        "effective_scope": EFFECTIVE_SCOPE,
        "inert_scopes": list(INERT_SCOPES),
        "scopes": scopes,
    }


def set_enabled(config: dict, scope: str, server: str, enabled: bool) -> dict:
    out = copy.deepcopy(config)
    servers = out["scopes"].setdefault(scope, {}).setdefault("servers", {})
    servers[server] = {"enabled": bool(enabled)}
    return out


def is_effectively_enabled(config: dict, server: str) -> bool:
    scope = str(config.get("effective_scope") or EFFECTIVE_SCOPE)
    row = (config.get("scopes") or {}).get(scope, {}).get("servers", {}).get(server) or {}
    return bool(row.get("enabled", True))


def enabled_servers(config: dict, servers: tuple[str, ...] = SERVERS) -> list[str]:
    return [name for name in servers if is_effectively_enabled(config, name)]


def write_config(root: Path, config: dict) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / "mcp-config.json"
    path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _cmdline(pid: int) -> str | None:
    try:
        raw = (PROC / str(pid) / "cmdline").read_bytes()
    except (OSError, PermissionError):
        return None
    return raw.replace(b"\x00", b" ").decode("utf-8", "replace")


def census(token: str, server: str | None = None) -> list[dict]:
    """Count live workers from the OS process table. Never matches the probe."""
    if not PROC.is_dir():
        raise RuntimeError("os-process-table unavailable: /proc is not a directory")
    found: list[dict] = []
    my_pid = os.getpid()
    for entry in PROC.iterdir():
        name = entry.name
        if not name.isdigit():
            continue
        pid = int(name)
        if pid == my_pid:
            continue
        cmd = _cmdline(pid)
        if not cmd:
            continue
        if WORKER_MARK not in cmd:
            continue
        if token not in cmd:
            continue
        if "probe1_" in cmd or "probe2_" in cmd or "write_receipts" in cmd:
            continue
        if server is not None and f"--server={server}" not in cmd:
            continue
        found.append({"pid": pid, "cmdline": cmd.strip(), "server": server})
    found.sort(key=lambda row: row["pid"])
    return found


def count_server(token: str, server: str) -> int:
    return len(census(token, server=server))


def kill_token(token: str, timeout: float = 2.0) -> None:
    deadline = time.time() + timeout
    while True:
        live = census(token)
        if not live:
            return
        sig = signal.SIGTERM if time.time() < deadline else signal.SIGKILL
        for row in live:
            try:
                os.kill(int(row["pid"]), sig)
            except OSError:
                pass
        if sig == signal.SIGKILL:
            time.sleep(0.05)
            return
        time.sleep(0.05)


def spawn_worker(
    token: str,
    server: str,
    session: str,
    mode: str,
) -> subprocess.Popen:
    argv = [
        sys.executable,
        "-B",
        str(WORKER),
        WORKER_MARK,
        f"--token={token}",
        f"--server={server}",
        f"--session={session}",
        f"--mode={mode}",
    ]
    return subprocess.Popen(
        argv,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def spawn_sessions(
    config: dict,
    n_sessions: int,
    mode: str,
    token: str,
    servers: tuple[str, ...] = SERVERS,
) -> list[subprocess.Popen]:
    active = enabled_servers(config, servers)
    procs: list[subprocess.Popen] = []
    if mode == "eager":
        for i in range(n_sessions):
            sid = f"sess-{i+1}"
            for name in active:
                procs.append(spawn_worker(token, name, sid, mode))
    elif mode == "shared":
        for name in active:
            procs.append(spawn_worker(token, name, "shared", mode))
    else:
        raise ValueError(mode)
    _wait_visible(token, len(procs))
    return procs


def _wait_visible(token: str, expected: int, timeout: float = 2.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if len(census(token)) >= expected:
            return
        time.sleep(0.02)
    live = len(census(token))
    if live < expected:
        raise RuntimeError(
            f"process-table census under-count: token={token} expected={expected} live={live}"
        )


def designed_not_multiplicative(eager_n: int, shared_n: int, sessions: int, servers: int) -> dict:
    product = sessions * servers
    return {
        "sessions": sessions,
        "servers": servers,
        "eager_count": eager_n,
        "shared_count": shared_n,
        "multiplicative_product": product,
        "eager_is_multiplicative": eager_n == product,
        "shared_is_server_count": shared_n == servers,
        "shared_is_not_multiplicative": shared_n != product and shared_n < product,
        "designed_ok": eager_n == product and shared_n == servers and shared_n != product,
        "broken_policy_fails_designed_check": eager_n != servers,
    }
