#!/usr/bin/env python3
"""Live end-to-end check: drive the hub subprocess exactly as a client would.

Serves initialize + tools/list from the committed caches (asserting NO backend
spawns for listing), calls a hub-native account tool (``rp_account_list`` -- no
backend spawn), then calls the local ``modal_app_list`` tool and measures the
modal wrapper process count before/after to prove lazy-spawn + routing +
response passthrough.

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
MATCH = "*cloud-hub*modal-mcp*server.py*"


def count_backend(match: str = MATCH) -> int:
    """Count live backend processes whose command line matches (via CIM)."""
    cmd = ("(Get-CimInstance Win32_Process | Where-Object "
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
        idle = count_backend()  # after listing: must NOT have spawned modal

        # Hub-native account tool: served WITHOUT spawning any backend.
        _send(proc, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                     "params": {"name": "rp_account_list", "arguments": {}}})
        acct = _read_until(proc, 3, 15)
        after_acct = count_backend()

        # Real backend call: lazily spawns ONLY the modal wrapper. Bounded read
        # so the harness can never hang on a slow/absent CLI.
        _send(proc, {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                     "params": {"name": "modal_app_list", "arguments": {}}})
        time.sleep(6)  # let the lazy spawn happen before we sample
        spawned = count_backend()
        resp = _read_until(proc, 4, 30)

        preview = None
        if resp and resp.get("result", {}).get("content"):
            preview = resp["result"]["content"][0].get("text", "")[:200]
        elif resp and resp.get("error"):
            preview = resp["error"]
        result = {
            "hub_server_name": init and init["result"]["serverInfo"]["name"],
            "tools_listed": n_tools,
            "lazy_spawn_on_list": idle - before,        # expect 0
            "account_tool_ok": bool(acct and acct.get("result")),
            "lazy_spawn_on_account_call": after_acct - idle,  # expect 0
            "lazy_spawn_on_modal_call": spawned - after_acct,  # expect >= 1
            "got_modal_response": resp is not None,
            "modal_response_preview": preview,
        }
    finally:
        try:
            proc.terminate()
        except OSError:
            pass
        _kill_lingering()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    # PASS on the deterministic promises (served from cache, account tool is
    # hub-native, neither spawns a backend). The modal lazy-spawn/response is
    # reported as an informational live check (it depends on the modal CLI).
    ok = (result.get("tools_listed") == 227
          and result.get("lazy_spawn_on_list") == 0
          and result.get("account_tool_ok") is True
          and result.get("lazy_spawn_on_account_call") == 0)
    print("E2E:", "PASS" if ok else "CHECK",
          "(modal live:", "spawned+responded)"
          if result.get("got_modal_response") else "unverified)", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
