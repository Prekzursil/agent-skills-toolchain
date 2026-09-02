"""Trigger each declared hook event and require a child-written RECEIPT line.

The client loop: strict-load hooks.json, then subprocess-exec each loaded
command. A listing of hook files is not a trigger. If strict-load returns
nothing, events are still requested so the unloaded state is observable.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import loader as L
import scenario as S

REPO = S.REPO


def parse_receipt(path: Path) -> list[dict[str, str]]:
    if not path.is_file() or path.stat().st_size <= 0:
        return []
    rows: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("RECEIPT "):
            continue
        fields = {"raw": line}
        for part in line.split():
            if "=" in part:
                key, value = part.split("=", 1)
                fields[key] = value
        rows.append(fields)
    return rows


def _run_command(argv: list[str], receipt: Path) -> dict[str, Any]:
    env = os.environ.copy()
    env["TST0082_RECEIPT"] = str(receipt)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        proc = subprocess.run(
            argv,
            cwd=str(REPO),
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "argv": argv,
            "exit_code": 124 if isinstance(exc, subprocess.TimeoutExpired) else 1,
            "error": type(exc).__name__,
            "stdout": "",
            "stderr": str(exc)[:500],
        }
    return {
        "argv": argv,
        "exit_code": proc.returncode,
        "stdout": (proc.stdout or "")[-500:],
        "stderr": (proc.stderr or "")[-500:],
    }


def trigger(hooks_path: Path, receipt_path: Path) -> dict[str, Any]:
    """Request every declared event. Execute only what strict-load returned."""
    S.ensure_fixtures()
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    parent_pid = os.getpid()
    loaded = L.load(hooks_path)
    naive = L.naive_file_count()
    appearance = L.appearance(hooks_path)
    receipt_path.write_text(
        f"# session parent_pid={parent_pid} hooks={loaded['path']} "
        f"loaded={len(loaded['loaded'])}\n",
        encoding="utf-8",
        newline="\n",
    )
    runs: list[dict[str, Any]] = []
    for hook_id, event in S.EVENTS:
        matching = [h for h in loaded["loaded"] if h["event"] == event]
        if not matching:
            runs.append(
                {
                    "hook_id": hook_id,
                    "event": event,
                    "requested": True,
                    "executed": False,
                    "reason": "not-loaded",
                }
            )
            continue
        for hook in matching:
            result = _run_command(list(hook["argv"]), receipt_path)
            result.update(
                {
                    "hook_id": hook_id,
                    "event": event,
                    "requested": True,
                    "executed": True,
                    "command": hook["command"],
                }
            )
            runs.append(result)
    lines = parse_receipt(receipt_path)
    fired_events = sorted({row.get("event", "") for row in lines if row.get("event")})
    declared_events = [event for _hook_id, event in S.EVENTS]
    child_pids = []
    for row in lines:
        try:
            child_pids.append(int(row.get("pid") or "0"))
        except ValueError:
            child_pids.append(0)
    child_ok = bool(child_pids) and all(pid != parent_pid and pid > 0 for pid in child_pids)
    return {
        "appearance": appearance,
        "child_pids": child_pids,
        "child_written": child_ok,
        "declared_events": declared_events,
        "fired_count": len(lines),
        "fired_events": fired_events,
        "hooks_path": loaded["path"],
        "loaded_count": len(loaded["loaded"]),
        "naive_file_count": naive,
        "parent_pid": parent_pid,
        "python": sys.executable,
        "receipt_exists": receipt_path.is_file(),
        "receipt_lines": [row.get("raw", "") for row in lines],
        "registered_count": len(loaded["registered"]),
        "rejected_keys": loaded["rejected_keys"],
        "reason": loaded["reason"],
        "runs": runs,
        "strict_load": loaded,
    }


def healthy_session(receipt_path: Path | None = None) -> dict[str, Any]:
    S.ensure_fixtures()
    dest = receipt_path or (S.HERE / "captures" / "healthy-receipt.txt")
    return trigger(S.healthy_path(), dest)


def malformed_session(receipt_path: Path | None = None) -> dict[str, Any]:
    S.ensure_fixtures()
    dest = receipt_path or (S.HERE / "captures" / "malformed-receipt.txt")
    return trigger(S.malformed_path(), dest)
