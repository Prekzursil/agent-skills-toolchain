#!/usr/bin/env python3
"""Live OS-state + endpoint-health measurements for AUD-0066.

Probe 1 is scheduled-task / service / listener state as the OS reports it.
Probe 2 is an HTTP/TCP health check per declared endpoint. A task listed
Running whose endpoint refuses connections is the finding; task state alone
cannot show it.

This Linux worktree has no pwsh/schtasks. That absence is measured, not
filled in from a prior Windows harvest.
"""
from __future__ import annotations

import json
import platform
import shutil
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "AUD-0066"
OUT_REL = "command-center/audit/AUD-0066-scheduled-service-dependency.json"
DECLARED_SCHEMA = "command-center/schema/audit-inventory.schema.json"
LOCAL_SCHEMA = "command-center/p2-wave/probes/AUD-0066/artifact.schema.json"
SENTINEL = (
    "SUCCESS:AUD-0066 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "Which Windows scheduled tasks and background services must be running "
    "for this program's rails to work, what is each one's current state, "
    "and what is the observed recovery behaviour when one dies?"
)

DECLARED: list[dict[str, Any]] = [
    {
        "id": "MCPAgentMailSupervisor",
        "kind": "windows-logon-scheduled-task",
        "role": "logon supervisor; health-poll of agent-mail MCP",
        "required": True,
        "endpoints": [
            {"host": "127.0.0.1", "port": 18812, "method": "GET", "path": "/api/health"},  # shard2-w1 2026-10-24: estate moved agent-mail 8812->18812; live-verified
            {"host": "127.0.0.1", "port": 18812, "method": "POST", "path": "/mcp"},
        ],
    },
    {
        "id": "BasicMemory-HTTP-MCP",
        "kind": "windows-scheduled-task",
        "role": "HTTP MCP memory service",
        "required": True,
        "endpoints": [
            {"host": "127.0.0.1", "port": 18765, "method": "POST", "path": "/mcp"},  # shard2-w1 2026-10-24: estate moved basic-memory 8765->18765; live-verified
            {"host": "127.0.0.1", "port": 18765, "method": "GET", "path": "/mcp"},
        ],
    },
    {
        "id": "BasicMemory-Watchdog",
        "kind": "windows-scheduled-task",
        "role": "restart BasicMemory-HTTP-MCP if it dies",
        "required": True,
        "endpoints": [],
    },
    {
        "id": "ClaudeScienceWatchdog",
        "kind": "windows-scheduled-task",
        "role": "science watchdog daemon",
        "required": True,
        "endpoints": [],
    },
    {
        "id": "ClaudeScienceMaintain",
        "kind": "windows-scheduled-task",
        "role": "periodic science maintain",
        "required": False,
        "endpoints": [],
    },
    {
        "id": "World-Watch",
        "kind": "windows-scheduled-task",
        "role": "monitor daemon",
        "required": True,
        "endpoints": [],
    },
    {
        "id": "Resource-Guard",
        "kind": "windows-scheduled-task",
        "role": "resource-guard daemon",
        "required": True,
        "endpoints": [],
    },
    {
        "id": "RAM-Keeper",
        "kind": "windows-scheduled-task",
        "role": "memory-guard daemon",
        "required": True,
        "endpoints": [],
    },
    {
        "id": "MCP-Orphan-Reaper",
        "kind": "windows-scheduled-task",
        "role": "orphan MCP reaper",
        "required": False,
        "endpoints": [],
    },
    {
        "id": "RecallIndexRebuild",
        "kind": "windows-scheduled-task",
        "role": "recall index rebuild",
        "required": False,
        "endpoints": [],
    },
    {
        "id": "unattributed-port-8000",
        "kind": "tcp-service",
        "role": "legacy HTTP listener named in a prior harvest (port 8000)",
        "required": False,
        "endpoints": [
            {"host": "127.0.0.1", "port": 8000, "method": "GET", "path": "/"}
        ],
    },
]

WRONG_PORT = 59999
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0066/probe1_os_state.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0066/probe2_endpoint_health.py"
)


def run(cmd: list[str], timeout: float = 8.0) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(REPO),
        )
        text = ((proc.stdout or "") + (proc.stderr or "")).strip()
        return {
            "command": cmd,
            "exit_code": proc.returncode,
            "output": text[:8000],
            "error": None,
        }
    except FileNotFoundError as exc:
        return {
            "command": cmd,
            "exit_code": 127,
            "output": "",
            "error": f"FileNotFoundError:{exc}",
        }
    except subprocess.TimeoutExpired:
        return {
            "command": cmd,
            "exit_code": 124,
            "output": "",
            "error": f"TIMEOUT:{timeout}",
        }


