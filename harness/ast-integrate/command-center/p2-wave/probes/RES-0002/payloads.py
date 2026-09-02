"""PostToolUse payloads and a loopback HTTP pair for WebFetch-shaped events."""
from __future__ import annotations

import hashlib
import http.server
import threading
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import urlopen

from constants import HERE, REPO

SESSION_ID = "res-0002-one-session"
OK_BODY = b"res-0002-ok-body\n"
MISSING_BODY = b"res-0002-missing-body\n"
READ_TARGET = HERE / "constants.py"


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") == "/ok":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(OK_BODY)))
            self.end_headers()
            self.wfile.write(OK_BODY)
            return
        self.send_response(404)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(MISSING_BODY)))
        self.end_headers()
        self.wfile.write(MISSING_BODY)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def fetch_loopback() -> dict[str, Any]:
    """Real HTTP 200 and HTTP 404 against a throwaway loopback server."""
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    base = f"http://{host}:{port}"
    try:
        with urlopen(base + "/ok", timeout=5) as resp:
            ok_body = resp.read()
            ok_status = int(resp.status)
        missing_status = None
        missing_body = b""
        try:
            urlopen(base + "/missing", timeout=5)
        except HTTPError as exc:
            missing_status = int(exc.code)
            missing_body = exc.read()
        return {
            "ok_url": base + "/ok",
            "missing_url": base + "/missing",
            "ok_status": ok_status,
            "ok_body_sha256": _sha(ok_body),
            "ok_body_len": len(ok_body),
            "missing_status": missing_status,
            "missing_body_sha256": _sha(missing_body),
            "missing_body_len": len(missing_body),
            "ok_body_matches_fixture": ok_body == OK_BODY,
            "missing_body_matches_fixture": missing_body == MISSING_BODY,
        }
    finally:
        server.shutdown()
        server.server_close()


def read_file_event() -> tuple[dict[str, Any], dict[str, Any]]:
    text = READ_TARGET.read_text(encoding="utf-8")
    meta = {
        "path": str(READ_TARGET.relative_to(REPO).as_posix()),
        "bytes": len(text.encode("utf-8")),
        "sha256": _sha(text.encode("utf-8")),
    }
    event = {
        "session_id": SESSION_ID,
        "cwd": str(REPO),
        "hook_event_name": "PostToolUse",
        "tool_name": "Read",
        "tool_input": {"file_path": meta["path"]},
        "tool_response": {
            "type": "text",
            "file": {"filePath": meta["path"], "content": text[:400]},
        },
    }
    return event, meta


def websearch_event() -> dict[str, Any]:
    return {
        "session_id": SESSION_ID,
        "cwd": str(REPO),
        "hook_event_name": "PostToolUse",
        "tool_name": "WebSearch",
        "tool_input": {"query": "RES-0002 tool-sentinel HTTP 200 FAILED"},
        "tool_response": {
            "results": [
                {
                    "title": "fixture search hit",
                    "url": "https://example.invalid/res-0002",
                    "snippet": "constructed WebSearch-shaped success payload",
                }
            ]
        },
    }


def webfetch_event(url: str, status: int, body: str) -> dict[str, Any]:
    return {
        "session_id": SESSION_ID,
        "cwd": str(REPO),
        "hook_event_name": "PostToolUse",
        "tool_name": "WebFetch",
        "tool_input": {"url": url},
        "tool_response": {
            "url": url,
            "status_code": status,
            "status": status,
            "http_status": status,
            "body": body,
        },
    }


def session_events(http_pair: dict[str, Any]) -> list[dict[str, Any]]:
    read_event, _ = read_file_event()
    return [
        websearch_event(),
        read_event,
        webfetch_event(http_pair["ok_url"], int(http_pair["ok_status"]), "ok"),
        webfetch_event(
            http_pair["missing_url"], int(http_pair["missing_status"]), "missing"
        ),
    ]
