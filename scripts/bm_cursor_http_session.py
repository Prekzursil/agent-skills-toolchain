"""Talk to Basic Memory over HTTP MCP with session refresh.

Cursor's built-in HTTP MCP client keeps a stale ``mcp-session-id`` after the
:18765 daemon restarts (watchdog). JSON-RPC then returns -32600 Session not
found while the port is healthy. This process:

* never binds :18765
* never starts/kills the daemon (watchdog / BasicMemory-HTTP-MCP own that)
* on Session not found, initialize again and retry the call once

Modes:
  --stdio   Cursor MCP stdio proxy (default when no --call)
  --call TOOL ARGS_JSON   one-shot tools/call for agents when Cursor MCP is stale
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any, cast

DEFAULT_URL = "http://127.0.0.1:18765/mcp"
CLIENT_INFO = {"name": "bm-cursor-http-session", "version": "1"}
PROTOCOL = "2025-03-26"


class SessionGone(RuntimeError):
    """Server rejected the MCP session id (daemon restarted)."""


class StdioMessageError(ValueError):
    """Malformed or unsupported message received on MCP stdio."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def decode_rpc_message(raw: bytes) -> dict[str, Any]:
    try:
        value: Any = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StdioMessageError(-32700, f"Parse error: {exc}") from exc
    if not isinstance(value, dict):
        raise StdioMessageError(-32600, "Invalid Request: expected a JSON object")
    return cast(dict[str, Any], value)


def parse_rpc_body(raw: bytes, content_type: str | None) -> dict[str, Any]:
    text = raw.decode("utf-8", errors="replace").strip()
    if not text:
        raise ValueError("Empty Basic Memory JSON-RPC response")
    ctype = (content_type or "").lower()
    if "text/event-stream" in ctype or text.startswith("event:") or "\ndata:" in text:
        data_lines: list[str] = []
        for line in text.splitlines():
            if line.startswith("data:"):
                data_lines.append(line[5:].lstrip())
        if not data_lines:
            raise ValueError("Empty Basic Memory SSE response")
        value: Any = json.loads("\n".join(data_lines))
    else:
        value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("Basic Memory returned a non-object JSON-RPC response")
    return cast(dict[str, Any], value)


def is_session_not_found(payload: dict[str, Any]) -> bool:
    err = payload.get("error")
    if not isinstance(err, dict):
        return False
    msg = str(err.get("message") or "")
    code = err.get("code")
    return code == -32600 and "session not found" in msg.lower()


