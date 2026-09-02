"""External URL fetch with retry; UNREACHABLE is never folded into WRONG."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

WRONG_STATUSES = frozenset({404, 410})
OK_STATUSES = range(200, 400)
RETRYABLE = frozenset(
    {
        "URLError",
        "OSError",
        "TimeoutError",
        "socket.timeout",
        "ConnectionError",
        "ConnectionRefusedError",
        "ConnectionResetError",
        "gaierror",
        "timeout",
        "HTTPException",
    }
)


def classify_result(row: dict) -> str:
    """Fail closed to UNREACHABLE. WRONG is only 404/410 after a real HTTP status."""
    status = row.get("http_status")
    if isinstance(status, int) and status in WRONG_STATUSES:
        return "WRONG"
    if isinstance(status, int) and status in OK_STATUSES:
        return "OK"
    if isinstance(status, int) and status in (401, 403):
        return "RESTRICTED"
    return "UNREACHABLE"


def fetch_once(url: str, timeout: float = 2.0) -> dict:
    req = Request(url, method="GET", headers={"User-Agent": "TST-0255-link-check"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            status = int(getattr(resp, "status", 200) or 200)
            resp.read(64)
        row = {
            "url": url,
            "ok": 200 <= status < 400,
            "http_status": status,
            "error_type": None,
            "error": None,
        }
    except HTTPError as exc:
        row = {
            "url": url,
            "ok": False,
            "http_status": int(exc.code),
            "error_type": "HTTPError",
            "error": str(exc)[:240],
        }
    except Exception as exc:
        row = {
            "url": url,
            "ok": False,
            "http_status": None,
            "error_type": type(exc).__name__,
            "error": str(exc)[:240],
        }
    row["classification"] = classify_result(row)
    return row


def fetch_with_retry(url: str, attempts: int = 3, timeout: float = 2.0) -> dict:
    last = None
    delays = (0.05, 0.15, 0.3)
    for i in range(attempts):
        last = fetch_once(url, timeout=timeout)
        last["attempt"] = i + 1
        last["attempts"] = attempts
        cls = last["classification"]
        if cls in {"OK", "WRONG", "RESTRICTED"}:
            last["retried"] = i > 0
            return last
        if i + 1 < attempts:
            time.sleep(delays[min(i, len(delays) - 1)])
    assert last is not None
    last["retried"] = attempts > 1
    last["classification"] = "UNREACHABLE"
    return last


_UNSHARE_SCRIPT = """
import json, sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError
url, timeout = sys.argv[1], float(sys.argv[2])
req = Request(url, method="GET", headers={"User-Agent": "TST-0255-link-check"})
try:
    with urlopen(req, timeout=timeout) as resp:
        status = int(getattr(resp, "status", 200) or 200)
        resp.read(64)
    print(json.dumps({"ok": True, "http_status": status, "error_type": None, "error": None}))
except HTTPError as e:
    print(json.dumps({"ok": False, "http_status": int(e.code), "error_type": "HTTPError", "error": str(e)}))
except Exception as e:
    print(json.dumps({"ok": False, "http_status": None, "error_type": type(e).__name__, "error": str(e)}))
"""


def fetch_unshare(url: str, timeout: float = 2.0) -> dict:
    try:
        proc = subprocess.run(
            ["unshare", "-n", sys.executable, "-c", _UNSHARE_SCRIPT, url, str(timeout)],
            capture_output=True,
            text=True,
            timeout=15,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
    except FileNotFoundError:
        row = {
            "url": url,
            "ok": False,
            "http_status": None,
            "error_type": "FileNotFoundError",
            "error": "unshare not found",
            "method": "unshare -n",
        }
        row["classification"] = classify_result(row)
        return row
    except subprocess.TimeoutExpired:
        row = {
            "url": url,
            "ok": False,
            "http_status": None,
            "error_type": "TimeoutExpired",
            "error": "unshare timeout",
            "method": "unshare -n",
        }
        row["classification"] = classify_result(row)
        return row
    raw = (proc.stdout or "").strip().splitlines()
    if not raw:
        row = {
            "url": url,
            "ok": False,
            "http_status": None,
            "error_type": "EmptyOutput",
            "error": (proc.stderr or "")[-400:],
            "returncode": proc.returncode,
            "method": "unshare -n",
        }
        row["classification"] = classify_result(row)
        return row
    try:
        parsed = json.loads(raw[-1])
    except json.JSONDecodeError:
        row = {
            "url": url,
            "ok": False,
            "http_status": None,
            "error_type": "JSONDecodeError",
            "error": raw[-1][:400],
            "method": "unshare -n",
        }
        row["classification"] = classify_result(row)
        return row
    parsed["url"] = url
    parsed["method"] = "unshare -n"
    parsed["returncode"] = proc.returncode
    parsed["classification"] = classify_result(parsed)
    return parsed


def broken_fold_unreachable_into_wrong(row: dict) -> str:
    """Known-broken classifier: any failure becomes 404/WRONG."""
    if row.get("classification") == "OK":
        return "OK"
    return "WRONG"


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/ok"):
            body = b"TST-0255-OK\n"
            self.send_response(200)
        elif self.path.startswith("/gone"):
            body = b"TST-0255-GONE\n"
            self.send_response(410)
        else:
            body = b"TST-0255-MISSING\n"
            self.send_response(404)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        return


class LocalOrigin:
    def __init__(self) -> None:
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.thread = Thread(target=self.httpd.serve_forever, daemon=True)

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
