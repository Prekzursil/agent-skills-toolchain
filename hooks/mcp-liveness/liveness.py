#!/usr/bin/env python3
r"""MCP-LIVENESS SELF-HEAL + ALERT — the keystone fix for the silent memory loss.

THE problem this solves: basic-memory's shared HTTP daemon (127.0.0.1:8765) can
die mid-session; the agent then keeps "saving" to a dead store and SILENTLY loses
hours of memory (the documented 4h loss). This hook makes the agent NEVER proceed
silently with a dead memory store:

  * SessionStart  -> always probe basic-memory (the resume-after-hours case).
  * PreToolUse    -> probe before basic-memory tool calls, THROTTLED ~60s so rapid
                     successive memory ops don't each re-probe.
  If a critical MCP is DOWN (or dead-but-listening — TCP up, MCP handshake fails):
    (a) attempt an AUTO-RESTART (basic-memory via restart-basic-memory.ps1, launched
        DETACHED so this hook never blocks), and
    (b) INJECT a LOUD additionalContext alert telling the agent memory is NOT being
        saved and to verify before relying on recall.

Liveness == a REAL MCP handshake (socket + JSON-RPC `initialize`), not just a port
being open — mirrors mcp_doctor's _mcp_handshake_ok so a dead-but-listening corpse
is caught. We deliberately do NOT call search_notes (it triggers a ~7s embed-model
load); `initialize` answers in well under a second.

re-harness RE daemons (IDA/Ghidra/...) are checked ONLY when registered in the
harness registry (so no noise when not doing RE) and are REPORT-ONLY (restart hint,
never auto-killed here).

DESIGN CONTRACT (AGENTS.md s6): FAIL-OPEN. Every path is wrapped; ANY error -> exit 0,
emit nothing. Inject-only (never blocks). Opt-out: MCP_LIVENESS=off or a .disabled file.

Usage (wired in settings.json):
  python liveness.py sessionstart   # SessionStart hook
  python liveness.py pretool        # PreToolUse(mcp__basic-memory__.*) hook
  python liveness.py probe          # CLI: print status JSON + SUCCESS/FAILED marker (testing)
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

THIS = Path(__file__).resolve().parent
CONFIG_PATH = THIS / "critical.json"
DISABLED = THIS / ".disabled"

# Per-session liveness state (throttle + alert dedup). Override for tests.
STATE_DIR = Path(
    os.environ.get(
        "MCP_LIVENESS_STATE_DIR",
        str(Path(os.environ.get("TEMP", "/tmp")) / "mcp-liveness"),
    )
)

# Streamable-HTTP handshake codes: the server IS serving MCP but wants a session /
# different content negotiation (NOT a generic 404/501 "nothing here"). Mirrors
# re-harness lib/mcp_doctor_core._mcp_handshake_ok.
_HANDSHAKE_CODES = {400, 405, 406, 409, 415, 426}


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
def load_config() -> dict:
    try:
        with CONFIG_PATH.open("r", encoding="utf-8", errors="replace") as fh:
            return json.load(fh)
    except Exception:
        # Hard-coded minimal fallback so the keystone still works if the JSON is gone.
        return {
            "throttle_seconds": 60,
            "handshake_timeout": 5.0,
            "tcp_timeout": 1.5,
            "critical": {
                "basic-memory": {
                    "url": "http://127.0.0.1:8765/mcp",
                    "host": "127.0.0.1",
                    "port": 8765,
                    "auto_restart": True,
                    "restart_helper": "restart-basic-memory.ps1",
                    "why": "semantic memory vault",
                }
            },
            "reharness": {
                "registry": "",
                "auto_restart": False,
                "restart_hint": "re_launch.py",
            },
        }


# ---------------------------------------------------------------------------
# Probes
# ---------------------------------------------------------------------------
def tcp_up(host: str, port: int, timeout: float) -> bool:
    """True iff a TCP connection to host:port is accepted within `timeout`."""
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except Exception:
        return False


def mcp_handshake(url: str, timeout: float):
    """Does the endpoint complete a minimal MCP `initialize` handshake?

    Returns True  -> server answered MCP (JSON-RPC result/error, SSE, or a
                     streamable-http session-handshake status).
            False -> TCP answered but it is NOT MCP (dead-but-listening corpse).
            None  -> unreachable.
    """
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "mcp-liveness", "version": "1.0"},
            },
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
    )
    try:
        # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected -- internal MCP liveness probe; URL from local config, not untrusted user data
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return True if exc.code in _HANDSHAKE_CODES else False
    except (urllib.error.URLError, OSError, socket.timeout):
        return None
    except Exception:
        # Malformed/non-HTTP response from a corpse on the port -> TCP is up but
        # this does not speak MCP. Caller (TCP already confirmed up) reads None as
        # dead-but-listening, which is the correct classification.
        return None
    # Parse application/json or SSE ("data: {json}")
    try:
        obj = None
        for line in body.splitlines():
            s = line.strip()
            if s.startswith("data:"):
                obj = json.loads(s[5:].strip())
                break
        if obj is None:
            obj = json.loads(body)
        return isinstance(obj, dict) and ("result" in obj or "error" in obj)
    except Exception:
        # Server answered with a body but it isn't JSON-RPC — still "spoke" over MCP.
        return True


def probe_critical(name: str, spec: dict, cfg: dict) -> dict:
    """Probe one critical server -> {name, state in up|down|dead-listening, ...}."""
    host = spec.get("host", "127.0.0.1")
    port = int(spec.get("port", 0))
    url = spec.get("url", "")
    tcp_t = float(cfg.get("tcp_timeout", 1.5))
    hs_t = float(cfg.get("handshake_timeout", 5.0))

    if not tcp_up(host, port, tcp_t):
        return {
            "name": name,
            "state": "down",
            "tcp": False,
            "mcp_ok": None,
            "url": url,
            "why": spec.get("why", ""),
        }
    hs = mcp_handshake(url, hs_t)
    state = "up" if hs else "dead-listening"
    return {
        "name": name,
        "state": state,
        "tcp": True,
        "mcp_ok": bool(hs),
        "url": url,
        "why": spec.get("why", ""),
    }


def probe_reharness(cfg: dict) -> list:
    """Probe re-harness RE daemons ONLY if registered (registry tools non-empty).

    Report-only: returns the list of registered-but-down daemons (never restarted
    here — RE daemons are heavy/context-specific; we just surface a hint).
    """
    rh = cfg.get("reharness") or {}
    reg_path = rh.get("registry") or ""
    if not reg_path:
        return []
    try:
        reg = json.loads(Path(reg_path).read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return []
    tools = (reg or {}).get("tools") or {}
    if not tools:
        return []  # nothing registered -> not doing RE -> silent
    down = []
    tcp_t = float(cfg.get("tcp_timeout", 1.5))
    for tool, info in tools.items():
        try:
            port = int((info or {}).get("port") or 0)
        except Exception:
            port = 0
        if not port:
            continue
        if not tcp_up("127.0.0.1", port, tcp_t):
            down.append({"name": f"re:{tool}", "port": port, "state": "down"})
    return down


# ---------------------------------------------------------------------------
# State (throttle + alert dedup), per session
# ---------------------------------------------------------------------------
def _state_file(sid: str) -> Path:
    safe = (
        "".join(c if c.isalnum() or c in "-_." else "-" for c in str(sid))[:80]
        or "default"
    )
    return STATE_DIR / f"{safe}.json"


def load_state(sid: str) -> dict:
    try:
        return json.loads(_state_file(sid).read_text(encoding="utf-8"))
    except Exception:
        return {
            "last_check": 0.0,
            "last_state": "unknown",
            "alerted_down": False,
            "restart_attempted": False,
        }


def save_state(sid: str, st: dict) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        _state_file(sid).write_text(json.dumps(st), encoding="utf-8")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Restart (detached — never blocks the hook)
# ---------------------------------------------------------------------------
def attempt_restart(spec: dict, dead_listening: bool) -> bool:
    """Launch the basic-memory restart helper DETACHED. Returns True if launched."""
    helper = spec.get("restart_helper")
    if not helper:
        return False
    ps1 = THIS / helper
    if not ps1.exists():
        return False
    args = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1)]
    if dead_listening:
        args += ["-KillCorpse"]
    try:
        flags = 0
        if os.name == "nt":
            # NOTE: do NOT add DETACHED_PROCESS here — on Windows it prevents the
            # powershell child from actually executing (verified: marker never
            # written). CREATE_NEW_PROCESS_GROUP keeps the child alive after this
            # short-lived hook exits; CREATE_NO_WINDOW hides the console flash.
            flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200) | getattr(
                subprocess, "CREATE_NO_WINDOW", 0x08000000
            )
        subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=flags,
        )
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Alert formatting
# ---------------------------------------------------------------------------
def format_alert(down: list, reharness_down: list, restarted: bool) -> str:
    parts = []
    for d in down:
        if d["name"] == "basic-memory":
            verb = (
                "DOWN"
                if d["state"] == "down"
                else "DEAD-but-LISTENING (corpse on the port)"
            )
            parts.append(
                f"WARNING: basic-memory {verb} - memory is NOT being saved and "
                f"recall is UNRELIABLE. "
                + (
                    "Auto-restart attempted - VERIFY (call a basic-memory tool) before "
                    "relying on recall, and re-save anything important. "
                    if restarted
                    else "Auto-restart could NOT be launched - start it manually: "
                    "Start-ScheduledTask -TaskName BasicMemory-HTTP-MCP. "
                )
            )
        else:
            parts.append(f"WARNING: critical MCP '{d['name']}' is {d['state']}.")
    if reharness_down:
        names = ", ".join(f"{r['name']}(:{r['port']})" for r in reharness_down)
        parts.append(
            f"RE daemon(s) registered but DOWN: {names}. "
            f"Restart via re_launch.py before relying on RE MCP calls."
        )
    return "[mcp-liveness] " + " ".join(parts)


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


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def run(mode: str, data: dict) -> int:
    cfg = load_config()
    sid = str(data.get("session_id") or "default")
    now = time.time()
    st = load_state(sid)
    throttle = float(cfg.get("throttle_seconds", 60))

    # PreToolUse fast-path: if we very recently saw the keystone UP, skip the probe.
    if mode == "pretool":
        if (
            now - float(st.get("last_check", 0)) < throttle
            and st.get("last_state") == "up"
        ):
            return 0

    critical = cfg.get("critical") or {}
    results = [probe_critical(name, spec, cfg) for name, spec in critical.items()]
    down = [r for r in results if r["state"] != "up"]
    reharness_down = probe_reharness(cfg)

    if not down and not reharness_down:
        save_state(
            sid,
            {
                "last_check": now,
                "last_state": "up",
                "alerted_down": False,
                "restart_attempted": False,
            },
        )
        return 0  # healthy -> silent

    # Something critical is down. Auto-restart (once per down-episode) + alert.
    restarted = bool(st.get("restart_attempted"))
    if not st.get("restart_attempted"):
        for r in down:
            spec = critical.get(r["name"], {})
            if spec.get("auto_restart"):
                if attempt_restart(
                    spec, dead_listening=(r["state"] == "dead-listening")
                ):
                    restarted = True
        st["restart_attempted"] = True

    # SessionStart always alerts when down (the resume-after-hours case is critical);
    # PreToolUse alerts once per down-episode (no nagging on every memory call).
    should_alert = (mode == "sessionstart") or (not st.get("alerted_down"))
    event = "SessionStart" if mode == "sessionstart" else "PreToolUse"
    if should_alert and down:
        emit(event, format_alert(down, reharness_down, restarted))
        st["alerted_down"] = True
    elif should_alert and reharness_down and mode == "sessionstart":
        emit(event, format_alert([], reharness_down, False))

    st.update({"last_check": now, "last_state": down[0]["state"] if down else "up"})
    save_state(sid, st)
    return 0


def main(argv) -> int:
    try:
        if DISABLED.exists() or os.environ.get("MCP_LIVENESS", "").lower() in (
            "off",
            "0",
            "false",
        ):
            return 0
        mode = (argv[0] if argv else "sessionstart").lower()

        if mode == "probe":
            # CLI test mode: print status + terminal-state marker, no restart/alert.
            cfg = load_config()
            results = [
                probe_critical(n, s, cfg)
                for n, s in (cfg.get("critical") or {}).items()
            ]
            rh = probe_reharness(cfg)
            down = [r for r in results if r["state"] != "up"]
            report = {"critical": results, "reharness_down": rh}
            marker = (
                "SUCCESS:liveness all critical MCPs up"
                if not down
                else f"FAILED:liveness {len(down)} critical down: "
                + ",".join(f"{r['name']}={r['state']}" for r in down)
            )
            print(json.dumps(report, indent=2))
            print(marker)
            return 1 if down else 0

        try:
            data = json.loads(sys.stdin.read() or "{}")
        except Exception:
            data = {}
        return run(mode, data)
    except Exception:
        return 0  # fail-open
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
