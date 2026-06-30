#!/usr/bin/env python3
r"""RE-BACKEND ON-DEMAND AUTO-LAUNCHER -- so the RE MCPs "just work" without ever
manually opening/navigating IDA / Ghidra / Binary Ninja.

THE problem this solves: ``mcp__ida-pro-mcp``, ``mcp__ghidra-mcp`` and
``mcp__binary-ninja-mcp`` are BRIDGE proxies. The bridge process is connected, but
every call forwards over a local socket to a plugin INSIDE the GUI app:
    ida-pro-mcp        -> IDA GUI :13337 (preferred)  OR  headless idalib :8745
    ghidra-mcp         -> GhidraMCP headless server   :8089
    binary-ninja-mcp   -> Binary Ninja GUI plugin     :9009  (no headless)
If the backend app/server is not running the bridge connects to nothing and the
call fails ("not reachable" / "connection refused" / list_instances -> []).

This PreToolUse hook fires ONLY when one of those MCP tools is invoked. It:
  * probes the backend port(s);
  * if UP (incl. the live GUI IDA on :13337) -> fast SILENT no-op;
  * if DOWN and launchable -> cold-starts ONLY that backend via the re-harness
    (re_launch.py, DETACHED so this hook never blocks), briefly waits for the
    port, and tells the agent to retry (cold-start analysis can take 1-3 min);
  * if DOWN and NOT launchable (Binary Ninja Personal-license) -> reports the
    manual step (no spawn).

RAM-CONSCIOUS (the user just hit an OOM): launch is ON-DEMAND only (never at
session start), SINGLE-backend (never the whole stack), IDEMPOTENT (re_launch
probes-if-up first), PREFERS an already-running GUI/headless instance (never
duplicates the heavy process), and is REFUSED when free RAM < min_free_ram_mb.

DESIGN CONTRACT (AGENTS.md s6): FAIL-OPEN. main() wraps everything; ANY error ->
exit 0, emit nothing, let the tool proceed. A *broken* hook never blocks a call.
A deliberate deny on a confirmed-down backend (deny_while_starting /
deny_when_unlaunchable, both config-toggleable) is a controlled decision, not an
error -- it replaces a guaranteed "connection refused" with an actionable retry
message. Flip either to false for pure inject-only (never-deny) behavior.

Opt-out entirely: RE_AUTOLAUNCH=off  or a ``.disabled`` file beside this script.

Usage:
  python autolaunch.py pretool       # PreToolUse(mcp__(ida-pro|ghidra|binary-ninja)-mcp__.*)
  python autolaunch.py probe         # CLI: status JSON + SUCCESS/FAILED marker (no launch)
  python autolaunch.py ensure <ida|ghidra|bn|all>   # explicit on-demand bring-up (re-ensure skill)
"""

from __future__ import annotations

import ctypes
import json
import os
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

THIS = Path(__file__).resolve().parent
CONFIG_PATH = THIS / "backends.json"
DISABLED = THIS / ".disabled"
SPAWN_LOG_DIR = THIS / "state"

# Per-session state (throttle + launch dedup). Overridable for tests.
STATE_DIR = Path(
    os.environ.get(
        "RE_AUTOLAUNCH_STATE_DIR",
        str(Path(os.environ.get("TEMP", "/tmp")) / "re-autolaunch"),
    )
)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
def load_config() -> dict:
    try:
        with CONFIG_PATH.open("r", encoding="utf-8", errors="replace") as fh:
            return json.load(fh)
    except Exception:
        # Minimal hard-coded fallback so the mechanism still works if JSON is gone.
        return {
            "re_launch": "C:/Users/Prekzursil/.local/opt/re-harness/re_launch.py",
            "launcher_python": None,
            "tcp_timeout": 1.2,
            "brief_wait_seconds": 6.0,
            "brief_poll_interval": 0.5,
            "up_recheck_seconds": 30,
            "launch_throttle_seconds": 90,
            "min_free_ram_mb": 2048,
            "deny_while_starting": True,
            "deny_when_unlaunchable": True,
            "backends": {
                "ida-pro-mcp": {
                    "tool": "ida",
                    "launchable": True,
                    "ports": [13337, 8745],
                    "prefer_ports": [13337],
                    "headless_port": 8745,
                    "binary": None,
                    "why": "IDA (GUI :13337 preferred; headless :8745)",
                },
                "ghidra-mcp": {
                    "tool": "ghidra",
                    "launchable": True,
                    "ports": [8089],
                    "headless_port": 8089,
                    "binary": None,
                    "why": "GhidraMCP headless :8089",
                },
                "binary-ninja-mcp": {
                    "tool": "bn",
                    "launchable": False,
                    "ports": [9009],
                    "manual_hint": "Open Binary Ninja GUI + start the MCP plugin on :9009.",
                    "why": "Binary Ninja GUI plugin :9009 (no headless)",
                },
            },
        }