class BmHttpSession:
    def __init__(self, url: str = DEFAULT_URL, timeout: float = 90.0) -> None:
        self.url = url
        self.timeout = timeout
        self.session_id: str | None = None
        self._next_id = 1
        self._initialized = False

    def _alloc_id(self) -> int:
        rid = self._next_id
        self._next_id += 1
        return rid

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        return headers

    def post_raw(self, payload: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.url, data=body, method="POST", headers=self._headers()
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
                sid = resp.headers.get("Mcp-Session-Id") or resp.headers.get(
                    "mcp-session-id"
                )
                try:
                    parsed = parse_rpc_body(raw, resp.headers.get("Content-Type"))
                except ValueError:
                    if "id" not in payload:
                        return {}, sid
                    raise
                return parsed, sid
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            parsed = parse_rpc_body(raw, exc.headers.get("Content-Type") if exc.headers else None)
            if parsed:
                return parsed, None
            raise

    def rpc(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": self._alloc_id(),
            "method": method,
        }
        if params is not None:
            payload["params"] = params
        parsed, sid = self.post_raw(payload)
        if sid:
            self.session_id = sid
        if is_session_not_found(parsed):
            raise SessionGone(parsed.get("error", {}).get("message", "Session not found"))
        return parsed

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        try:
            self.post_raw(payload)
        except SessionGone:
            raise
        except OSError:
            # notifications are fire-and-forget on a dying socket
            return

    def handshake(
        self,
        protocol_version: str = PROTOCOL,
        *,
        notify_initialized: bool = True,
    ) -> dict[str, Any]:
        self.session_id = None
        self._initialized = False
        result = self.rpc(
            "initialize",
            {
                "protocolVersion": protocol_version,
                "capabilities": {},
                "clientInfo": CLIENT_INFO,
            },
        )
        if "error" in result:
            return result
        if notify_initialized:
            self.notify("notifications/initialized")
        self._initialized = True
        return result

    def call_with_retry(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if method == "initialize":
            version_value = (
                params.get("protocolVersion") if isinstance(params, dict) else None
            )
            requested_version = (
                version_value if isinstance(version_value, str) else PROTOCOL
            )
            return self.handshake(
                requested_version,
                notify_initialized=False,
            )
        if not self._initialized:
            init = self.handshake()
            if "error" in init:
                return init
        try:
            return self.rpc(method, params)
        except SessionGone:
            init = self.handshake()
            if "error" in init:
                return init
            if method == "notifications/initialized":
                return {"jsonrpc": "2.0", "result": None}
            return self.rpc(method, params)


def read_stdio_message() -> dict[str, Any] | None:
    while True:
        first_line = sys.stdin.buffer.readline()
        if not first_line:
            return None
        if first_line not in (b"\r\n", b"\n"):
            break

    # MCP stdio uses one JSON-RPC message per line. Retain Content-Length input
    # support for older callers, but always emit MCP-native NDJSON below.
    if not first_line.lower().startswith(b"content-length:"):
        return decode_rpc_message(first_line)

    header_lines = [first_line]
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break
        header_lines.append(line)

    length = None
    for raw_line in header_lines:
        line = raw_line.decode("ascii", errors="replace").strip()
        if line.lower().startswith("content-length:"):
            try:
                length = int(line.split(":", 1)[1].strip())
            except ValueError as exc:
                raise StdioMessageError(-32600, "Invalid Content-Length") from exc
            break
    if length is None or length <= 0:
        raise StdioMessageError(-32600, "Invalid Content-Length")
    body = sys.stdin.buffer.read(length)
    if len(body) != length:
        raise StdioMessageError(-32700, "Incomplete Content-Length frame")
    return decode_rpc_message(body)


def write_stdio_message(payload: dict[str, Any]) -> None:
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    sys.stdout.buffer.write(raw)
    sys.stdout.buffer.write(b"\n")
    sys.stdout.buffer.flush()


def write_stdio_error(req_id: Any, code: int, message: str) -> None:
    write_stdio_message(
        {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": code, "message": message[:500]},
        }
    )


def stdio_loop(session: BmHttpSession) -> int:
    while True:
        try:
            msg = read_stdio_message()
        except StdioMessageError as exc:
            write_stdio_error(None, exc.code, exc.message)
            continue
        if msg is None:
            return 0
        method = msg.get("method")
        params = msg.get("params")
        req_id = msg.get("id")
        if not isinstance(method, str):
            write_stdio_error(req_id, -32600, "Invalid Request: method must be a string")
            continue
        if req_id is None:
            if method == "notifications/initialized":
                session.notify("notifications/initialized")
            elif method:
                try:
                    session.notify(str(method), params if isinstance(params, dict) else None)
                except SessionGone:
                    session.handshake()
            continue
        try:
            result = session.call_with_retry(
                method, params if isinstance(params, dict) else None
            )
        except OSError as exc:
            write_stdio_error(
                req_id, -32000, f"Basic Memory transport unavailable: {exc}"
            )
            continue
        except ValueError as exc:
            write_stdio_error(req_id, -32603, f"Basic Memory response error: {exc}")
            continue
        out: dict[str, Any] = {"jsonrpc": "2.0", "id": req_id}
        if "error" in result:
            out["error"] = result["error"]
        else:
            out["result"] = result.get("result")
        write_stdio_message(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--stdio", action="store_true", help="Cursor MCP stdio proxy")
    parser.add_argument("--call", nargs=2, metavar=("TOOL", "ARGS_JSON"), help="one-shot tools/call")
    args = parser.parse_args(argv)
    session = BmHttpSession(url=args.url)
    if args.call:
        tool, raw_args = args.call
        params = {"name": tool, "arguments": json.loads(raw_args)}
        result = session.call_with_retry("tools/call", params)
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0 if "error" not in result and not _is_tool_error(result) else 1
    return stdio_loop(session)


def _is_tool_error(result: dict[str, Any]) -> bool:
    inner = result.get("result")
    return isinstance(inner, dict) and inner.get("isError") is True


if __name__ == "__main__":
    raise SystemExit(main())
