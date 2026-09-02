"""Live egress block (unshare -n) plus a local HTTP origin for unblocked runs."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent
GETPIP = HERE / "fixtures" / "get-pip.py"


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/bootstrap/get-pip.py"):
            body = GETPIP.read_bytes()
            self._send(200, body, "text/x-python")
            return
        if self.path.startswith("/control"):
            self._send(200, b"CNF-0147-CONTROL-OK\n", "text/plain")
            return
        if self.path.startswith("/declared"):
            self._send(200, b"CNF-0147-DECLARED-OK\n", "text/plain")
            return
        self._send(404, b"not found\n", "text/plain")

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        return


class LocalOrigin:
    def __init__(self) -> None:
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def port(self) -> int:
        return int(self.httpd.server_address[1])

    def start(self) -> int:
        self.thread.start()
        return self.port

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)


def control_url(port: int) -> str:
    return f"http://127.0.0.1:{port}/control"


def fetch_open(url: str, timeout: float = 2.0) -> dict:
    try:
        with urlopen(url, timeout=timeout) as resp:
            body = resp.read()
        return {
            "ok": True,
            "status": int(getattr(resp, "status", 200) or 200),
            "body_prefix": body[:80].decode("utf-8", "replace"),
        }
    except Exception as exc:
        return {
            "ok": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def fetch_blocked_unshare(url: str) -> dict:
    """Second-process netns block: mechanically different from in-process patch."""
    script = (
        "import json,sys\n"
        "from urllib.request import urlopen\n"
        "url=sys.argv[1]\n"
        "try:\n"
        "    urlopen(url, timeout=2)\n"
        "    print(json.dumps({'ok': True}))\n"
        "except Exception as e:\n"
        "    print(json.dumps({'ok': False, 'error_type': type(e).__name__, 'error': str(e)}))\n"
    )
    try:
        proc = subprocess.run(
            ["unshare", "-rn", sys.executable, "-c", script, url],
            capture_output=True,
            text=True,
            timeout=15,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
    except FileNotFoundError:
        return {
            "ok": None,
            "error_type": "FileNotFoundError",
            "error": "unshare not found",
        }
    except subprocess.TimeoutExpired:
        return {"ok": None, "error_type": "TimeoutExpired", "error": "unshare timeout"}
    raw = (proc.stdout or "").strip().splitlines()
    if not raw:
        return {
            "ok": None,
            "error_type": "EmptyOutput",
            "error": (proc.stderr or "")[-400:],
            "returncode": proc.returncode,
        }
    try:
        return json.loads(raw[-1])
    except json.JSONDecodeError:
        return {
            "ok": None,
            "error_type": "JSONDecodeError",
            "error": raw[-1][:400],
            "returncode": proc.returncode,
        }


def prove_block(port: int) -> dict:
    url = control_url(port)
    opened = fetch_open(url)
    blocked = fetch_blocked_unshare(url)
    ok = bool(opened.get("ok")) and blocked.get("ok") is False
    return {
        "url": url,
        "method": "unshare -n",
        "unblocked_ok": bool(opened.get("ok")),
        "unblocked": opened,
        "blocked_ok": bool(blocked.get("ok")),
        "blocked": blocked,
        "blocked_error": str(
            (blocked or {}).get("error") or (blocked or {}).get("error_type") or ""
        ),
        "pass": ok,
    }