# ---------------------------------------------------------------------------
# Pure helpers (the TDD targets)
# ---------------------------------------------------------------------------
def backend_for_tool(tool_name: str, cfg: dict):
    """Map an MCP tool name -> (backend_key, spec). 'mcp__ghidra-mcp__list_methods'
    -> ('ghidra-mcp', {...}). Returns (None, None) when not a handled RE tool."""
    if not tool_name or not tool_name.startswith("mcp__"):
        return None, None
    parts = tool_name.split("__")
    if len(parts) < 2:
        return None, None
    key = parts[1]
    spec = (cfg.get("backends") or {}).get(key)
    return (key, spec) if spec else (None, None)


def tcp_up(host: str, port: int, timeout: float) -> bool:
    """True iff a TCP connect to host:port is accepted within `timeout`."""
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except Exception:
        return False


def probe_ports(ports, timeout: float, host: str = "127.0.0.1") -> list:
    """Return the subset of `ports` that are currently listening (in input order)."""
    out = []
    for p in ports or []:
        try:
            if tcp_up(host, int(p), timeout):
                out.append(int(p))
        except Exception:
            continue
    return out


def prefer_port(spec: dict, up_ports: list) -> Optional[int]:
    """Pick which up-port to report, preferring 'prefer_ports' (e.g. GUI IDA 13337)."""
    for p in spec.get("prefer_ports") or []:
        if int(p) in up_ports:
            return int(p)
    return up_ports[0] if up_ports else None


def wait_port(spec: dict) -> Optional[int]:
    """The port the cold-started backend will bind (the one to brief-poll)."""
    hp = spec.get("headless_port")
    if hp:
        return int(hp)
    ports = spec.get("ports") or []
    return int(ports[-1]) if ports else None


