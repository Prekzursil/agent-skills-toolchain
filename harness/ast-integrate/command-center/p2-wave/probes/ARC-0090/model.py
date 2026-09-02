#!/usr/bin/env python3
"""ARC-0090 executable MCP adapter contract.

Choke point the named probes call. Production MCP clients are not claimed
to be wired through it. Scope pass/fail uses the configuration files that
hold the setting AND the OS process table, never the adapter's child dict
alone.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
STUB = HERE / "stub_server.py"

SCOPES = ("local", "project", "user")
# First listed scope that names a server wins. `user` is the analog of a
# root ~/.claude.json disabledMcpServers dump: inert when project/local
# already has an entry. `project` is the analog of per-project .mcp.json.
SCOPE_FILE = {
    "local": "mcp.local.json",
    "project": ".mcp.json",
    "user": "user-mcp.json",
}
TRANSPORTS = ("stdio", "http")
LIFECYCLE_OWNER = "adapter"
STDIO_PROCESS_CAP = 8
NAMESPACE_SEP = "__"
DEFAULT_ENABLED = True
MARK_FLAG = "--arc0090-mark"


class ContractError(ValueError):
    """Declaration, cap, namespace, or lifecycle violation."""


class Policy:
    def __init__(
        self,
        *,
        any_scope_disable: bool = False,
        preserve_enable_on_migrate: bool = True,
        stdio_cap: int | None = STDIO_PROCESS_CAP,
        reap_on_unmount: bool = True,
        require_declaration: bool = True,
    ) -> None:
        self.any_scope_disable = any_scope_disable
        self.preserve_enable_on_migrate = preserve_enable_on_migrate
        self.stdio_cap = stdio_cap
        self.reap_on_unmount = reap_on_unmount
        self.require_declaration = require_declaration


def empty_enable() -> dict[str, dict[str, bool]]:
    return {scope: {} for scope in SCOPES}


def canonical_enable_text(enable: dict[str, dict[str, bool]]) -> str:
    payload = {
        scope: {k: bool(v) for k, v in sorted((enable.get(scope) or {}).items())}
        for scope in SCOPES
    }
    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


def canonical_enable_bytes(enable: dict[str, dict[str, bool]]) -> bytes:
    return canonical_enable_text(enable).encode("utf-8")


def validate_declaration(transport: str, declaration: dict[str, Any] | None) -> None:
    if transport not in TRANSPORTS:
        raise ContractError(f"transport must be stdio or http, not {transport!r}")
    if not isinstance(declaration, dict) or not declaration:
        raise ContractError("server declaration required")
    if transport == "stdio":
        command = declaration.get("command")
        if not isinstance(command, list) or not command:
            raise ContractError("stdio declaration must name command")
        if not all(isinstance(x, str) and x for x in command):
            raise ContractError("stdio command tokens must be non-empty strings")
        if declaration.get("url"):
            raise ContractError("stdio declaration must not include url")
        return
    url = declaration.get("url")
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        raise ContractError("http declaration must name an http(s) url")
    if declaration.get("command"):
        raise ContractError("http declaration must not include command")


def namespaced(server_id: str, tool_name: str) -> str:
    if not server_id or not tool_name:
        raise ContractError("server_id and tool_name required")
    if NAMESPACE_SEP in tool_name:
        raise ContractError("bare tool name must not contain the namespace marker")
    if NAMESPACE_SEP in server_id:
        raise ContractError("server_id must not contain the namespace marker")
    return f"{server_id}{NAMESPACE_SEP}{tool_name}"


def split_namespaced(full: str) -> tuple[str, str]:
    if NAMESPACE_SEP not in full:
        raise ContractError(f"un-namespaced tool {full!r}")
    server_id, tool_name = full.split(NAMESPACE_SEP, 1)
    if not server_id or not tool_name or NAMESPACE_SEP in tool_name:
        raise ContractError(f"malformed namespaced tool {full!r}")
    return server_id, tool_name


def resolve_enabled(
    enable: dict[str, dict[str, bool]],
    server_id: str,
    *,
    any_scope_disable: bool = False,
) -> dict[str, Any]:
    """Whether the server is enabled and which scope decided it."""
    if any_scope_disable:
        for scope in SCOPES:
            if enable.get(scope, {}).get(server_id) is False:
                return {
                    "enabled": False,
                    "effective_scope": scope,
                    "reason": "any-scope-disable-mutant",
                    "inert_user_disable": False,
                }
    for scope in SCOPES:
        if server_id in (enable.get(scope) or {}):
            enabled = bool(enable[scope][server_id])
            user_disable = enable.get("user", {}).get(server_id) is False
            return {
                "enabled": enabled,
                "effective_scope": scope,
                "reason": "first-listed-scope-with-entry",
                "inert_user_disable": bool(user_disable and scope != "user" and enabled),
            }
    return {
        "enabled": DEFAULT_ENABLED,
        "effective_scope": None,
        "reason": "default-enabled",
        "inert_user_disable": False,
    }


def iter_marked_pids(mark: str) -> list[int]:
    """PIDs whose /proc cmdline contains the stub script and the mark token."""
    found: list[int] = []
    proc = Path("/proc")
    if not proc.is_dir():
        return found
    needle = mark.encode("utf-8")
    stub = b"stub_server.py"
    self_pid = os.getpid()
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if pid == self_pid:
            continue
        try:
            raw = (entry / "cmdline").read_bytes()
        except (OSError, PermissionError):
            continue
        if stub in raw and needle in raw:
            found.append(pid)
    return sorted(found)


def process_table_count(mark: str) -> int:
    return len(iter_marked_pids(mark))


def _reap(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        proc.send_signal(signal.SIGTERM)
    except OSError:
        pass
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
            proc.wait(timeout=1)
        except (OSError, subprocess.TimeoutExpired):
            pass


class Adapter:
    """Owns MCP stub children for one session and one unique mark."""

    def __init__(
        self,
        *,
        config_dir: Path,
        mark: str,
        policy: Policy | None = None,
        session_id: str = "session-0",
    ) -> None:
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.mark = mark
        self.policy = policy or Policy()
        self.session_id = session_id
        self.enable = empty_enable()
        self._children: dict[str, subprocess.Popen] = {}
        self._load_files()

    def _path(self, scope: str) -> Path:
        return self.config_dir / SCOPE_FILE[scope]

    def _load_files(self) -> None:
        for scope in SCOPES:
            path = self._path(scope)
            if not path.is_file():
                continue
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            enabled = doc.get("enabled") if isinstance(doc, dict) else None
            if isinstance(enabled, dict):
                self.enable[scope] = {str(k): bool(v) for k, v in enabled.items()}

    def persist(self) -> dict[str, str]:
        written: dict[str, str] = {}
        for scope in SCOPES:
            doc = {
                "scope": scope,
                "effective_when_first_listed": True,
                "enabled": {
                    k: bool(v) for k, v in sorted(self.enable[scope].items())
                },
            }
            path = self._path(scope)
            path.write_text(
                json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=True) + "\n",
                encoding="utf-8",
            )
            written[scope] = str(path)
        return written

    def set_enabled(self, server_id: str, enabled: bool, *, scope: str) -> None:
        if scope not in SCOPES:
            raise ContractError(f"unknown scope {scope!r}")
        self.enable[scope][server_id] = bool(enabled)
        self.persist()

    def snapshot_enable(self) -> dict[str, dict[str, bool]]:
        return deepcopy(self.enable)

    def migrate(self, snapshot: dict[str, dict[str, bool]]) -> None:
        if self.policy.preserve_enable_on_migrate:
            self.enable = deepcopy(snapshot)
        else:
            self.enable = empty_enable()
        self.persist()

    def enabled_resolution(self, server_id: str) -> dict[str, Any]:
        return resolve_enabled(
            self.enable,
            server_id,
            any_scope_disable=self.policy.any_scope_disable,
        )

    def _stdio_live_count(self) -> int:
        return sum(1 for p in self._children.values() if p.poll() is None)

    def mount(
        self,
        server_id: str,
        *,
        transport: str,
        declaration: dict[str, Any] | None,
        tools: list[str] | None = None,
    ) -> dict[str, Any]:
        if self.policy.require_declaration:
            validate_declaration(transport, declaration)
        resolution = self.enabled_resolution(server_id)
        files = self.persist()
        if not resolution["enabled"]:
            return {
                "mounted": False,
                "reason": "disabled-at-effective-scope",
                "resolution": resolution,
                "config_files": files,
                "process_table_count": process_table_count(self.mark),
                "lifecycle_owner": LIFECYCLE_OWNER,
                "transport": transport,
            }
        if transport == "stdio" and self.policy.stdio_cap is not None:
            if self._stdio_live_count() >= self.policy.stdio_cap:
                raise ContractError(
                    f"stdio process cap {self.policy.stdio_cap} per session"
                )
        exposed = [namespaced(server_id, t) for t in (tools or [])]
        proc = subprocess.Popen(
            [
                sys.executable,
                "-u",
                str(STUB),
                MARK_FLAG,
                self.mark,
                "--server-id",
                server_id,
                "--mode",
                "http" if transport == "http" else "stdio",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        if proc.poll() is not None:
            raise ContractError(f"stub exited rc={proc.returncode} before listed")
        self._children[server_id] = proc
        deadline = time.time() + 3.0
        while time.time() < deadline:
            if proc.pid in iter_marked_pids(self.mark):
                break
            if proc.poll() is not None:
                raise ContractError("stub died before process-table listing")
            time.sleep(0.02)
        else:
            raise ContractError("stub never appeared in the process table")
        return {
            "mounted": True,
            "server_id": server_id,
            "pid": proc.pid,
            "transport": transport,
            "lifecycle_owner": LIFECYCLE_OWNER,
            "resolution": resolution,
            "config_files": files,
            "exposed_tools": exposed,
            "process_table_count": process_table_count(self.mark),
            "process_table_pids": iter_marked_pids(self.mark),
        }

    def unmount(self, server_id: str) -> None:
        proc = self._children.pop(server_id, None)
        if proc is None:
            return
        if self.policy.reap_on_unmount:
            _reap(proc)

    def close(self) -> None:
        for sid in list(self._children):
            self.unmount(sid)

    def __enter__(self) -> Adapter:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
