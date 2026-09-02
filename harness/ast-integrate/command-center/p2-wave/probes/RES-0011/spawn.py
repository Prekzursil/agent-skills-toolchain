#!/usr/bin/env python3
"""Spawn a fixture subagent and attempt one tool call, writing a transcript.

The 'subagent' is a local process bound to a markdown definition. The gate
is the documented tool-resolution contract in contract.py. Allowed Bash is
restricted to a single safe echo so the allow-path is a real subprocess
without becoming a general shell.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from contract import (
    FORBIDDEN_ARGV,
    FORBIDDEN_TOOL,
    SAFE_BASH_RE,
    agent_gate,
    attempt_agent_tool,
    attempt_command_tool,
    command_gate,
)

HERE = Path(__file__).resolve().parent
TRANSCRIPTS = HERE / "transcripts"


def _run_safe_bash(argv: str) -> dict[str, Any]:
    if not SAFE_BASH_RE.match(argv.strip()):
        return {
            "status": "REFUSED",
            "reason": "unsafe-bash-shape",
            "stdout": "",
            "returncode": None,
        }
    p = subprocess.run(
        ["bash", "-c", argv],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return {
        "status": "ALLOWED",
        "reason": "safe-bash-executed",
        "stdout": (p.stdout or "").strip(),
        "stderr": (p.stderr or "").strip(),
        "returncode": p.returncode,
    }


def spawn_agent_forbidden_call(definition: Path) -> dict:
    gate = agent_gate(definition)
    decision = attempt_agent_tool(gate, FORBIDDEN_TOOL)
    executed = None
    if decision["status"] == "ALLOWED":
        executed = _run_safe_bash(FORBIDDEN_ARGV)
        if executed["returncode"] != 0:
            decision = {
                **decision,
                "status": "FAILED",
                "reason": "allowed-but-subprocess-nonzero",
            }
    event = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "definition": definition.name,
        "kind": "agent",
        "name": (gate.get("frontmatter") or {}).get("name"),
        "model": gate.get("model"),
        "tool": FORBIDDEN_TOOL,
        "argv": FORBIDDEN_ARGV,
        "body_mentions_bash": "Bash" in (gate.get("body") or ""),
        "resolved_tools": (gate.get("tool_resolution") or {}).get("tools"),
        "decision": decision["status"],
        "reason": decision.get("reason"),
        "execution": executed,
    }
    return event


def spawn_command_forbidden_call(definition: Path) -> dict:
    gate = command_gate(definition)
    decision = attempt_command_tool(gate, FORBIDDEN_TOOL)
    executed = None
    if decision["status"] == "ALLOWED":
        executed = _run_safe_bash(FORBIDDEN_ARGV)
    event = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "definition": definition.name,
        "kind": "command",
        "resolved_available": (gate.get("tool_resolution") or {}).get(
            "available"
        ),
        "preapproved": (gate.get("tool_resolution") or {}).get("preapproved"),
        "tool": FORBIDDEN_TOOL,
        "argv": FORBIDDEN_ARGV,
        "decision": decision["status"],
        "reason": decision.get("reason"),
        "in_preapproved": decision.get("in_preapproved"),
        "execution": executed,
    }
    return event


def write_transcript(name: str, event: dict) -> Path:
    TRANSCRIPTS.mkdir(parents=True, exist_ok=True)
    path = TRANSCRIPTS / name
    path.write_text(json.dumps(event, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