def free_ram_mb() -> Optional[int]:
    """Free physical RAM in MB (Windows, via GlobalMemoryStatusEx). None if unknown
    -> callers treat None as 'enough' (fail-open, never blocks a launch on doubt)."""
    if os.name != "nt":
        try:
            with open("/proc/meminfo", encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("MemAvailable:"):
                        return int(line.split()[1]) // 1024
        except Exception:
            return None
        return None
    try:

        class _MEMSTAT(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        st = _MEMSTAT()
        st.dwLength = ctypes.sizeof(_MEMSTAT)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)) == 0:
            return None
        return int(st.ullAvailPhys // (1024 * 1024))
    except Exception:
        return None


@dataclass(frozen=True)
class Decision:
    action: str  # noop | launch | wait | manual | lowram
    backend: str
    tool: str
    up_port: Optional[int]
    wait_port: Optional[int]
    reason: str


def decide(
    key: str,
    spec: dict,
    up_ports: list,
    *,
    started_recently: bool,
    free_mb: Optional[int],
    min_free_mb: int,
) -> Decision:
    """Pure decision logic (no I/O). The heart of the hook -- exhaustively tested.

    Priority: already-up (no-op, prefer GUI) > not-launchable (manual) > low-RAM
    (refuse) > launch-in-flight (wait) > cold-start (launch)."""
    tool = str(spec.get("tool") or "")
    if up_ports:
        return Decision(
            "noop",
            key,
            tool,
            prefer_port(spec, up_ports),
            None,
            f"backend already up on :{prefer_port(spec, up_ports)}",
        )
    # Not auto-launchable in the PreToolUse path: either truly unlaunchable, OR
    # launchable-but-auto_launch-disabled. The latter (Binary Ninja) is a heavy GUI
    # window we deliberately do NOT auto-pop on every stray tool call -- it is
    # brought up EXPLICITLY via cmd_ensure (`re-ensure bn`), which checks only
    # `launchable`. Both surface the manual_hint here. `auto_launch` defaults True
    # so IDA/Ghidra (which omit it) keep their existing auto-launch behavior.
    if not spec.get("launchable", False) or not spec.get("auto_launch", True):
        return Decision(
            "manual",
            key,
            tool,
            None,
            None,
            spec.get("manual_hint", "backend down; manual start required"),
        )
    if min_free_mb and free_mb is not None and free_mb < min_free_mb:
        return Decision(
            "lowram",
            key,
            tool,
            None,
            wait_port(spec),
            f"free RAM {free_mb}MB < {min_free_mb}MB threshold",
        )
    if started_recently:
        return Decision(
            "wait",
            key,
            tool,
            None,
            wait_port(spec),
            "a cold-start was launched recently; still coming up",
        )
    return Decision(
        "launch",
        key,
        tool,
        None,
        wait_port(spec),
        "backend down; cold-starting headless",
    )


def build_launch_cmd(cfg: dict, spec: dict) -> list:
    """Pure: build the detached re_launch.py argv for a backend. Testable."""
    py = cfg.get("launcher_python") or sys.executable
    rl = cfg.get("re_launch")
    cmd = [str(py), str(rl), str(spec["tool"])]
    if spec.get("binary"):
        cmd.append(str(spec["binary"]))
    return cmd


# ---------------------------------------------------------------------------
# Side-effecting helpers (kept thin so tests can monkeypatch them)
# ---------------------------------------------------------------------------
def spawn_launch(cfg: dict, spec: dict) -> bool:
    """Launch re_launch.py DETACHED (fire-and-forget). re_launch spawns the heavy
    server detached + polls it ready + registers it, all in the background, so this
    hook returns immediately. Returns True if the launcher process was started."""
    rl = cfg.get("re_launch")
    if not rl or not Path(rl).exists():
        return False
    cmd = build_launch_cmd(cfg, spec)
    log_handle = None
    try:
        SPAWN_LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_path = SPAWN_LOG_DIR / f"{spec.get('tool', 'tool')}-spawn.log"
        log_handle = open(log_path, "ab", buffering=0)  # noqa: SIM115 - spans child
        flags = 0
        if os.name == "nt":
            # CREATE_NEW_PROCESS_GROUP keeps the launcher alive after this short
            # hook exits; CREATE_NO_WINDOW hides the console flash. (Deliberately
            # NOT DETACHED_PROCESS -- harmless for python but unnecessary here.)
            flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200) | getattr(
                subprocess, "CREATE_NO_WINDOW", 0x08000000
            )
        subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=log_handle,
            close_fds=True,
            creationflags=flags,
            cwd=str(Path(rl).resolve().parent),
        )
        return True
    except Exception:
        return False
    finally:
        if log_handle is not None:
            try:
                log_handle.close()
            except Exception:
                pass


def brief_wait(
    port: Optional[int], seconds: float, interval: float, timeout: float
) -> bool:
    """Poll `port` for up to `seconds`; True as soon as it listens. Bounded well
    under the hook timeout so the hook never blocks for the multi-minute analysis."""
    if not port:
        return False
    deadline = time.monotonic() + max(0.0, seconds)
    while True:
        if tcp_up("127.0.0.1", int(port), timeout):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(max(0.05, interval))


# ---------------------------------------------------------------------------
# Per-session state (throttle + dedup)
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
        return {}


def save_state(sid: str, st: dict) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        _state_file(sid).write_text(json.dumps(st), encoding="utf-8")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
def emit_context(msg: str, event: str = "PreToolUse") -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": event,
                    "additionalContext": "[re-autolaunch] " + msg,
                }
            }
        )
    )


def emit_deny(msg: str, event: str = "PreToolUse") -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": event,
                    "permissionDecision": "deny",
                    "permissionDecisionReason": "[re-autolaunch] " + msg,
                }
            }
        )
    )


