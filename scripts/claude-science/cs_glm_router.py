#!/usr/bin/env python3
"""cs_glm_router — local Anthropic-API router for Claude Science (GLM bridge v2).

WHY THIS EXISTS (measured 2026-09-20): pointing the daemon's ANTHROPIC_BASE_URL
straight at api.z.ai breaks its account plane — session validation, OAuth
refresh and the MCP directory all ride the same SDK base URL and fail at the
GLM endpoint ("claude.ai session expired ... could not be refreshed"). The
daemon is not Claude Code; you cannot redirect everything.

This router splits the planes:
  /v1/messages*  -> https://api.z.ai/api/coding/paas/v4  (model mapped to GLM,
                    auth swapped to the ZAI plan key)
  everything else-> https://api.anthropic.com             (headers untouched:
                    the session/OAuth plane keeps talking to the real thing)

Run:  python3 cs_glm_router.py            (foreground; supervise via nohup)
Env:  CS_ROUTER_PORT (default 8231)
      ZAI_API_KEY    (the active plan key; cs-model glm exports it)
Fail-closed: without ZAI_API_KEY it exits 1 at startup.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ZAI_MESSAGES_URL = "https://api.z.ai/api/anthropic/v1/messages"
ANTHROPIC_ORIGIN = "https://api.anthropic.com"
GLM_MODEL = os.environ.get("CS_GLM_MODEL", "glm-4.6")
PORT = int(os.environ.get("CS_ROUTER_PORT", "8231"))
ZAI_KEY = os.environ.get("ZAI_API_KEY", "")

HOP_HEADERS = {"content-length", "host", "connection", "transfer-encoding", "accept-encoding"}


class Router(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _proxy(self) -> None:
        length = int(self.headers.get("content-length") or 0)
        body = self.rfile.read(length) if length else b""
        is_messages = self.path.startswith("/v1/messages")

        url = ZAI_MESSAGES_URL if is_messages else ANTHROPIC_ORIGIN + self.path
        out_headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_HEADERS}

        if is_messages:
            out_headers["Authorization"] = f"Bearer {ZAI_KEY}"
            out_headers["x-api-key"] = ZAI_KEY
            try:
                doc = json.loads(body) if body else {}
                if isinstance(doc.get("model"), str):
                    doc["model"] = GLM_MODEL
                body = json.dumps(doc).encode()
                out_headers["content-length"] = str(len(body))
            except Exception:
                pass  # non-JSON body: forward as-is

        req = urllib.request.Request(url, data=body or None, headers=out_headers, method=self.command)
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                status, rheaders, rbody = r.status, r.headers, r.read()
        except urllib.error.HTTPError as e:
            status = e.code
            rbody = e.read()
            self.send_response(status)
            self.send_header("content-type", e.headers.get("content-type", "application/json"))
            self.send_header("content-length", str(len(rbody)))
            self.end_headers()
            self.wfile.write(rbody)
            print(f"[router] {self.command} {self.path} -> {status} (upstream error)", flush=True)
            return
        except Exception as e:
            msg = json.dumps({"router_error": f"{type(e).__name__}: {e}"}).encode()
            self.send_response(502)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)
            print(f"[router] {self.command} {self.path} -> 502 ({type(e).__name__})", flush=True)
            return

        self.send_response(status)
        for k, v in rheaders.items():
            if k.lower() in HOP_HEADERS or k.lower() == "content-encoding":
                continue
            self.send_header(k, v)
        self.send_header("content-length", str(len(rbody)))
        self.end_headers()
        self.wfile.write(rbody)
        print(f"[router] {self.command} {self.path} -> {status} ({'glm' if is_messages else 'anthropic'})", flush=True)

    do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = _proxy

    def log_message(self, *a):  # default noise off; [router] lines above suffice
        pass


def main() -> int:
    if not ZAI_KEY:
        print("FAILED:cs-glm-router ZAI_API_KEY not set (cs-model glm exports it)")
        return 1
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Router)
    print(f"SUCCESS:cs-glm-router listening on 127.0.0.1:{PORT} "
          f"(/v1/messages -> {GLM_MODEL} @ z.ai; rest -> api.anthropic.com)", flush=True)
    srv.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
