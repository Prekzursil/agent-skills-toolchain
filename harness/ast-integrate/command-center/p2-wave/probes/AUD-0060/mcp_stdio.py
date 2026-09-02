#!/usr/bin/env python3
"""MCP stdio JSON-RPC helper: Content-Length framing, plus a newline-JSON fallback."""
from __future__ import annotations

import json
import os
import select
import subprocess
import time
from typing import Any


def _encode(msg: dict) -> bytes:
    body = json.dumps(msg, separators=(",", ":")).encode("utf-8")
    return f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body


def _read_content_length(buf: bytearray) -> dict | None:
    sep = b"\r\n\r\n"
    alt = b"\n\n"
    idx = buf.find(sep)
    hlen = 4
    if idx < 0:
        idx = buf.find(alt)
        hlen = 2
    if idx < 0:
        return None
    header = buf[:idx].decode("ascii", errors="replace")
    length = None
    for line in header.splitlines():
        if line.lower().startswith("content-length:"):
            try:
                length = int(line.split(":", 1)[1].strip())
            except ValueError:
                return None
    if length is None:
        return None
    start = idx + hlen
    if len(buf) < start + length:
        return None
    body = bytes(buf[start : start + length])
    del buf[: start + length]
    return json.loads(body.decode("utf-8"))


def _read_ndjson(buf: bytearray) -> dict | None:
    nl = buf.find(b"\n")
    if nl < 0:
        return None
    line = bytes(buf[:nl]).strip()
    del buf[: nl + 1]
    if not line or not line.startswith(b"{"):
        return None
    return json.loads(line.decode("utf-8"))


def _recv(stdout, buf: bytearray, deadline: float) -> dict | None:
    while time.monotonic() < deadline:
        msg = _read_content_length(buf)
        if msg is not None:
            return msg
        msg = _read_ndjson(buf)
        if msg is not None:
            return msg
        remain = max(0.0, deadline - time.monotonic())
        ready, _, _ = select.select([stdout], [], [], min(0.2, remain))
        if not ready:
            continue
        chunk = os.read(stdout.fileno(), 4096)
        if not chunk:
            return None
        buf.extend(chunk)
    return None


def list_tools_stdio(
    command: list[str],
    *,
    env: dict[str, str] | None = None,
    cwd: str | None = None,
    timeout_s: float = 8.0,
) -> dict[str, Any]:
    """Handshake + tools/list against a stdio MCP server. Never raises on failure."""
    merged = os.environ.copy()
    if env:
        merged.update({str(k): str(v) for k, v in env.items()})
    merged["PYTHONDONTWRITEBYTECODE"] = "1"
    started = time.monotonic()
    proc = None
    try:
        proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=cwd,
            env=merged,
        )
    except OSError as exc:
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "tools": [],
            "elapsed_s": 0.0,
        }

    buf = bytearray()
    try:
        if proc.stdin is None or proc.stdout is None:
            return {
                "ok": False,
                "error": "stdio-closed",
                "tools": [],
                "elapsed_s": time.monotonic() - started,
            }
        proc.stdin.write(
            _encode(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "aud-0060-enumerator", "version": "1"},
                    },
                }
            )
        )
        proc.stdin.flush()
        init = _recv(proc.stdout, buf, started + timeout_s)
        if not isinstance(init, dict) or "result" not in init:
            return {
                "ok": False,
                "error": "initialize-failed",
                "tools": [],
                "elapsed_s": round(time.monotonic() - started, 3),
            }
        proc.stdin.write(_encode({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        proc.stdin.flush()
        proc.stdin.write(
            _encode({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        )
        proc.stdin.flush()
        listed = _recv(proc.stdout, buf, started + timeout_s)
        tools = []
        if isinstance(listed, dict):
            result = listed.get("result") or {}
            if isinstance(result, dict) and isinstance(result.get("tools"), list):
                tools = [t for t in result["tools"] if isinstance(t, dict)]
        ok = bool(tools) or (isinstance(listed, dict) and "result" in listed)
        return {
            "ok": ok,
            "error": None if ok else "tools-list-failed",
            "protocol_version": (
                (init.get("result") or {}) if isinstance(init.get("result"), dict) else {}
            ).get("protocolVersion"),
            "tools": tools,
            "elapsed_s": round(time.monotonic() - started, 3),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "tools": [],
            "elapsed_s": time.monotonic() - started,
        }
    finally:
        if proc is not None:
            try:
                if proc.stdin:
                    proc.stdin.close()
            except OSError:
                pass
            try:
                proc.kill()
            except OSError:
                pass
            try:
                proc.wait(timeout=1)
            except Exception:  # noqa: BLE001
                pass
