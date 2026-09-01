#!/usr/bin/env python3
"""Inspect MCP singleton/resource health and maintain session quarantine state."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import time
from dataclasses import dataclass
from typing import Any

import mcp_control_plane as control


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "agents.json"
DEFAULT_STATE = ROOT / "state" / "mcp-supervisor.json"
DEFAULT_REPORT = ROOT / "reports" / "mcp-fleet-status.json"
GENERIC_COMMANDS = {
    "cmd",
    "node",
    "npx",
    "npm",
    "powershell",
    "pwsh",
    "python",
    "pythonw",
    "uv",
    "uvx",
}
SECRET_ARGUMENT_RE = re.compile(
    r"(?i)(?:--?(?:api[-_]?key|access[-_]?key|password|secret|token)\s*[=:]\s*\S+|"
    r"(?:github_pat_|gh[pousr]_|hf_|apify_api_|sntry[su]_)[A-Za-z0-9_-]{12,})"
)


@dataclass(frozen=True)
class ProcessRecord:
    pid: int
    parent_pid: int
    executable_path: str
    command_line: str
    private_bytes: int


def _normalize_token(value: str) -> str:
    return value.replace("\\", "/").strip("\"'").lower()


def identity_tokens(name: str, server: dict[str, Any]) -> list[str]:
    explicit = server.get("processMatch")
    if isinstance(explicit, list) and explicit:
        return [
            _normalize_token(str(token)) for token in explicit if str(token).strip()
        ]

    tokens: list[str] = []
    for argument in server.get("args", []):
        value = _normalize_token(str(argument))
        if not value or value.startswith("-") or value in {"stdio", "serve", "mcp"}:
            continue
        if value.startswith(("http://", "https://")):
            continue
        candidate = value
        if candidate.startswith("@") and "/" in candidate:
            version_at = candidate.rfind("@")
            if version_at > candidate.find("/"):
                candidate = candidate[:version_at]
        elif "@" in candidate and "/" not in candidate:
            candidate = candidate.split("@", 1)[0]
        if (
            "/" in candidate or "mcp" in candidate or candidate == name.lower()
        ) and len(candidate) >= 5:
            tokens.append(candidate)

    if not tokens:
        command = pathlib.PurePath(str(server.get("command", ""))).stem.lower()
        if command and command not in GENERIC_COMMANDS:
            tokens.append(command)
    if not tokens and len(name) >= 5:
        tokens.append(name.lower())
    return sorted(set(tokens), key=lambda item: (-len(item), item))


def assign_processes(
    servers: dict[str, dict[str, Any]], processes: list[ProcessRecord]
) -> tuple[dict[str, set[int]], set[int], int]:
    """Assign each process to its strongest unambiguous registry identity."""
    server_tokens = {
        name: identity_tokens(name, server)
        for name, server in servers.items()
        if server.get("transport") == "stdio" or server.get("processMatch")
    }
    assigned: dict[str, set[int]] = {name: set() for name in server_tokens}
    ambiguous: set[int] = set()
    secret_argument_processes = 0
    for process in processes:
        haystack = _normalize_token(f"{process.executable_path} {process.command_line}")
        if SECRET_ARGUMENT_RE.search(process.command_line):
            secret_argument_processes += 1
        candidates: list[tuple[int, str]] = []
        for name, tokens in server_tokens.items():
            matched = [token for token in tokens if token in haystack]
            if matched:
                candidates.append((max(map(len, matched)), name))
        if not candidates:
            continue
        candidates.sort(reverse=True)
        best_score = candidates[0][0]
        best = [name for score, name in candidates if score == best_score]
        if len(best) != 1:
            ambiguous.add(process.pid)
            continue
        assigned[best[0]].add(process.pid)
    return assigned, ambiguous, secret_argument_processes


def process_roots(pids: set[int], processes: list[ProcessRecord]) -> set[int]:
    parent = {process.pid: process.parent_pid for process in processes}
    roots: set[int] = set()
    for pid in pids:
        current = parent.get(pid, 0)
        seen: set[int] = set()
        has_assigned_ancestor = False
        while current and current not in seen:
            if current in pids:
                has_assigned_ancestor = True
                break
            seen.add(current)
            current = parent.get(current, 0)
        if not has_assigned_ancestor:
            roots.add(pid)
    return roots


def _root_for_pid(pid: int, roots: set[int], parent: dict[int, int]) -> int | None:
    current = pid
    seen: set[int] = set()
    while current and current not in seen:
        if current in roots:
            return current
        seen.add(current)
        current = parent.get(current, 0)
    return None


def _client_owner(root: int, process_by_id: dict[int, ProcessRecord]) -> str:
    current = root
    seen: set[int] = set()
    while current and current not in seen:
        seen.add(current)
        process = process_by_id.get(current)
        if process is None:
            break
        executable = pathlib.PurePath(process.executable_path).stem.lower()
        if executable in {"claude", "codex", "chatgpt"}:
            return f"{executable}:{current}"
        current = process.parent_pid
    return f"service:{root}"


def evaluate_fleet(
    config: dict[str, Any], processes: list[ProcessRecord], quarantine: set[str]
) -> dict[str, Any]:
    control.validate_registry(config)
    servers = config["mcp"]["servers"]
    assigned, ambiguous, secret_argument_processes = assign_processes(
        servers, processes
    )
    process_by_id = {process.pid: process for process in processes}
    parent = {process.pid: process.parent_pid for process in processes}
    unique_assigned = set().union(*assigned.values()) if assigned else set()
    total_private = sum(
        process_by_id[pid].private_bytes
        for pid in unique_assigned
        if pid in process_by_id
    )
    session_limit = config["mcp"]["supervision"]["totalIdlePrivateBytes"]
    session_private: dict[str, int] = {}

    server_status: dict[str, Any] = {}
    duplicate_servers: list[str] = []
    over_budget_servers: list[str] = []
    for name, server in servers.items():
        pids = assigned.get(name, set())
        roots = process_roots(pids, processes)
        private_bytes = sum(
            process_by_id[pid].private_bytes for pid in pids if pid in process_by_id
        )
        root_private: dict[int, int] = {root: 0 for root in roots}
        for pid in pids:
            root = _root_for_pid(pid, roots, parent)
            if root is not None and pid in process_by_id:
                root_private[root] += process_by_id[pid].private_bytes
        root_owners = {root: _client_owner(root, process_by_id) for root in roots}
        owner_root_counts: dict[str, int] = {}
        for root, owner in root_owners.items():
            owner_root_counts[owner] = owner_root_counts.get(owner, 0) + 1
            session_private[owner] = session_private.get(owner, 0) + root_private[root]
        contract = control.effective_server_contract(config, name)
        max_instance_private = max(root_private.values(), default=0)
        over_budget = max_instance_private > contract["maxPrivateBytes"]
        duplicate = any(count > 1 for count in owner_root_counts.values())
        if duplicate:
            duplicate_servers.append(name)
        if over_budget:
            over_budget_servers.append(name)
        state = (
            "quarantined"
            if name in quarantine
            else ("degraded" if duplicate or over_budget else "healthy")
        )
        server_status[name] = {
            "state": state,
            "processCount": len(pids),
            "rootCount": len(roots),
            "privateBytes": private_bytes,
            "maxInstancePrivateBytes": max_instance_private,
            "privateByteLimit": contract["maxPrivateBytes"],
            "duplicate": duplicate,
            "overBudget": over_budget,
            "terminationEligible": False,
        }

    sessions_over_budget = sorted(
        owner for owner, private in session_private.items() if private > session_limit
    )
    # `totalIdlePrivateBytes` is a FLEET ceiling, so the fleet sum is compared to it
    # as well as each session. Checking only per-session let the estate run 13.6 GiB
    # across 7 sessions against a 6 GiB budget and still report `healthy` (captured
    # in reconcile-flags/import-2026-08-28/live-only-flagged/reports/mcp-fleet-status.json):
    # per-session stdio duplication never breaches any single session's budget, which
    # is precisely how it exhausts commit unnoticed.
    total_over_budget = total_private > session_limit
    degraded = bool(
        duplicate_servers
        or over_budget_servers
        or sessions_over_budget
        or total_over_budget
        or ambiguous
        or secret_argument_processes
        or quarantine
    )
    return {
        "schemaVersion": 1,
        "status": "degraded" if degraded else "healthy",
        "totalPrivateBytes": total_private,
        "sessionPrivateByteLimit": session_limit,
        "maxSessionPrivateBytes": max(session_private.values(), default=0),
        "sessionCount": len(session_private),
        "sessionsOverBudget": len(sessions_over_budget),
        "totalOverBudget": total_over_budget,
        "ambiguousProcessCount": len(ambiguous),
        "secretArgumentProcessCount": secret_argument_processes,
        "duplicateServers": sorted(duplicate_servers),
        "overBudgetServers": sorted(over_budget_servers),
        "quarantinedServers": sorted(quarantine),
        "servers": server_status,
    }


def update_quarantine_state(
    state: dict[str, Any],
    *,
    session_id: str,
    failures: list[str],
    now: float,
    threshold: int,
    window_seconds: int,
) -> tuple[dict[str, Any], set[str]]:
    if state.get("sessionId") != session_id:
        state = {
            "schemaVersion": 1,
            "sessionId": session_id,
            "failures": {},
            "quarantined": [],
        }
    failure_map = state.setdefault("failures", {})
    cutoff = now - window_seconds
    for server, timestamps in list(failure_map.items()):
        failure_map[server] = [
            float(value) for value in timestamps if float(value) >= cutoff
        ]
    for server in failures:
        failure_map.setdefault(server, []).append(now)
    quarantined = {
        server
        for server, timestamps in failure_map.items()
        if len(timestamps) >= threshold
    }
    state["quarantined"] = sorted(quarantined)
    state["updatedAt"] = now
    return state, quarantined


def live_process_snapshot() -> list[ProcessRecord]:
    script = r"""
