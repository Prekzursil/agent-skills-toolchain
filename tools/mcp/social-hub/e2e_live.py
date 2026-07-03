#!/usr/bin/env python3
"""Live end-to-end check: route a REAL tool call through the hub subprocess.

Spawns ``python hub.py`` exactly as a client would, serves initialize +
tools/list from cache (asserting NO backend spawns for listing), then calls the
keyless ``tiktok_trending`` tool and measures the tiktok backend process count
before/after to prove lazy-spawn + routing + response passthrough.

Windows-only (uses PowerShell/CIM to count backend processes by command line).
Run directly: ``python e2e_live.py``.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

HUB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hub.py")
MATCH = "*tiktok-mcp*server.py*"


def count_backend(match: str = MATCH) -> int:
    """Count live backend processes whose command line matches (via CIM)."""
    cmd = (
        "(Get-CimInstance Win32_Process | Where-Object "
        f"{{ $_.CommandLine -like '{match}' }} | Measure-Object).Count")
    ps = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                        capture_output=True, text=True)
    try:
        return int((ps.stdout or "0").strip() or "0")
    except ValueError:
        return -1


def _send(proc: subprocess.Popen, obj: dict) -> None:
    proc.stdin.write(json.dumps(obj) + "\n")
    proc.stdin.flush()


def _read_until(proc: subprocess.Popen, want_id, timeout: float) -> dict | None:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        line = proc.stdout.readline()
        if not line:
            return None
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("id") == want_id:
            return msg
    return None


def _kill_lingering(match: str = MATCH) -> None:
    cmd = ("Get-CimInstance Win32_Process | Where-Object "
           f"{{ $_.CommandLine -like '{match}' }} | ForEach-Object "
           "{ Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }")
    subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                   capture_output=True, text=True)


def main() -> int:
    before = count_backend()
    proc = subprocess.Popen(
        [sys.executable, HUB], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True, bufsize=1, encoding="utf-8",
        errors="replace")
    result: dict = {}
    try:
        _send(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                     "params": {"protocolVersion": "2024-11-05",
                                "capabilities": {},
                                "clientInfo": {"name": "e2e", "version": "1"}}})
        init = _read_until(proc, 1, 10)
        _send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        _send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list",
                     "params": {}})
        listing = _read_until(proc, 2, 10)
        n_tools = len(listing["result"]["tools"]) if listing else -1
        idle = count_backend()  # after listing: must NOT have spawned tiktok

        _send(proc, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                     "params": {"name": "tiktok_trending",
                                "arguments": {"count": 1}}})
        time.sleep(4)  # let the lazy spawn happen before we sample
        spawned = count_backend()
        resp = _read_until(proc, 3, 150)

        content = None
        if resp and resp.get("result", {}).get("content"):
            content = resp["result"]["content"][0].get("text", "")[:400]
        elif resp and resp.get("error"):
            content = resp["error"]
        result = {
            "hub_server_name": init and init["result"]["serverInfo"]["name"],
            "tools_listed": n_tools,
            "tiktok_procs_before_hub": before,
            "tiktok_procs_after_list": idle,
            "tiktok_procs_after_call": spawned,
            "lazy_spawn_on_list": idle - before,   # expect 0
            "lazy_spawn_on_call": spawned - idle,  # expect >= 1
            "got_response": resp is not None,
            "response_is_error": bool(resp and resp.get("result", {}).get("isError")),
            "response_preview": content,
        }
    finally:
        try:
            proc.terminate()
        except OSError:
            pass
        _kill_lingering()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    ok = (result.get("tools_listed") == 60
          and result.get("lazy_spawn_on_list") == 0
          and result.get("got_response") is True)
    print("E2E:", "PASS" if ok else "CHECK", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
