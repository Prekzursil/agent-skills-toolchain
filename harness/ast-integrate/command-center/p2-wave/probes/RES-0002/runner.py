"""Run a PostToolUse hook script against one JSON event."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def classify_verdict(stdout: str, returncode: int) -> str:
    token = ""
    for line in (stdout or "").splitlines():
        piece = line.strip()
        if piece:
            token = piece.split()[0]
            break
    if token == "FAILED" or (returncode not in (0, None) and returncode != 0):
        return "FAILED"
    if token == "OK" and returncode == 0:
        return "OK"
    if returncode == 0:
        return "OK"
    return "FAILED"


def run_hook(script: Path, event: dict[str, Any], timeout: float = 10.0) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    payload = json.dumps(event, sort_keys=True)
    try:
        proc = subprocess.run(
            [sys.executable, "-B", str(script)],
            input=payload,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        code = int(proc.returncode)
        return {
            "script": str(script),
            "tool_name": event.get("tool_name"),
            "http_status": ((event.get("tool_response") or {}) or {}).get("status_code"),
            "returncode": code,
            "stdout_token": (stdout.strip().split() or [""])[0],
            "stdout": stdout[-500:],
            "stderr": stderr[-300:],
            "verdict": classify_verdict(stdout, code),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired:
        return {
            "script": str(script),
            "tool_name": event.get("tool_name"),
            "http_status": ((event.get("tool_response") or {}) or {}).get("status_code"),
            "returncode": 124,
            "stdout_token": "",
            "stdout": "",
            "stderr": "TIMEOUT",
            "verdict": "FAILED",
            "timed_out": True,
        }


def run_session(script: Path | None, events: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    if script is None:
        for event in events:
            rows.append(
                {
                    "script": None,
                    "tool_name": event.get("tool_name"),
                    "http_status": ((event.get("tool_response") or {}) or {}).get(
                        "status_code"
                    ),
                    "returncode": None,
                    "stdout_token": "",
                    "stdout": "",
                    "stderr": "",
                    "verdict": "NOT-FIRED",
                    "timed_out": False,
                }
            )
        return {"hook": None, "ran": False, "results": rows}
    for event in events:
        rows.append(run_hook(script, event))
    return {"hook": str(script), "ran": True, "results": rows}


def verdicts_by_tool(results: list[dict[str, Any]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in results:
        name = str(row.get("tool_name") or "")
        status = row.get("http_status")
        if name == "WebFetch" and status == 200:
            out["WebFetch"] = str(row.get("verdict"))
        elif name == "WebFetch" and status == 404:
            out["WebFetch_404"] = str(row.get("verdict"))
        elif name:
            out[name] = str(row.get("verdict"))
    return out
