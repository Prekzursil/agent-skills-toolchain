#!/usr/bin/env python3
"""Host-client inventory and adjacent-install retry for BLD-0012."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PINS = HERE / "changelog_pins.json"


def load_pins() -> dict:
    return json.loads(PINS.read_text(encoding="utf-8"))


def which_clients() -> dict:
    cursor = shutil.which("cursor-agent") or shutil.which("cursor")
    return {
        "claude": shutil.which("claude"),
        "npm": shutil.which("npm"),
        "npx": shutil.which("npx"),
        "node": shutil.which("node"),
        "cursor_agent": cursor,
        "node_version": _run(["node", "--version"]) if shutil.which("node") else None,
        "cursor_agent_version": _run(
            [
                "/root/.local/share/cursor-agent/versions/2026.08.11-e8db854/cursor-agent",
                "--version",
            ]
        ),
    }


def _run(cmd: list[str], timeout: int = 20) -> str | None:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return text.splitlines()[0] if text else None


def adjacent_install_attempt() -> dict:
    """Retry policy: try once to install/run adjacent Claude Code. Do not pretend.

    Strike 1: look for a live `claude` binary.
    Strike 2 (different measurement): probe the npm registry without installing.
    """
    pins = load_pins()
    one_back = pins["one_back_version"]
    one_forward = pins["one_forward_version"]
    clients = which_clients()
    strike1 = {
        "id": "live-binary",
        "claude_path": clients["claude"],
        "present": bool(clients["claude"]),
    }
    registry = None
    curl = shutil.which("curl")
    if curl:
        try:
            p = subprocess.run(
                [
                    curl,
                    "-sS",
                    "-o",
                    "/dev/null",
                    "-w",
                    "%{http_code}",
                    "--max-time",
                    "15",
                    "https://registry.npmjs.org/@anthropic-ai/claude-code",
                ],
                capture_output=True,
                text=True,
                timeout=20,
            )
            registry = {"http_code": (p.stdout or "").strip(), "exit": p.returncode}
        except (OSError, subprocess.TimeoutExpired) as exc:
            registry = {"error": type(exc).__name__}
    else:
        registry = {"error": "curl-absent"}
    strike2 = {
        "id": "npm-registry-probe",
        "npm_path": clients["npm"],
        "npm_present": bool(clients["npm"]),
        "registry": registry,
    }
    blockers = []
    if not clients["claude"]:
        blockers.append("claude-binary-absent")
    if not clients["npm"]:
        blockers.append("npm-not-installed")
    if not pins.get("one_forward_published"):
        blockers.append(f"{one_forward}-not-published-on-changelog-head")
    return {
        "status": "NOT-CHECKED",
        "one_back": one_back,
        "one_forward": one_forward,
        "strike1": strike1,
        "strike2": strike2,
        "blocker": ";".join(blockers),
        "note": (
            "Adjacent Claude Code was not installed. Retry used a different "
            "measurement (npm registry HEAD) rather than re-running the missing binary."
        ),
        "cwd": os.getcwd(),
        "clients": {
            k: clients[k]
            for k in ("claude", "npm", "npx", "node", "node_version", "cursor_agent_version")
        },
    }
