#!/usr/bin/env python3
r"""bg-registry/_common.py — shared helpers for the background-work registry trio
(register.py / done_marker.py / reconcile.py).

These mirror the B1 hook conventions (mcp-liveness/liveness.py state-file handling,
persist-nudge/_first_session dedup, the `emit` JSON shape, session-id extraction,
fail-open file I/O) but are kept SELF-CONTAINED in this dir so the registry hooks
have NO cross-dir import coupling — exactly how liveness.py / checkpoint.py / nudge.py
each re-implement their own tiny emit/session helpers.

Pure stdlib. Every public helper swallows its own errors (returns a safe default) so
callers can stay simple and FAIL-OPEN.
"""
from __future__ import annotations

import ctypes
import json
import os
import time
from pathlib import Path

# Registry root: one append-only NDJSON file per session: <session>.ndjson .
BG_DIR = Path(os.environ.get(
    "BG_REGISTRY_DIR", str(Path.home() / ".claude" / "bg-registry")))
# Sidecar (NOT the registry) — reconcile.py records which orphans it has already
# surfaced so it alerts ONCE, never nags. Keeps reconcile READER-only vs the registry.
SEEN_FILE = BG_DIR / ".reconciled.json"

# An artifact counts as "complete" once it has at least this many bytes (a 0-byte
# file is the classic "detached launch returned success but never wrote anything").
MIN_ARTIFACT_BYTES = int(os.environ.get("BG_REGISTRY_MIN_ARTIFACT_BYTES", "1"))


def now() -> float:
    return time.time()


def fmt_ts(ts) -> str:
    try:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(float(ts)))
    except Exception:
        return "?"


def _safe(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "-" for c in str(s))[:80] or "default"


def session_id(data: dict) -> str:
    """Extract the session id (B1 convention: data['session_id'])."""
    return str((data or {}).get("session_id") or "default").replace("/", "_").replace("\\", "_")


def registry_file(sid: str) -> Path:
    return BG_DIR / f"{_safe(sid)}.ndjson"


def append_record(sid: str, rec: dict) -> bool:
    """Append one NDJSON record to this session's registry. FAIL-OPEN -> bool."""
    try:
        BG_DIR.mkdir(parents=True, exist_ok=True)
        with registry_file(sid).open("a", encoding="utf-8", errors="replace") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False


def read_records(path: Path):
    """Yield each JSON record from an NDJSON file (skipping blank/corrupt lines)."""
    try:
        if not Path(path).exists():
            return
        with Path(path).open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except Exception:
                    continue
    except Exception:
        return


def fold(records) -> dict:
    """Fold an append-only NDJSON stream into effective state, keyed by id.

    The first line for an id is the full spawn record; later lines (status updates
    like {"id": X, "status": "done"}) are merged over it (last write wins per key).
    Records with no id are ignored.
    """
    eff: dict = {}
    for r in records:
        if not isinstance(r, dict):
            continue
        rid = r.get("id")
        if not rid:
            continue
        if rid in eff:
            eff[rid].update(r)
        else:
            eff[rid] = dict(r)
    return eff


# ---------------------------------------------------------------------------
# Process liveness — OS process table, stdlib-only, cross-platform.
# NB: on Windows os.kill(pid, 0) actually CALLS TerminateProcess (it would KILL the
# pid!), so we must use OpenProcess+GetExitCodeProcess via ctypes, never os.kill.
# Returns True (alive) / False (dead) / None (cannot determine).
# ---------------------------------------------------------------------------
def _win_pid_alive(pid: int):
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    ERROR_INVALID_PARAMETER = 87  # no such pid
    ERROR_ACCESS_DENIED = 5       # pid EXISTS but we lack rights -> alive
    try:
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.restype = wintypes.HANDLE
        k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k32.GetExitCodeProcess.restype = wintypes.BOOL
        k32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        k32.CloseHandle.argtypes = [wintypes.HANDLE]

        h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            err = ctypes.get_last_error()
            if err == ERROR_ACCESS_DENIED:
                return True
            if err == ERROR_INVALID_PARAMETER:
                return False
            return None
        try:
            code = wintypes.DWORD(0)
            if not k32.GetExitCodeProcess(h, ctypes.byref(code)):
                return None
            return code.value == STILL_ACTIVE
        finally:
            k32.CloseHandle(h)
    except Exception:
        return None


def pid_alive(pid):
    """True/False/None — is OS process `pid` currently alive?"""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return None
    if pid <= 0:
        return None
    if os.name == "nt":
        return _win_pid_alive(pid)
    try:
        os.kill(pid, 0)  # POSIX: signal 0 only checks existence (safe)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return None


def artifact_complete(path) -> bool:
    """True iff the declared artifact exists and is non-trivial.

    A directory artifact is complete when it is non-empty; a file when it has at
    least MIN_ARTIFACT_BYTES (catches the 0-byte 'wired-but-dead' launch).
    """
    if not path:
        return False
    try:
        p = Path(path)
        if p.is_dir():
            return any(p.iterdir())
        return p.is_file() and p.stat().st_size >= MIN_ARTIFACT_BYTES
    except OSError:
        return False
    except Exception:
        return False


def load_seen() -> dict:
    try:
        return json.loads(SEEN_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_seen(seen: dict) -> None:
    try:
        BG_DIR.mkdir(parents=True, exist_ok=True)
        # bound the sidecar: keep the 500 most-recent ids
        if len(seen) > 500:
            keep = sorted(seen.items(), key=lambda kv: kv[1], reverse=True)[:500]
            seen = dict(keep)
        SEEN_FILE.write_text(json.dumps(seen), encoding="utf-8")
    except Exception:
        pass


def emit(event_name: str, msg: str) -> None:
    """Inject additionalContext (B1 `emit` shape)."""
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": event_name, "additionalContext": msg}}))


def read_stdin() -> dict:
    import sys
    try:
        return json.loads(sys.stdin.read() or "{}")
    except Exception:
        return {}