def tcp_open(host: str, port: int, timeout: float = 0.6) -> dict[str, Any]:
    sock = socket.socket()
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        return {"tcp": True, "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"tcp": False, "error": f"{type(exc).__name__}:{exc}"}
    finally:
        sock.close()


def http_call(
    host: str, port: int, method: str, path: str, timeout: float = 1.2
) -> dict[str, Any]:
    tcp = tcp_open(host, port, timeout=min(timeout, 0.6))
    url = f"http://{host}:{port}{path}"
    row: dict[str, Any] = {
        "host": host,
        "port": port,
        "method": method,
        "path": path,
        "url": url,
        "tcp": bool(tcp["tcp"]),
        "http_status": None,
        "detail": tcp.get("error") or "tcp-ok",
        "up": False,
    }
    if not tcp["tcp"]:
        return row
    data = b"{}" if method.upper() == "POST" else None
    req = urllib.request.Request(url, data=data, method=method.upper())
    if data is not None:
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json, text/event-stream, */*")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(120)
            row["http_status"] = int(resp.status)
            row["detail"] = f"HTTP {resp.status} body={body[:60]!r}"
            row["up"] = True
    except urllib.error.HTTPError as exc:
        row["http_status"] = int(exc.code)
        row["detail"] = f"HTTP {exc.code}"
        row["up"] = True
    except Exception as exc:  # noqa: BLE001
        row["detail"] = f"{type(exc).__name__}:{exc}"
        row["up"] = bool(tcp["tcp"])
    return row


class _H(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        body = b'{"ok":true,"control":"AUD-0066-scratch"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        self.send_response(400)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"error":"scratch-mcp"}')


def scratch_control() -> dict[str, Any]:
    server = HTTPServer(("127.0.0.1", 0), _H)
    port = int(server.server_address[1])
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.05)
    try:
        got = http_call("127.0.0.1", port, "GET", "/api/health")
        return {
            "port": port,
            "up": bool(got.get("up")),
            "http_status": got.get("http_status"),
            "detail": got.get("detail"),
            "passed": bool(got.get("up") and got.get("http_status") == 200),
        }
    finally:
        server.shutdown()
        server.server_close()


def windows_tools() -> dict[str, Any]:
    names = ["pwsh", "powershell", "powershell.exe", "schtasks", "schtasks.exe"]
    found = {n: shutil.which(n) for n in names}
    return {
        "available": any(found.values()),
        "which": found,
        "platform": platform.system(),
    }


def linux_state() -> dict[str, Any]:
    ss = run(["ss", "-lnt"])
    systemctl = run(
        [
            "systemctl",
            "list-units",
            "--type=service",
            "--all",
            "--no-pager",
            "--no-legend",
        ]
    )
    timers = run(["systemctl", "list-timers", "--all", "--no-pager"])
    keys = (
        "mcp",
        "agent-mail",
        "agentmail",
        "basic-memory",
        "basicmemory",
        "watchdog",
        "ram-keeper",
        "memguard",
        "science",
        "orphan",
    )
    svc_lines = [
        ln
        for ln in (systemctl.get("output") or "").splitlines()
        if any(k in ln.lower() for k in keys)
    ]
    listen_ports: list[int] = []
    for ln in (ss.get("output") or "").splitlines():
        if "LISTEN" not in ln:
            continue
        parts = ln.split()
        if len(parts) < 4:
            continue
        local = parts[3]
        if ":" in local:
            try:
                listen_ports.append(int(local.rsplit(":", 1)[-1]))
            except ValueError:
                pass
    return {
        "ss_exit": ss.get("exit_code"),
        "ss_output": ss.get("output"),
        "listen_ports": sorted(set(listen_ports)),
        "matching_systemd_units": svc_lines,
        "timers_head": (timers.get("output") or "")[:1500],
        "cron_program_relevant": False,
    }


def windows_tasks() -> dict[str, Any]:
    tools = windows_tools()
    if not tools["available"]:
        return {
            "attempted": True,
            "available": False,
            "reason": "pwsh/powershell/schtasks absent on this Linux host",
            "tasks": [],
            "raw": "",
        }
    ps = (
        "Get-ScheduledTask | Where-Object { $_.TaskName -match "
        "'MCP|Memory|Watch|Guard|Keeper|Science|Reaper|Watch|Recall' } | "
        "ForEach-Object { '{0}`t{1}`t{2}' -f $_.TaskPath, $_.TaskName, "
        "$_.State }"
    )
    exe = (
        tools["which"].get("pwsh")
        or tools["which"].get("powershell")
        or tools["which"].get("powershell.exe")
    )
    if not exe:
        return {
            "attempted": True,
            "available": False,
            "reason": "pwsh/powershell absent (schtasks-only which() hit)",
            "tasks": [],
            "raw": "",
        }
    got = run([exe, "-NoProfile", "-Command", ps], timeout=20)
    return {
        "attempted": True,
        "available": True,
        "exit_code": got["exit_code"],
        "raw": got["output"],
        "tasks": [],
    }


def probe_os() -> dict[str, Any]:
    win = windows_tasks()
    linux = linux_state()
    tools = windows_tools()
    rows = []
    for decl in DECLARED:
        name = decl["id"]
        linux_unit = [
            u for u in linux["matching_systemd_units"] if name.lower() in u.lower()
        ]
        rows.append(
            {
                "id": name,
                "kind": decl["kind"],
                "role": decl["role"],
                "required": decl["required"],
                "windows_task_state": "UNAVAILABLE"
                if not win["available"]
                else "NOT-MATCHED",
                "linux_systemd_match": linux_unit,
                "linux_present": bool(linux_unit),
            }
        )
    return {
        "platform": platform.platform(),
        "system": platform.system(),
        "windows_tools": tools,
        "windows_tasks": win,
        "linux": {
            "listen_ports": linux["listen_ports"],
            "matching_systemd_units": linux["matching_systemd_units"],
            "ss_exit": linux["ss_exit"],
            "ss_output": linux["ss_output"],
        },
        "declared_rows": rows,
        "n_declared": len(rows),
        "n_windows_queryable": 0
        if not win["available"]
        else len(win.get("tasks") or []),
        "n_linux_matching_units": len(linux["matching_systemd_units"]),
    }


def probe_health() -> dict[str, Any]:
    live = []
    for decl in DECLARED:
        for ep in decl["endpoints"]:
            got = http_call(ep["host"], ep["port"], ep["method"], ep["path"])
            got["service_id"] = decl["id"]
            live.append(got)
    wrong = http_call("127.0.0.1", WRONG_PORT, "GET", "/api/health")
    scratch = scratch_control()
    n_up = sum(1 for r in live if r.get("up"))
    n_down = sum(1 for r in live if not r.get("up"))
    control_pass = (not wrong.get("up")) and bool(scratch.get("passed"))
    return {
        "live": live,
        "n_live_up": n_up,
        "n_live_down": n_down,
        "wrong_port": {"port": WRONG_PORT, **wrong},
        "wrong_port_failed": not bool(wrong.get("up")),
        "scratch_good": scratch,
        "scratch_good_passed": bool(scratch.get("passed")),
        "control_pass": control_pass,
        "finding": (
            "every declared live endpoint refused TCP on this host"
            if n_up == 0
            else f"{n_up} endpoint(s) up, {n_down} down"
        ),
    }


def measure() -> dict[str, Any]:
    return {"os": probe_os(), "health": probe_health()}


def text_p1(os_state: dict[str, Any]) -> str:
    lines = [
        f"platform={os_state['platform']}",
        f"system={os_state['system']}",
        f"windows_tools_available={os_state['windows_tools']['available']}",
        "windows_query="
        + str(
            os_state["windows_tasks"].get("reason")
            or os_state["windows_tasks"].get("available")
        ),
        f"linux_listen_ports={os_state['linux']['listen_ports']}",
        f"linux_matching_systemd={os_state['linux']['matching_systemd_units']}",
        f"n_declared={os_state['n_declared']}",
        f"n_linux_matching_units={os_state['n_linux_matching_units']}",
    ]
    for row in os_state["declared_rows"]:
        lines.append(
            f"TASK\t{row['id']}\t{row['windows_task_state']}\t"
            f"linux_present={row['linux_present']}"
        )
    lines.append("SUCCESS:AUD-0066-probe1 OS scheduled-task/service state")
    return "\n".join(lines)


def text_p2(health: dict[str, Any]) -> str:
    lines = [
        f"wrong_port={WRONG_PORT} failed={health['wrong_port_failed']} "
        f"detail={health['wrong_port'].get('detail')}",
        f"scratch_good_passed={health['scratch_good_passed']} "
        f"port={health['scratch_good'].get('port')} "
        f"status={health['scratch_good'].get('http_status')}",
        f"control_pass={health['control_pass']}",
        f"n_live_up={health['n_live_up']} n_live_down={health['n_live_down']}",
        f"finding={health['finding']}",
    ]
    for row in health["live"]:
        lines.append(
            f"EP\t{row['service_id']}\t{row['method']}\t{row['url']}\t"
            f"tcp={row['tcp']}\tstatus={row['http_status']}\tup={row['up']}\t"
            f"{row['detail']}"
        )
    lines.append("SUCCESS:AUD-0066-probe2 endpoint health + wrong-port control")
    return "\n".join(lines)


def dump(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def load_artifact() -> tuple[str, dict[str, Any]]:
    path = REPO / OUT_REL
    if not path.is_file() or path.stat().st_size <= 0:
        raise FileNotFoundError(OUT_REL)
    text = path.read_text(encoding="utf-8")
    return text, json.loads(text)