def _disposition(deny: bool, msg: str) -> None:
    (emit_deny if deny else emit_context)(msg)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def run(mode: str, data: dict) -> int:
    cfg = load_config()
    tool_name = str(data.get("tool_name") or "")
    key, spec = backend_for_tool(tool_name, cfg)
    if not spec:
        return 0  # not a handled RE tool -> silent no-op

    sid = str(data.get("session_id") or "default")
    now = time.time()
    st = load_state(sid)
    bstate = dict(st.get(key) or {})

    tcp_t = float(cfg.get("tcp_timeout", 1.2))
    up_recheck = float(cfg.get("up_recheck_seconds", 30))

    # Fast-path: if we very recently confirmed THIS backend up, skip the probe.
    if (
        mode == "pretool"
        and bstate.get("last_state") == "up"
        and now - float(bstate.get("last_check", 0)) < up_recheck
    ):
        return 0

    up_ports = probe_ports(spec.get("ports") or [], tcp_t)
    launch_throttle = float(cfg.get("launch_throttle_seconds", 90))
    started_recently = (now - float(bstate.get("last_launch", 0))) < launch_throttle
    min_free = int(cfg.get("min_free_ram_mb", 0) or 0)
    free_mb = free_ram_mb() if (not up_ports and spec.get("launchable")) else None

    d = decide(
        key,
        spec,
        up_ports,
        started_recently=started_recently,
        free_mb=free_mb,
        min_free_mb=min_free,
    )

    deny_starting = bool(cfg.get("deny_while_starting", True))
    deny_unlaunch = bool(cfg.get("deny_when_unlaunchable", True))

    if d.action == "noop":
        bstate.update(last_state="up", last_check=now)
        st[key] = bstate
        save_state(sid, st)
        return 0  # healthy -> silent fast no-op

    if d.action == "launch":
        launched = spawn_launch(cfg, spec)
        bstate["last_launch"] = now
        came_up = brief_wait(
            d.wait_port,
            float(cfg.get("brief_wait_seconds", 6.0)),
            float(cfg.get("brief_poll_interval", 0.5)),
            tcp_t,
        )
        bstate.update(last_state="up" if came_up else "starting", last_check=now)
        st[key] = bstate
        save_state(sid, st)
        if came_up:
            emit_context(
                f"{key}: backend was down; brought it up on :{d.wait_port}. Proceeding."
            )
        elif not launched:
            _disposition(
                deny_unlaunch,
                f"{key}: backend down and the re-harness launcher could not "
                f"be started (check {cfg.get('re_launch')}). Start it manually: "
                f"python re_launch.py {d.tool}",
            )
        else:
            _disposition(
                deny_starting,
                f"{key}: backend was DOWN -- started headless cold-start on "
                f":{d.wait_port} in the background. Cold-start + analysis can "
                f"take ~1-3 min; retry this call shortly. Log: "
                f"{SPAWN_LOG_DIR / (d.tool + '-spawn.log')} and "
                f"re-harness state/{d.tool}.log",
            )
        return 0

    if d.action == "wait":
        # A launch is already in flight; re-poll once in case it just came up.
        if probe_ports([d.wait_port] if d.wait_port else [], tcp_t):
            bstate.update(last_state="up", last_check=now)
            st[key] = bstate
            save_state(sid, st)
            return 0  # came up -> silent allow
        bstate.update(last_state="starting", last_check=now)
        st[key] = bstate
        save_state(sid, st)
        _disposition(
            deny_starting,
            f"{key}: a cold-start launched moments ago is still coming up on "
            f":{d.wait_port}. Retry shortly (analysis can take 1-3 min).",
        )
        return 0

    if d.action == "lowram":
        bstate.update(last_state="down", last_check=now)
        st[key] = bstate
        save_state(sid, st)
        _disposition(
            deny_starting,
            f"{key}: backend down but {d.reason} -- NOT auto-launching to avoid "
            f"an OOM (IDA/Ghidra are heavy). Free some RAM, then launch manually: "
            f"python re_launch.py {d.tool}  (or lower min_free_ram_mb).",
        )
        return 0

    if d.action == "manual":
        already = bool(bstate.get("alerted_manual"))
        bstate.update(last_state="down", last_check=now, alerted_manual=True)
        st[key] = bstate
        save_state(sid, st)
        # Deny every time it's down (the call cannot succeed) but only attach the
        # full hint once per session to avoid nagging when deny is off.
        if deny_unlaunch:
            emit_deny(f"{key}: {d.reason}")
        elif not already:
            emit_context(f"{key}: {d.reason}")
        return 0

    return 0


