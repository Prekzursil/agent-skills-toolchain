#!/usr/bin/env python3
"""
Local launcher and stdio bridge for HexStrike MCP.

HexStrike's upstream `hexstrike_mcp.py` currently speaks line-delimited JSON-RPC
over stdio. Codex, Claude, and Gemini expect Content-Length framed MCP stdio.

This wrapper:
1. Ensures the localhost-only HexStrike HTTP server is healthy.
2. Starts the upstream MCP adapter as a child process.
3. Translates modern framed MCP stdio <-> upstream line-delimited JSON-RPC.
"""

from __future__ import annotations

import json
import os
import requests
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_HOST = os.environ.get("HEXSTRIKE_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.environ.get("HEXSTRIKE_PORT", "8888"))
DEFAULT_START_TIMEOUT = int(os.environ.get("HEXSTRIKE_START_TIMEOUT", "180"))
DEFAULT_POLL_INTERVAL = float(os.environ.get("HEXSTRIKE_POLL_INTERVAL", "1.0"))


def install_root() -> Path:
    return Path(__file__).resolve().parent


def log_path() -> Path:
    path = install_root() / "logs" / "launcher.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def write_log(message: str) -> None:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with log_path().open("a", encoding="utf-8") as handle:
        handle.write(f"{timestamp} {message}\n")


def server_url(host: str, port: int) -> str:
    return f"http://{host}:{port}"


def health_url(host: str, port: int) -> str:
    return f"{server_url(host, port)}/health"


def port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.0)
        return sock.connect_ex((host, port)) == 0


def healthy(host: str, port: int) -> bool:
    try:
        with urllib.request.urlopen(health_url(host, port), timeout=60) as response:
            body = response.read().decode("utf-8", errors="replace")
        payload = json.loads(body)
        return payload.get("status") == "healthy"
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return False


def spawn_server(host: str, port: int) -> None:
    root = install_root()
    python_exe = root / ".venv" / "Scripts" / "python.exe"
    server_script = root / "hexstrike_server.py"
    logs_dir = root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    stdout_handle = (logs_dir / "server.stdout.log").open("ab")
    stderr_handle = (logs_dir / "server.stderr.log").open("ab")

    env = os.environ.copy()
    env["HEXSTRIKE_HOST"] = host
    env["HEXSTRIKE_PORT"] = str(port)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    kwargs: dict[str, object] = {
        "cwd": str(root),
        "env": env,
        "stdin": subprocess.DEVNULL,
        "stdout": stdout_handle,
        "stderr": stderr_handle,
        "close_fds": True,
    }

    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

    subprocess.Popen([str(python_exe), str(server_script)], **kwargs)
    write_log(f"spawned server {host}:{port}")


def ensure_server(host: str, port: int) -> None:
    if port_open(host, port):
        write_log(f"server already listening at {host}:{port}")
        return

    spawn_server(host, port)

    deadline = time.time() + DEFAULT_START_TIMEOUT
    while time.time() < deadline:
        if port_open(host, port):
            write_log(f"server now listening at {host}:{port}")
            return
        time.sleep(DEFAULT_POLL_INTERVAL)

    raise RuntimeError(
        f"HexStrike server did not start listening at {host}:{port} within {DEFAULT_START_TIMEOUT}s"
    )


def read_framed_message() -> dict[str, object] | None:
    header = b""
    while b"\r\n\r\n" not in header:
        chunk = sys.stdin.buffer.read(1)
        if not chunk:
            return None
        header += chunk

    raw_headers, _ = header.split(b"\r\n\r\n", 1)
    content_length = None
    for line in raw_headers.decode("ascii", errors="replace").split("\r\n"):
        if line.lower().startswith("content-length:"):
            content_length = int(line.split(":", 1)[1].strip())
            break
    if content_length is None:
        raise RuntimeError("missing Content-Length header")

    body = sys.stdin.buffer.read(content_length)
    return json.loads(body.decode("utf-8"))


def write_framed_message(payload: dict[str, object]) -> None:
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(data)}\r\n\r\n".encode("ascii"))
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def relay_child_stdout(child: subprocess.Popen[str]) -> None:
    assert child.stdout is not None
    for line in child.stdout:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            write_log(f"non-json child stdout: {stripped[:200]}")
            continue
        write_framed_message(payload)


def relay_child_stderr(child: subprocess.Popen[str]) -> None:
    assert child.stderr is not None
    for line in child.stderr:
        sys.stderr.write(line)
        sys.stderr.flush()


def main() -> int:
    host = DEFAULT_HOST
    port = DEFAULT_PORT
    root = install_root()
    python_exe = root / ".venv" / "Scripts" / "python.exe"
    mcp_script = root / "hexstrike_mcp.py"

    ensure_server(host, port)

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    child = subprocess.Popen(
        [str(python_exe), str(mcp_script), "--server", server_url(host, port), *sys.argv[1:]],
        cwd=str(root),
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    write_log(f"launching bridged mcp client against {server_url(host, port)}")

    stdout_thread = threading.Thread(target=relay_child_stdout, args=(child,), daemon=True)
    stderr_thread = threading.Thread(target=relay_child_stderr, args=(child,), daemon=True)
    stdout_thread.start()
    stderr_thread.start()

    try:
        while True:
            message = read_framed_message()
            if message is None:
                break
            if child.stdin is None:
                raise RuntimeError("child stdin unavailable")
            child.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
            child.stdin.flush()
    finally:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - defensive launcher path
        write_log(f"launcher failure: {exc}")
        raise
