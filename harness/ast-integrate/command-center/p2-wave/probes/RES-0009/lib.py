"""Parse frozen hook docs and run the command-hook protocol locally."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SNAP = HERE / "snapshots"
HOOKS = HERE / "hooks"
CLI_DOC = SNAP / "cli-hooks.md"
SDK_DOC = SNAP / "sdk-hooks.md"
CLI_SRC = Path(
    "/root/.cursor/projects/opt-p2-ast-integrate/agent-tools/"
    "dcea34a3-47c1-40cd-a43d-79fcb6ac1ef4.txt"
)
SDK_SRC = Path(
    "/root/.cursor/projects/opt-p2-ast-integrate/agent-tools/"
    "dc1d9c28-1f5d-445e-ad97-5957387dd728.txt"
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_path(path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    return sha256_bytes(raw), len(raw.replace(b"\r\n", b"\n"))


def ensure_snapshots() -> None:
    SNAP.mkdir(parents=True, exist_ok=True)
    if not CLI_DOC.is_file():
        if not CLI_SRC.is_file():
            raise SystemExit("FAILED:RES-0009 cli-hooks snapshot missing")
        CLI_DOC.write_bytes(CLI_SRC.read_bytes())
    if not SDK_DOC.is_file():
        if not SDK_SRC.is_file():
            raise SystemExit("FAILED:RES-0009 sdk-hooks snapshot missing")
        SDK_DOC.write_bytes(SDK_SRC.read_bytes())


def load_docs() -> tuple[str, str]:
    ensure_snapshots()
    return (
        CLI_DOC.read_text(encoding="utf-8", errors="replace"),
        SDK_DOC.read_text(encoding="utf-8", errors="replace"),
    )


def _uniq(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def table_first_idents(text: str, header_substr: str) -> list[str]:
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith("|") and header_substr.lower() in line.lower():
            start = i
            break
    if start is None:
        return []
    out: list[str] = []
    for line in lines[start + 1 :]:
        if not line.startswith("|"):
            break
        if re.match(r"^\|\s*:?-+\s*\|", line):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells:
            continue
        match = re.search(r"`([A-Za-z][A-Za-z0-9]+)`", cells[0])
        if not match:
            continue
        ident = match.group(1)
        if re.match(r"^[A-Z][A-Za-z0-9]+$", ident) and len(ident) >= 4:
            out.append(ident)
    return out


def parse_cli_events(text: str) -> list[str]:
    events: list[str] = []
    in_sec = False
    for line in text.splitlines():
        if re.match(r"^## Hook events\b", line):
            in_sec = True
            continue
        if in_sec and line.startswith("## ") and not line.startswith("## Hook events"):
            break
        if in_sec:
            match = re.match(r"^### ([A-Z][A-Za-z0-9]+)\s*$", line.strip())
            if match:
                events.append(match.group(1))
    if len(events) < 15:
        events = table_first_idents(text, "When it fires")
    return _uniq(events)


def parse_sdk_events(text: str) -> list[str]:
    events = table_first_idents(text, "Python SDK")
    if len(events) < 8:
        events = table_first_idents(text, "TypeScript SDK")
    return _uniq(events)


def parse_exit2_table(text: str) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith("|") and "Can block?" in line:
            start = i
            break
    if start is None:
        return rows
    for line in lines[start + 1 :]:
        if not line.startswith("|"):
            break
        if re.match(r"^\|\s*:?-+\s*\|", line):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        match = re.search(r"`([A-Za-z][A-Za-z0-9]+)`", cells[0])
        if not match:
            continue
        rows[match.group(1)] = {
            "can_block": cells[1].lower().startswith("yes"),
            "effect": cells[2],
        }
    return rows


def parse_timeout_defaults(cli_text: str, sdk_text: str) -> dict[str, Any]:
    cli: dict[str, Any] = {}
    match = re.search(r"Defaults:\s*(\d+)\s+for command", cli_text)
    if match:
        cli["command_default_s"] = int(match.group(1))
    match = re.search(r"UserPromptSubmit lowers[^\n]*?to (\d+)", cli_text)
    if match:
        cli["user_prompt_submit_s"] = int(match.group(1))
    match = re.search(r"MessageDisplay lowers[^\n]*?to (\d+)", cli_text)
    if match:
        cli["message_display_s"] = int(match.group(1))
    match = re.search(r"SessionEnd[^\n]{0,80}?([\d.]+)-second", cli_text)
    if match:
        cli["session_end_s"] = float(match.group(1))
    sdk: dict[str, Any] = {}
    match = re.search(
        r"(\d+)\s+seconds for most events,\s*(\d+)\s+seconds for `UserPromptSubmit`",
        sdk_text,
    )
    if match:
        sdk["most_events_s"] = int(match.group(1))
        sdk["user_prompt_submit_s"] = int(match.group(2))
    match = re.search(r"(\d+)\s+seconds for `MessageDisplay`", sdk_text)
    if match:
        sdk["message_display_s"] = int(match.group(1))
    match = re.search(r"SessionEnd[^\n]{0,120}?([\d.]+) seconds", sdk_text)
    if match:
        sdk["session_end_s"] = float(match.group(1))
    return {"cli": cli, "sdk": sdk}


def extra_fields(event: str) -> dict[str, Any]:
    toolish = {
        "PreToolUse",
        "PostToolUse",
        "PostToolUseFailure",
        "PostToolBatch",
        "PermissionRequest",
        "PermissionDenied",
    }
    if event in toolish:
        base: dict[str, Any] = {
            "tool_name": "Bash",
            "tool_input": {"command": "true", "description": "RES-0009 probe"},
            "tool_use_id": "toolu_res0009",
        }
        if event == "PostToolUse":
            base["tool_response"] = {
                "stdout": "ok",
                "stderr": "",
                "interrupted": False,
            }
        if event == "PostToolUseFailure":
            base["error"] = "simulated-failure"
        return base
    if event in {"UserPromptSubmit", "UserPromptExpansion"}:
        return {"prompt": "RES-0009 probe prompt"}
    if event == "SessionStart":
        return {"source": "startup", "model": "probe-not-a-client"}
    if event == "SessionEnd":
        return {"reason": "clear"}
    if event in {"SubagentStart", "SubagentStop"}:
        return {"agent_id": "agent_res0009", "agent_type": "general-purpose"}
    if event in {"Stop", "StopFailure"}:
        return {"last_assistant_message": "done"}
    if event == "Notification":
        return {"message": "notify"}
    if event == "PreCompact":
        return {"trigger": "manual"}
    if event == "PostCompact":
        return {"compact_result": "ok"}
    if event == "FileChanged":
        return {"file_path": "/tmp/res-0009.txt"}
    if event == "CwdChanged":
        return {"new_cwd": "/tmp"}
    if event == "DirectoryAdded":
        return {"path": "/tmp/extra"}
    if event == "Setup":
        return {"trigger": "init"}
    if event == "InstructionsLoaded":
        return {"file_path": "CLAUDE.md"}
    if event == "ConfigChange":
        return {"setting": "permissionMode"}
    if event in {"TaskCreated", "TaskCompleted"}:
        return {"task_id": "task_res0009", "subject": "probe"}
    if event in {"WorktreeCreate", "WorktreeRemove"}:
        return {"path": "/tmp/wt-res0009"}
    if event in {"Elicitation", "ElicitationResult"}:
        return {"server_name": "probe", "message": "input?"}
    if event == "MessageDisplay":
        return {"content": "hello"}
    if event == "TeammateIdle":
        return {"teammate_name": "probe"}
    return {}


def make_payload(event: str) -> dict[str, Any]:
    payload = {
        "session_id": "res-0009-session",
        "transcript_path": "/tmp/res-0009/transcript.jsonl",
        "cwd": str(REPO),
        "permission_mode": "default",
        "hook_event_name": event,
    }
    payload.update(extra_fields(event))
    return payload


def raw_payload_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def run_hook(
    script: Path,
    payload: dict[str, Any],
    timeout_s: float = 8.0,
    capture: Path | None = None,
) -> dict[str, Any]:
    data = raw_payload_bytes(payload)
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if capture is not None:
        capture.parent.mkdir(parents=True, exist_ok=True)
        env["RES0009_CAPTURE"] = str(capture)
    started = time.monotonic()
    timed_out = False
    try:
        proc = subprocess.run(
            [sys.executable, "-B", str(script)],
            input=data,
            capture_output=True,
            timeout=timeout_s,
            env=env,
            cwd=str(REPO),
        )
        returncode = proc.returncode
        stdout = proc.stdout
        stderr = proc.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        returncode = None
        stdout = exc.stdout or b""
        stderr = exc.stderr or b""
    elapsed = time.monotonic() - started
    return {
        "event": payload.get("hook_event_name"),
        "returncode": returncode,
        "stdout": stdout.decode("utf-8", errors="replace"),
        "stderr": stderr.decode("utf-8", errors="replace"),
        "timed_out": timed_out,
        "elapsed_s": round(elapsed, 4),
        "stdin_sha256": sha256_bytes(data),
        "script": str(script.relative_to(REPO)) if script.is_relative_to(REPO) else str(script),
    }


def interpret_exit2(
    event: str, table: dict[str, dict[str, Any]], returncode: int | None
) -> dict[str, Any]:
    row = table.get(event) or {"can_block": False, "effect": "unknown"}
    return {
        "event": event,
        "returncode": returncode,
        "can_block": bool(row.get("can_block")),
        "blocked": bool(returncode == 2 and row.get("can_block")),
        "effect": row.get("effect"),
    }


def discover_client() -> dict[str, Any]:
    binary = shutil.which("claude")
    version = None
    if binary:
        try:
            proc = subprocess.run(
                [binary, "--version"],
                capture_output=True,
                text=True,
                timeout=8,
            )
            lines = ((proc.stdout or "") + (proc.stderr or "")).strip().splitlines()
            version = lines[0] if lines else f"exit={proc.returncode}"
        except (OSError, subprocess.TimeoutExpired) as exc:
            version = f"unreadable:{type(exc).__name__}"
    home = Path.home() / ".claude"
    manifest = home / "hooks" / "_dispatch" / "manifest.json"
    return {
        "binary": binary,
        "version": version,
        "claude_home_exists": home.is_dir(),
        "dispatch_manifest": str(manifest),
        "dispatch_manifest_exists": manifest.is_file(),
        "live_session_fired": False,
    }