# ---------------------------------------------------------------------------
# CLI modes (skill + testing): probe / ensure
# ---------------------------------------------------------------------------
def cmd_probe(cfg: dict) -> int:
    tcp_t = float(cfg.get("tcp_timeout", 1.2))
    results = []
    down = []
    for key, spec in (cfg.get("backends") or {}).items():
        up = probe_ports(spec.get("ports") or [], tcp_t)
        state = "up" if up else "down"
        results.append(
            {
                "backend": key,
                "tool": spec.get("tool"),
                "ports": spec.get("ports"),
                "up_ports": up,
                "state": state,
                "launchable": spec.get("launchable"),
            }
        )
        if not up:
            down.append(key)
    report = {"free_ram_mb": free_ram_mb(), "backends": results}
    marker = (
        "SUCCESS:re-autolaunch all backends up"
        if not down
        else f"FAILED:re-autolaunch {len(down)} down: " + ",".join(down)
    )
    print(json.dumps(report, indent=2))
    print(marker)
    return 1 if down else 0


def cmd_ensure(cfg: dict, target: str) -> int:
    """Explicit on-demand bring-up (the re-ensure skill). Kicks DETACHED launches
    for the requested backend(s), brief-waits each port, prints terminal markers.
    'all' brings up every LAUNCHABLE backend (IDA + Ghidra); BN reports its manual
    step. Still single-shot + idempotent; full readiness (analysis) continues in
    the background -- poll `autolaunch.py probe` until SUCCESS."""
    backends = cfg.get("backends") or {}
    if target == "all":
        keys = list(backends.keys())
    else:
        keys = [
            k for k, s in backends.items() if k == target or s.get("tool") == target
        ]
    if not keys:
        print(
            f"FAILED:re-ensure unknown target '{target}' "
            f"(use one of: {', '.join(backends)}, or 'all')"
        )
        return 1
    tcp_t = float(cfg.get("tcp_timeout", 1.2))
    rc = 0
    for key in keys:
        spec = backends[key]
        # Bulk 'all' bring-up must NOT surprise-pop a heavy GUI: skip backends with
        # auto_launch disabled (e.g. the Binary Ninja GUI). They remain available
        # via an EXPLICIT `re-ensure <tool>` (which targets the key/tool directly).
        if target == "all" and spec.get("auto_launch", True) is False:
            print(
                f"SKIP:re-ensure {key} auto_launch off; bring up explicitly: "
                f"re-ensure {spec.get('tool', key)}"
            )
            continue
        up = probe_ports(spec.get("ports") or [], tcp_t)
        if up:
            print(f"SUCCESS:re-ensure {key} already-up on :{prefer_port(spec, up)}")
            continue
        if not spec.get("launchable"):
            print(
                f"MANUAL:re-ensure {key} {spec.get('manual_hint', 'manual start required')}"
            )
            rc = rc or 2
            continue
        launched = spawn_launch(cfg, spec)
        if not launched:
            print(
                f"FAILED:re-ensure {key} could not start launcher {cfg.get('re_launch')}"
            )
            rc = 1
            continue
        wp = wait_port(spec)
        came_up = brief_wait(
            wp,
            float(cfg.get("brief_wait_seconds", 6.0)),
            float(cfg.get("brief_poll_interval", 0.5)),
            tcp_t,
        )
        if came_up:
            print(
                f"SUCCESS:re-ensure {key} port :{wp} now listening (analysis may continue)"
            )
        else:
            print(
                f"STARTING:re-ensure {key} cold-start launched on :{wp}; "
                f"poll `autolaunch.py probe` until up (analysis can take 1-3 min)"
            )
    return rc


def main(argv) -> int:
    try:
        if DISABLED.exists() or os.environ.get("RE_AUTOLAUNCH", "").lower() in (
            "off",
            "0",
            "false",
        ):
            return 0
        mode = (argv[0] if argv else "pretool").lower()

        if mode == "probe":
            return cmd_probe(load_config())
        if mode == "ensure":
            target = (argv[1] if len(argv) > 1 else "all").lower()
            return cmd_ensure(load_config(), target)

        try:
            data = json.loads(sys.stdin.read() or "{}")
        except Exception:
            data = {}
        if not isinstance(data, dict):
            data = {}
        return run(mode, data)
    except Exception:
        return 0  # FAIL-OPEN: a broken hook must never block a tool call
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