$memory = @{}
Get-Process -ErrorAction SilentlyContinue | ForEach-Object { $memory[[int]$_.Id] = [int64]$_.PrivateMemorySize64 }
Get-CimInstance Win32_Process | ForEach-Object {
  [pscustomobject]@{
    pid = [int]$_.ProcessId
    parent_pid = [int]$_.ParentProcessId
    executable_path = [string]$_.ExecutablePath
    command_line = [string]$_.CommandLine
    private_bytes = [int64]($memory[[int]$_.ProcessId] ?? 0)
  }
} | ConvertTo-Json -Depth 3 -Compress
"""
    completed = subprocess.run(
        ["pwsh", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    payload = json.loads(completed.stdout or "[]")
    if isinstance(payload, dict):
        payload = [payload]
    return [ProcessRecord(**item) for item in payload]


def atomic_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    control.atomic_write_text(
        path,
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=pathlib.Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--state", type=pathlib.Path, default=DEFAULT_STATE)
    parser.add_argument("--report", type=pathlib.Path, default=DEFAULT_REPORT)
    parser.add_argument("--snapshot", type=pathlib.Path)
    parser.add_argument(
        "--session-id", default=os.environ.get("CODEX_THREAD_ID", "local-session")
    )
    parser.add_argument("--record-failure", action="append", default=[])
    args = parser.parse_args()

    config = json.loads(args.registry.read_text(encoding="utf-8"))
    control.validate_registry(config)
    state = (
        json.loads(args.state.read_text(encoding="utf-8"))
        if args.state.exists()
        else {}
    )
    supervision = config["mcp"]["supervision"]
    state, quarantine = update_quarantine_state(
        state,
        session_id=args.session_id,
        failures=args.record_failure,
        now=time.time(),
        threshold=supervision["failureThreshold"],
        window_seconds=supervision["failureWindowSeconds"],
    )
    if args.snapshot:
        raw = json.loads(args.snapshot.read_text(encoding="utf-8"))
        processes = [ProcessRecord(**item) for item in raw]
    else:
        processes = live_process_snapshot()
    report = evaluate_fleet(config, processes, quarantine)
    report["sessionIdHash"] = (
        __import__("hashlib").sha256(args.session_id.encode("utf-8")).hexdigest()[:16]
    )
    report["generatedAt"] = time.time()
    atomic_json(args.state, state)
    atomic_json(args.report, report)
    print(
        "SUCCESS:mcp-fleet-status "
        f"status={report['status']} total_private_bytes={report['totalPrivateBytes']} "
        f"fleet_over_budget={str(report['totalOverBudget']).lower()} "
        f"sessions_over_budget={report['sessionsOverBudget']} "
        f"duplicates={len(report['duplicateServers'])} "
        f"over_budget={len(report['overBudgetServers'])} "
        f"quarantined={len(report['quarantinedServers'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
