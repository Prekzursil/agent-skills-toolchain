"""Isolated live-dispatcher trigger. Does not mutate ~/.claude or the live manifest.

Two measurements:
1. Committed manifest as-is (Windows hooks_root on this Linux box).
2. Scratch manifest with hooks_root rewritten to repo hooks/, HOME/TMP in scratch.
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import inventory as I  # noqa: E402

DISPATCH_PY = REPO / "hooks" / "_dispatch" / "dispatch.py"
SCRATCH = HERE / "scratch" / "live-dispatch"


def _load_dispatch():
    spec = importlib.util.spec_from_file_location("aud0059_dispatch", DISPATCH_PY)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load hooks/_dispatch/dispatch.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(mod, event: str, payload: dict[str, Any], manifest: dict[str, Any]) -> tuple[Any, str]:
    old_out, old_in, old_err = sys.stdout, sys.stdin, sys.stderr
    cap = io.StringIO()
    sys.stdout = mod._ThreadStdout(old_out)
    sys.stdin = mod._ThreadStdin(old_in)
    sys.stderr = cap
    try:
        out = mod.run(event, json.dumps(payload), manifest)
    finally:
        sys.stdout, sys.stdin, sys.stderr = old_out, old_in, old_err
    return out, cap.getvalue()


def _payload_for(event: str, matcher: Any) -> dict[str, Any]:
    tool = "Read"
    if isinstance(matcher, str) and matcher.strip():
        # Pick a concrete tool_name that satisfies the regex.
        if "Bash" in matcher:
            tool = "Bash"
        elif "Write" in matcher:
            tool = "Write"
        elif "Edit" in matcher:
            tool = "Edit"
        elif "Task" in matcher:
            tool = "Task"
        elif "mcp__basic-memory" in matcher:
            tool = "mcp__basic-memory__write_note"
        elif "PowerShell" in matcher:
            tool = "PowerShell"
        elif "Workflow" in matcher:
            tool = "Workflow"
        elif "mcp__codex" in matcher:
            tool = "mcp__codex__codex"
    return {
        "hook_event_name": event,
        "session_id": "aud-0059-scratch",
        "cwd": str(REPO),
        "tool_name": tool,
        "tool_input": {"command": "echo aud-0059"},
    }


def committed_manifest_trigger() -> dict[str, Any]:
    """Run the live dispatcher against the committed manifest (no hook code if root is bad)."""
    if not DISPATCH_PY.is_file():
        return {"ran": False, "reason": "dispatch.py absent"}
    man = I.load_live_manifest()
    if not man:
        return {"ran": False, "reason": "live manifest absent"}
    mod = _load_dispatch()
    root = str(man.get("hooks_root") or "")
    receipts: list[str] = []
    selected = 0
    events_payloads = [
        ("SessionStart", ""),
        ("Stop", ""),
        ("PostToolUse", "Write"),
        ("PostToolUse", "Bash"),
        ("PreToolUse", "Write"),
        ("PreToolUse", "Bash"),
        ("PreToolUse", "Task"),
        ("PreToolUse", "mcp__basic-memory__write_note"),
        ("PreToolUse", "mcp__codex__codex"),
    ]
    for event, tool in events_payloads:
        if event not in (man.get("events") or {}):
            continue
        payload = _payload_for(event, None)
        payload["tool_name"] = tool
        _out, err = _run(mod, event, payload, man)
        if err.strip():
            selected += 1
            for line in err.splitlines():
                if line.strip() and line not in receipts:
                    receipts.append(line.strip())
    load_failed = sum(1 for r in receipts if "status=load-failed" in r or "status=out-of-root" in r)
    return {
        "ran": True,
        "hooks_root": root,
        "hooks_root_exists": Path(root).exists() if root else False,
        "receipt_count": len(receipts),
        "load_failed_or_out_of_root": load_failed,
        "receipts_sample": receipts[:12],
        "windows_root_on_linux": (":/" in root.replace("\\", "/")) or root.lower().startswith("c:"),
    }


def isolated_heartbeat() -> dict[str, Any]:
    """SessionStart heartbeat with hooks_root = repo hooks/ and HOME in scratch."""
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True)
    home = SCRATCH / "home"
    tmp = SCRATCH / "tmp"
    home.mkdir()
    tmp.mkdir()
    old_env = {
        k: os.environ.get(k)
        for k in (
            "HOME",
            "TMPDIR",
            "TEMP",
            "TMP",
            "EVENT_LEDGER_ROOT",
            "BG_REGISTRY_DIR",
            "MEMORY_SPOOL_DIR",
            "HEARTBEAT_STATE_DIR",
            "MONITOR_AUTOLAUNCH",
            "GIT_HYGIENE",
            "DARK_SURFACE",
        )
    }
    os.environ["HOME"] = str(home)
    os.environ["TMPDIR"] = str(tmp)
    os.environ["TEMP"] = str(tmp)
    os.environ["TMP"] = str(tmp)
    os.environ["EVENT_LEDGER_ROOT"] = str(SCRATCH / "event-ledger")
    os.environ["BG_REGISTRY_DIR"] = str(home / ".claude" / "bg-registry")
    os.environ["MEMORY_SPOOL_DIR"] = str(home / ".claude" / "memory-spool")
    os.environ["HEARTBEAT_STATE_DIR"] = str(tmp / "heartbeat")
    os.environ["MONITOR_AUTOLAUNCH"] = "off"
    os.environ["GIT_HYGIENE"] = "off"
    os.environ["DARK_SURFACE"] = "off"
    try:
        mod = _load_dispatch()
        manifest = {
            "version": 1,
            "hooks_root": str(REPO / "hooks"),
            "events": {
                "SessionStart": {
                    "checks": [
                        {
                            "name": "heartbeat",
                            "script": "heartbeat/heartbeat.py",
                            "args": ["sessionstart"],
                            "timeout": 8,
                            "emits": True,
                            "side_effect": "state",
                        }
                    ]
                }
            },
        }
        payload = {
            "hook_event_name": "SessionStart",
            "session_id": "aud-0059-heartbeat",
            "cwd": str(REPO),
        }
        out, err = _run(mod, "SessionStart", payload, manifest)
        text = "" if out is None else str(out)
        injected = "[health]" in text or "bg:" in text
        return {
        "ran": True,
        "observable_effect": injected,
        "inject_context": injected,
        "aggregate_empty": out is None or not str(out).strip(),
        "aggregate_tail": text[-400:],
        "stderr_tail": err.strip()[-300:],
        "hooks_root": str(REPO / "hooks"),
        "two_signals": bool(injected),
    }
    finally:
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def run_live() -> dict[str, Any]:
    committed = committed_manifest_trigger()
    heart = isolated_heartbeat()
    return {
        "committed_manifest": committed,
        "isolated_heartbeat": heart,
        "pass": bool(heart.get("observable_effect"))
        and bool(committed.get("ran")),
    }


if __name__ == "__main__":
    result = run_live()
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result.get("pass") else 1)
