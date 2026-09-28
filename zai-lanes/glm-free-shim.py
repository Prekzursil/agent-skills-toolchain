#!/usr/bin/env python3
"""glm-free-shim - Anthropic Messages API facade over the free GLM lane (:18319).

Lets a DEDICATED Claude Code instance run on free browser-lane GLM:
    ANTHROPIC_BASE_URL=http://127.0.0.1:18400 ANTHROPIC_AUTH_TOKEN=free-lane-local claude
Never point an EXISTING session's env at this ( blunt base-url override breaks the
session plane); use the claude-free.cmd launcher (separate instance).

Endpoints: POST /v1/messages (stream + non-stream), GET /v1/models.
Model mapping: any requested model -> FREE_MODEL env (default glm-web; use
glm-web-think / glm-web-max for the deeper modes).
"""
import json
import os
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BRIDGE = os.environ.get("FREE_BRIDGE", "http://127.0.0.1:18319")
FREE_MODEL = os.environ.get("FREE_MODEL", "glm-web")
PORT = int(os.environ.get("SHIM_PORT", "18400"))
TIMEOUT = int(os.environ.get("SHIM_TIMEOUT", "600"))


def bridge_chat(messages):
    body = json.dumps({"model": FREE_MODEL, "messages": messages}).encode()
    req = urllib.request.Request(
        BRIDGE + "/v1/chat/completions", data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        data = json.loads(r.read().decode())
    return data["choices"][0]["message"]["content"] or ""


def to_openai_messages(req):
    msgs = []
    sysv = req.get("system")
    if sysv:
        msgs.append({"role": "system", "content": sysv if isinstance(sysv, str)
                     else " ".join(b.get("text", "") for b in sysv)})
    for m in req.get("messages", []):
        c = m.get("content")
        text = c if isinstance(c, str) else " ".join(
            b.get("text", "") for b in c if isinstance(b, dict))
        msgs.append({"role": m.get("role", "user"), "content": text})
    return msgs


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _json(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.rstrip("/").endswith("/models"):
            self._json(200, {"data": [{"id": FREE_MODEL, "type": "model",
                                       "display_name": "GLM free lane"}]})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if not self.path.rstrip("/").endswith("/messages"):
            self._json(404, {"error": "not found"})
            return
        req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        rid = "msg_" + uuid.uuid4().hex[:20]
        try:
            reply = bridge_chat(to_openai_messages(req))
        except Exception as exc:  # surface a real Anthropic-shaped error
            self._json(529, {"type": "error", "error": {
                "type": "api_error", "message": f"free-lane bridge error: {exc}"}})
            return
        usage = {"input_tokens": 0, "output_tokens": 0}
        if not req.get("stream"):
            self._json(200, {
                "id": rid, "type": "message", "role": "assistant",
                "model": req.get("model", FREE_MODEL),
                "content": [{"type": "text", "text": reply}],
                "stop_reason": "end_turn", "stop_sequence": None,
                "usage": usage})
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        def ev(name, obj):
            self.wfile.write(f"event: {name}\ndata: {json.dumps(obj)}\n\n".encode())
            self.wfile.flush()

        ev("message_start", {"type": "message_start", "message": {
            "id": rid, "type": "message", "role": "assistant",
            "model": req.get("model", FREE_MODEL), "content": [],
            "stop_reason": None, "stop_sequence": None, "usage": usage}})
        ev("content_block_start", {"type": "content_block_start", "index": 0,
                                   "content_block": {"type": "text", "text": ""}})
        for i in range(0, len(reply), 200):
            ev("content_block_delta", {"type": "content_block_delta", "index": 0,
                                       "delta": {"type": "text_delta",
                                                 "text": reply[i:i + 200]}})
        ev("content_block_stop", {"type": "content_block_stop", "index": 0})
        ev("message_delta", {"type": "message_delta",
                             "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                             "usage": usage})
        ev("message_stop", {"type": "message_stop"})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print(f"glm-free-shim on :{PORT} -> {BRIDGE} (model {FREE_MODEL})", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
