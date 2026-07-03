#!/usr/bin/env python3
"""rclone-mcp launcher: ensure a local ``rclone rcd`` daemon is up, then run the
``rclone-mcp`` client with stdio passed straight through to the cloud-hub.

``rclone-mcp`` is a *client* of rclone's remote-control (RC) HTTP daemon, so the
daemon must be listening before the client is useful. This launcher is what the
hub spawns as the rclone backend: it starts ``rclone rcd --rc-no-auth`` on the
RC address (derived from ``RCLONE_URL``, default ``http://localhost:5572``) if
that port is down, waits briefly for it, then execs ``npx -y rclone-mcp`` whose
stdin/stdout ARE the hub's MCP pipes (this process only waits).

If ``rclone`` is not installed the daemon cannot start; the client then fails to
connect and the hub surfaces a clear per-tool error -- the hub never crashes.
"""
from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
from urllib.parse import urlparse

# The rclone-mcp client is a node package (a .cmd shim) -> go through cmd /c.
MCP_CMD = ("cmd", "/c", "npx", "-y", "rclone-mcp")
_DEFAULT_URL = "http://localhost:5572"


def _endpoint() -> tuple[str, int]:
    """Parse host:port for the RC daemon from RCLONE_URL (or the default)."""
    url = os.environ.get("RCLONE_URL") or _DEFAULT_URL
    parsed = urlparse(url if "://" in url else f"http://{url}")
    return parsed.hostname or "localhost", parsed.port or 5572


def _port_up(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _ensure_rcd(host: str, port: int) -> None:
    """Start ``rclone rcd`` detached if the RC port is not already listening."""
    if _port_up(host, port):
        return
    rclone = shutil.which("rclone")
    if not rclone:
        return  # not installed: the client will fail to connect; hub degrades
    flags = 0
    if os.name == "nt":  # detach + no console so the daemon outlives this launcher
        flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    try:
        subprocess.Popen(
            [rclone, "rcd", "--rc-no-auth", "--rc-addr", f":{port}"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, creationflags=flags)
    except OSError:
        return
    for _ in range(50):  # up to ~5s for the daemon to bind
        if _port_up(host, port):
            return
        time.sleep(0.1)


def main() -> int:
    host, port = _endpoint()
    _ensure_rcd(host, port)
    # Our stdio (the hub's MCP pipes) is inherited by the client unchanged.
    try:
        client = subprocess.Popen(list(MCP_CMD))
    except OSError as exc:  # npx/node missing: emit nothing, let the hub time out cleanly
        print(f"rclone-mcp launch failed: {exc}", file=sys.stderr)
        return 127
    return client.wait()


if __name__ == "__main__":
    raise SystemExit(main())
