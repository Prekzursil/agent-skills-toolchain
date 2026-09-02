"""Loopback fixture server: genuine registry JSON vs HTML interstitial."""
from __future__ import annotations

import hashlib
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

INTERSTITIAL = (HERE / "fixtures" / "interstitial.html").read_bytes()
SEED_MARKER = b"TST-0134-INDEX-SEED-DO-NOT-CLOBBER\n"
FIXTURE_INDEX = REPO / "tools" / "marketplace" / "fixtures" / "index.json"


def genuine_index_page() -> dict[str, Any]:
    """Build an index_page document {ok: true, items: [...]} for the live fixture.

    Uses the IMP-0074 conformance index when present; otherwise a loopback
    singleton. Shape is the HTTP client's index_page, not index_response.
    """
    items: list[dict[str, Any]] = []
    if FIXTURE_INDEX.is_file():
        doc = json.loads(FIXTURE_INDEX.read_text(encoding="utf-8"))
        for plugin in doc.get("plugins") or []:
            if not isinstance(plugin, dict):
                continue
            name = plugin.get("name")
            if not name:
                continue
            row: dict[str, Any] = {
                "name": name,
                "version": plugin.get("version") or "0.0.0",
                "source": plugin.get("source") or ".",
                "license": plugin.get("license") or "MIT",
            }
            items.append(row)
    if not items:
        items = [
            {
                "name": "loopback-fixture",
                "version": "1.0.0",
                "source": "loopback://tst-0134",
                "license": "MIT",
            }
        ]
    return {"ok": True, "items": items}


class FixtureServer:
    def __init__(self) -> None:
        payload = genuine_index_page()
        if payload.get("ok") is not True or "items" not in payload:
            raise RuntimeError("fixture index_page missing ok/items")
        self.genuine_payload = payload
        self.genuine_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        handler = _handler(self.genuine_body)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.httpd.server_address[:2]
        self.base = f"http://{host}:{port}"
        self.genuine_url = f"{self.base}/v1/index"
        self.interstitial_url = f"{self.base}/interstitial"
        self.bad_schema_url = f"{self.base}/bad-schema"
        self.json_typed_html_url = f"{self.base}/json-typed-html"

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)


def _handler(genuine_body: bytes) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path == "/v1/index":
                body = genuine_body
                ctype = "application/json; charset=utf-8"
            elif path == "/interstitial":
                body = INTERSTITIAL
                ctype = "text/html; charset=utf-8"
            elif path == "/json-typed-html":
                body = INTERSTITIAL
                ctype = "application/json"
            elif path == "/bad-schema":
                body = b'{"ok": true}'
                ctype = "application/json; charset=utf-8"
            else:
                self.send_response(404)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"not found\n")
                return
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args: object) -> None:
            return

    return Handler


def seed_index(path: Path) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(SEED_MARKER)
    st = path.stat()
    return {
        "mtime_ns": st.st_mtime_ns,
        "size": st.st_size,
        "sha256": hashlib.sha256(SEED_MARKER).hexdigest(),
        "exists": True,
    }


def stat_index(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"mtime_ns": None, "size": None, "sha256": None, "exists": False}
    raw = path.read_bytes()
    st = path.stat()
    return {
        "mtime_ns": st.st_mtime_ns,
        "size": st.st_size,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "exists": True,
    }


def index_unchanged(before: dict[str, Any], after: dict[str, Any]) -> bool:
    return (
        before.get("exists") is True
        and after.get("exists") is True
        and before.get("mtime_ns") == after.get("mtime_ns")
        and before.get("size") == after.get("size")
        and before.get("sha256") == after.get("sha256")
    )


def error_names_content_type(err: BaseException) -> bool:
    text = str(err)
    lowered = text.lower()
    if "traceback" in lowered or "jsondecodeerror" in lowered or "expecting value" in lowered:
        return False
    return "content-type" in lowered or "content type" in lowered
