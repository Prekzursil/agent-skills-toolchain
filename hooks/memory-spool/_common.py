#!/usr/bin/env python3
r"""memory-spool/_common.py — shared helpers for the write-ahead memory spool
(spool.py PreToolUse + flush_check.py PostToolUse/SessionStart).

Mirrors B1 conventions (mcp-liveness state handling, the `emit` JSON shape, fail-open
file I/O, session-id extraction) but kept self-contained in this dir — no cross-dir
import coupling, exactly like liveness.py / checkpoint.py / nudge.py each do.

The spool is the durable companion to mcp-liveness: liveness HEALS the basic-memory
server, but a note you were writing WHILE it was down is gone. We persist the intended
payload to a local file BEFORE the MCP call so it can be re-flushed/surfaced even if the
call (or the whole session) dies. Pure stdlib.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

SPOOL_DIR = Path(os.environ.get(
    "MEMORY_SPOOL_DIR", str(Path.home() / ".claude" / "memory-spool")))
# Sidecar so SessionStart surfaces each unflushed entry once, then prunes.
REPORTED_FILE = SPOOL_DIR / ".reported.json"
# Spool entries older than this are garbage-collected at SessionStart.
SPOOL_TTL_DAYS = float(os.environ.get("MEMORY_SPOOL_TTL_DAYS", "14"))

# The basic-memory write tools we spool. write_note creates/overwrites; edit_note
# appends/patches. Both are durable memory writes whose loss is the failure mode.
SPOOLED_TOOLS = ("mcp__basic-memory__write_note", "mcp__basic-memory__edit_note")


def now() -> float:
    return time.time()


def session_id(data: dict) -> str:
    return str((data or {}).get("session_id") or "default").replace("/", "_").replace("\\", "_")


def read_stdin() -> dict:
    try:
        return json.loads(sys.stdin.read() or "{}")
    except Exception:
        return {}


def emit(event_name: str, msg: str) -> None:
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": event_name, "additionalContext": msg}}))


def payload_key(tool_name: str, tool_input: dict) -> str:
    """Stable key derived from the call so PreToolUse and PostToolUse agree.

    PostToolUse sees the SAME tool_input as PreToolUse, so a hash of it correlates
    the spool file to its completion without relying on a shared tool_use_id.
    """
    try:
        blob = (str(tool_name) + "|" + json.dumps(tool_input or {}, sort_keys=True,
                                                  ensure_ascii=False))
    except Exception:
        blob = str(tool_name) + "|" + repr(tool_input)
    return hashlib.sha1(blob.encode("utf-8", "replace")).hexdigest()[:12]


def title_of(tool_name: str, tool_input: dict) -> str:
    ti = tool_input or {}
    if tool_name.endswith("edit_note"):
        return str(ti.get("identifier") or ti.get("title") or "(edit)")[:80]
    return str(ti.get("title") or ti.get("identifier") or "(untitled note)")[:80]


def spool_path(ts: float, key: str) -> Path:
    return SPOOL_DIR / f"{int(ts)}-{key}.json"


def write_spool(rec: dict) -> Path | None:
    try:
        SPOOL_DIR.mkdir(parents=True, exist_ok=True)
        p = spool_path(rec["ts"], rec["key"])
        p.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
        return p
    except Exception:
        return None


def find_spools(key: str) -> list[Path]:
    """All spool files for a payload key (usually one; >1 only on rapid identical retries)."""
    try:
        return sorted(SPOOL_DIR.glob(f"*-{key}.json"))
    except Exception:
        return []


def find_spools_by_uid(uid: str) -> list[Path]:
    """Secondary correlation: spool files whose stored tool_use_id matches.

    Defends against the (unlikely) case where Claude Code delivers a slightly
    different tool_input to PostToolUse than PreToolUse, which would otherwise make
    the payload-hash drift and leave a successful write's spool entry to linger as a
    false 'unflushed' alert. If the call carries a tool_use_id we match on that too.
    """
    out: list[Path] = []
    if not uid:
        return out
    for p in list_spools():
        if load_json(p).get("tool_use_id") == uid:
            out.append(p)
    return out


def list_spools() -> list[Path]:
    try:
        return sorted(p for p in SPOOL_DIR.glob("*.json") if not p.name.startswith("."))
    except Exception:
        return []


def load_json(p: Path) -> dict:
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return {}


def response_ok(tr) -> bool:
    """Did the basic-memory write actually land?

    Bias is deliberate and asymmetric: we only declare SUCCESS on a clearly non-empty,
    non-error result; ANY error envelope or empty result -> NOT ok (keep the spool).
    Keeping a spool we didn't need is mild noise; dropping one we needed is the silent
    4h-memory-loss we are here to prevent — so when uncertain we keep it.
    """
    if tr is None:
        return False
    if isinstance(tr, bool):
        return tr
    if isinstance(tr, str):
        s = tr.strip()
        if not s:
            return False
        low = s.lower()
        if low.startswith(("error", "mcp error", "tool execution failed",
                           "exception", "traceback", "failed")):
            return False
        return True
    if isinstance(tr, dict):
        if tr.get("isError") is True or tr.get("is_error") is True:
            return False
        if tr.get("error"):
            return False
        if str(tr.get("status", "")).lower() in ("error", "failed"):
            return False
        # Unwrap one nesting level some CC versions use.
        for k in ("result", "output", "response"):
            inner = tr.get(k)
            if isinstance(inner, (dict, list, str)):
                return response_ok(inner)
        content = tr.get("content")
        if content not in (None, "", [], {}):
            return True
        # Dict with neither error nor recognizable content -> treat empty as failure,
        # otherwise assume the call returned something meaningful.
        return bool(tr) and bool([k for k in tr if k not in ("isError", "is_error")])
    if isinstance(tr, list):
        return len(tr) > 0
    return True  # unknown non-empty type -> assume ok (avoid false alerts)


def load_reported() -> dict:
    return load_json(REPORTED_FILE) if REPORTED_FILE.exists() else {}


def save_reported(rep: dict) -> None:
    try:
        SPOOL_DIR.mkdir(parents=True, exist_ok=True)
        if len(rep) > 500:
            rep = dict(sorted(rep.items(), key=lambda kv: kv[1], reverse=True)[:500])
        REPORTED_FILE.write_text(json.dumps(rep), encoding="utf-8")
    except Exception:
        pass
