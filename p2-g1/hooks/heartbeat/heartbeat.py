#!/usr/bin/env python3
r"""heartbeat/heartbeat.py — one-line durability HEALTH BANNER.

A pure, cheap READER that folds the three durability ledgers into a single terse line:

    [health] bg:Nopen spool:Nunflushed mem:up|DOWN|? re-harness:Nreg|off

  bg:Nopen        — running (un-reconciled) records in the bg-registry (Check 1)
  spool:Nunflushed— spooled basic-memory writes not yet confirmed saved (Check 2)
  mem:up|DOWN|?   — last mcp-liveness probe result for basic-memory (the keystone store)
  re-harness:...  — count of registered RE daemons (report-only; never probed here)

Modes (mirrors mcp-liveness/liveness.py):
  sessionstart  SessionStart  -> ALWAYS emits the banner (the resume-time health view).
  stop          Stop          -> emits ONLY when something is noteworthy (open bg work,
                                 unflushed spool, or memory DOWN) AND a throttle window
                                 has elapsed, so a healthy steady state stays silent.
  probe         CLI/testing    -> prints the banner + a SUCCESS/FAILED marker (no hook JSON).

Reads only files written by other hooks (no network, no process probes, no MCP calls).
FAIL-OPEN: any error -> exit 0. Opt-out: HEARTBEAT=off or a .disabled file.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

THIS = Path(__file__).resolve().parent
DISABLED = THIS / ".disabled"

HOME = Path.home()
BG_DIR = Path(os.environ.get("BG_REGISTRY_DIR", str(HOME / ".claude" / "bg-registry")))
SPOOL_DIR = Path(
    os.environ.get("MEMORY_SPOOL_DIR", str(HOME / ".claude" / "memory-spool"))
)
LIVENESS_STATE_DIR = Path(
    os.environ.get(
        "MCP_LIVENESS_STATE_DIR",
        str(Path(os.environ.get("TEMP", "/tmp")) / "mcp-liveness"),
    )
)
CRITICAL_JSON = Path(
    os.environ.get(
        "HEARTBEAT_CRITICAL_JSON",
        str(HOME / ".claude" / "hooks" / "mcp-liveness" / "critical.json"),
    )
)
STATE_DIR = Path(
    os.environ.get(
        "HEARTBEAT_STATE_DIR", str(Path(os.environ.get("TEMP", "/tmp")) / "heartbeat")
    )
)
THROTTLE_SEC = float(os.environ.get("HEARTBEAT_THROTTLE_SEC", "900"))


def _disabled() -> bool:
    return DISABLED.exists() or os.environ.get("HEARTBEAT", "").lower() in (
        "off",
        "0",
        "false",
    )


def _safe(s: str) -> str:
    return (
        "".join(c if c.isalnum() or c in "-_." else "-" for c in str(s))[:80]
        or "default"
    )


def _iter_json_lines(path: Path):
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
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


def bg_open_count() -> int:
    """Number of bg-registry records whose effective status is still 'running'."""
    total = 0
    try:
        if not BG_DIR.exists():
            return 0
        for f in BG_DIR.glob("*.ndjson"):
            eff: dict = {}
            for r in _iter_json_lines(f):
                rid = r.get("id") if isinstance(r, dict) else None
                if not rid:
                    continue
                eff.setdefault(rid, {}).update(r)
            total += sum(1 for rec in eff.values() if rec.get("status") == "running")
    except Exception:
        return total
    return total


def spool_unflushed_count() -> int:
    try:
        if not SPOOL_DIR.exists():
            return 0
        return sum(1 for p in SPOOL_DIR.glob("*.json") if not p.name.startswith("."))
    except Exception:
        return 0


def mem_state(sid: str) -> str:
    """Is basic-memory (:8765) actually listening RIGHT NOW?

    A live socket probe (~ms) instead of the mcp-liveness *last* probe, which can
    read DOWN long after a restart already fixed it — a false alarm that erodes
    trust in the whole banner. Listening => up; not => DOWN. The mcp-liveness
    PreToolUse hook still does the real MCP handshake when a memory op actually runs.
    """
    import socket

    port = int(os.environ.get("BASIC_MEMORY_PORT", "8765"))
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.4):
            return "up"
    except Exception:
        return "DOWN"


def reharness_summary() -> str:
    """Count registered RE daemons from the harness registry (no probing)."""
    try:
        cfg = json.loads(CRITICAL_JSON.read_text(encoding="utf-8"))
        reg_path = ((cfg.get("reharness") or {}).get("registry") or "").strip()
        if not reg_path:
            return "off"
        reg = json.loads(Path(reg_path).read_text(encoding="utf-8"))
        tools = (reg or {}).get("tools") or {}
        return f"{len(tools)}reg" if tools else "off"
    except Exception:
        return "off"


def build_summary(sid: str) -> dict:
    bg = bg_open_count()
    spool = spool_unflushed_count()
    mem = mem_state(sid)
    rh = reharness_summary()
    return {
        "bg": bg,
        "spool": spool,
        "mem": mem,
        "reharness": rh,
        "noteworthy": (bg > 0 or spool > 0 or mem == "DOWN"),
        "line": f"[health] bg:{bg}open spool:{spool}unflushed mem:{mem} re-harness:{rh}",
    }


def _state_file(sid: str) -> Path:
    return STATE_DIR / f"{_safe(sid)}.json"


def _last_emit(sid: str) -> float:
    try:
        return float(
            json.loads(_state_file(sid).read_text(encoding="utf-8")).get("last_emit", 0)
        )
    except Exception:
        return 0.0


def _mark_emit(sid: str) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        _state_file(sid).write_text(
            json.dumps({"last_emit": time.time()}), encoding="utf-8"
        )
    except Exception:
        pass


def emit(event_name: str, msg: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": event_name,
                    "additionalContext": msg,
                }
            }
        )
    )


def run(mode: str, data: dict) -> int:
    sid = str((data or {}).get("session_id") or "default")
    summ = build_summary(sid)

    if mode == "sessionstart":
        emit("SessionStart", summ["line"])
        _mark_emit(sid)
        return 0

    # stop: only when noteworthy AND past the throttle window (healthy -> silent).
    if not summ["noteworthy"]:
        return 0
    if (time.time() - _last_emit(sid)) < THROTTLE_SEC:
        return 0
    emit("Stop", summ["line"])
    _mark_emit(sid)
    return 0


def main(argv) -> int:
    try:
        if _disabled():
            return 0
        mode = (argv[0] if argv else "sessionstart").lower()
        if mode == "probe":
            summ = build_summary(os.environ.get("HEARTBEAT_PROBE_SID", "probe"))
            print(summ["line"])
            print(f"SUCCESS:heartbeat {summ['line'][9:]}")
            return 0
        try:
            data = json.loads(sys.stdin.read() or "{}")
        except Exception:
            data = {}
        return run(mode, data)
    except Exception:
        return 0  # fail-open


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
