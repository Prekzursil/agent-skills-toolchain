#!/usr/bin/env python3
"""Local interceptors for HTTP client, MCP stdio, and CLI subprocess.

Observers bind 127.0.0.1 only. They never contact a vendor, never read
API keys, and never print environment values.
"""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent


class _HitHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n)
        peer = self.client_address[0] if self.client_address else ""
        self.server.hits.append(  # type: ignore[attr-defined]
            {
                "method": "POST",
                "path": self.path,
                "bytes": len(body),
                "peer": peer,
                "body": body.decode("utf-8", errors="replace"),
            }
        )
        self.send_response(204)
        self.end_headers()

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        return


class HttpObserver:
    """Accepted-POST count on 127.0.0.1:ephemeral. Not a config read."""

    def __init__(self) -> None:
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _HitHandler)
        self.httpd.hits = []  # type: ignore[attr-defined]
        self.port = int(self.httpd.server_address[1])
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def endpoint(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1/research"

    @property
    def hits(self) -> list[dict]:
        return list(self.httpd.hits)  # type: ignore[attr-defined]

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)


class ConnectCounter:
    def __init__(self) -> None:
        self.count = 0
        self._orig = socket.socket.connect
        self._installed = False

    def install(self) -> None:
        if self._installed:
            return
        orig = self._orig
        counter = self

        def _hook(sock: socket.socket, address: Any, *args: Any, **kwargs: Any) -> Any:
            counter.count += 1
            return orig(sock, address, *args, **kwargs)

        socket.socket.connect = _hook  # type: ignore[method-assign]
        self._installed = True

    def remove(self) -> None:
        if not self._installed:
            return
        socket.socket.connect = self._orig  # type: ignore[method-assign]
        self._installed = False


def post_http(endpoint: str, payload: dict) -> int:
    body = json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("utf-8")
    req = Request(
        endpoint,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "Content-Length": str(len(body))},
    )
    with urlopen(req, timeout=3) as resp:  # noqa: S310 localhost observer
        resp.read()
    return len(body)


def send_mcp_stdio(payload: dict, capture: Path) -> dict:
    capture.parent.mkdir(parents=True, exist_ok=True)
    msg = json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n"
    cmd = [
        sys.executable,
        "-B",
        str(HERE / "intercept.py"),
        "--mode",
        "mcp-stub",
        "--capture",
        str(capture),
    ]
    proc = subprocess.run(
        cmd,
        input=msg,
        capture_output=True,
        text=True,
        timeout=8,
        cwd=str(HERE),
    )
    child = {}
    if capture.is_file():
        child = json.loads(capture.read_text(encoding="utf-8"))
    return {
        "exit_code": proc.returncode,
        "parent_wrote": msg,
        "parent_bytes": len(msg.encode("utf-8")),
        "child": child,
        "stdout": (proc.stdout or "")[-400:],
        "stderr": (proc.stderr or "")[-400:],
    }


def send_cli_subprocess(prompt: str, capture: Path, *, workspace: str) -> dict:
    capture.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-B",
        str(HERE / "intercept.py"),
        "--mode",
        "cli-stub",
        "--capture",
        str(capture),
        "-p",
        "--force",
        "--trust",
        "--sandbox",
        "disabled",
        "--workspace",
        workspace,
        prompt,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=8, cwd=str(HERE))
    child = {}
    if capture.is_file():
        child = json.loads(capture.read_text(encoding="utf-8"))
    return {
        "exit_code": proc.returncode,
        "parent_argv_tail": prompt,
        "parent_workspace": workspace,
        "child": child,
        "stdout": (proc.stdout or "")[-400:],
        "stderr": (proc.stderr or "")[-400:],
    }


def _mcp_stub(capture: Path) -> int:
    raw = sys.stdin.read()
    capture.parent.mkdir(parents=True, exist_ok=True)
    rec = {"transport": "mcp-stdio", "stdin": raw, "bytes": len(raw.encode("utf-8"))}
    capture.write_text(json.dumps(rec, ensure_ascii=True) + "\n", encoding="utf-8")
    reply = {"jsonrpc": "2.0", "id": 1, "result": {"ok": True, "echo_bytes": rec["bytes"]}}
    sys.stdout.write(json.dumps(reply) + "\n")
    return 0


def _cli_stub(capture: Path, argv: list[str]) -> int:
    stdin = sys.stdin.read() if not sys.stdin.isatty() else ""
    prompt = argv[-1] if argv else ""
    workspace = ""
    if "--workspace" in argv:
        i = argv.index("--workspace")
        if i + 1 < len(argv):
            workspace = argv[i + 1]
    rec = {
        "transport": "cli-subprocess",
        "argv_count": len(argv),
        "workspace": workspace,
        "prompt": prompt,
        "stdin": stdin,
        "bytes": len(prompt.encode("utf-8")),
    }
    capture.parent.mkdir(parents=True, exist_ok=True)
    capture.write_text(json.dumps(rec, ensure_ascii=True) + "\n", encoding="utf-8")
    sys.stdout.write(json.dumps({"ok": True, "bytes": rec["bytes"]}) + "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--mode" not in args:
        print("FAILED:ADV-0046 intercept needs --mode mcp-stub|cli-stub")
        return 2
    mode = args[args.index("--mode") + 1]
    if "--capture" not in args:
        print("FAILED:ADV-0046 intercept needs --capture")
        return 2
    capture = Path(args[args.index("--capture") + 1])
    if mode == "mcp-stub":
        return _mcp_stub(capture)
    if mode == "cli-stub":
        return _cli_stub(capture, args)
    print(f"FAILED:ADV-0046 unknown intercept mode {mode}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
