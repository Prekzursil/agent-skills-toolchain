#!/usr/bin/env python3
"""zai-anon-mcp — Lane A, SOTA build (v2). Free consumer GLM (chat.z.ai web) as MCP + OpenAI-compat bridge.

Web-lane modes (mapped from the live UI request stream):
  flash  — GLM-5.3-Flash fast path (enable_thinking false)
  think  — Deep Think (enable_thinking true)
  max    — Deep Think + Max (reasoning_effort max)

Tools (stdio MCP):
  glm_chat(prompt, mode?, web_search?, chat?)   reply text; chat=<ref> continues a conversation
  glm_stream(prompt, mode?)                     streams partials via MCP progress notifications
  glm_conversations()                           list live conversation refs
  glm_status()                                  engine/profile health
HTTP bridge (python zai-anon-mcp.py http [port], default 18319):
  POST /v1/chat/completions {model: glm-web|glm-web-think|glm-web-max, stream:true|false, messages}
  (multi-turn honored: prior messages concatenated as context prompt)

Engine: dedicated HEADED Playwright profile ~/.zcode/web-profile (Aliyun invisible captcha
passes only in headed real contexts — headless measured-blocked). Idle reaper 10 min.
Session bootstrap ~/.zcode/web-session.json; refresh via `login` subcommand (headed, once).
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
import uuid
from pathlib import Path

PROFILE = Path.home() / ".zcode" / "web-profile"
SESSION_FILE = Path.home() / ".zcode" / "web-session.json"
BASE = "https://chat.z.ai"
IDLE_KILL_S = 600


class Engine:
    def __init__(self):
        self._pw = self._browser = self._page = None
        self._lock = threading.Lock()
        self._last_used = 0.0
        self.chats: dict[str, str] = {}
        self.chat_lock = threading.Lock()

    def _bootstrap_cookies(self, context):
        if SESSION_FILE.exists():
            tok = json.loads(SESSION_FILE.read_text(encoding="utf-8")).get("token", "")
            if tok:
                context.add_cookies(
                    [
                        {
                            "name": "token",
                            "value": tok,
                            "domain": ".chat.z.ai",
                            "path": "/",
                            "httpOnly": True,
                            "secure": True,
                            "sameSite": "Lax",
                        }
                    ]
                )

    def ensure(self):
        with self._lock:
            self._last_used = time.time()
            if self._page and not self._page.is_closed():
                return self._page
            from playwright.sync_api import sync_playwright

            self._pw = sync_playwright().start()
            headed = os.environ.get("ZAI_LANE_A_HEADED", "1") != "0"
            context = self._pw.chromium.launch_persistent_context(
                str(PROFILE),
                headless=not headed,
                viewport={"width": 1280, "height": 900},
                args=["--disable-blink-features=AutomationControlled"],
            )
            self._bootstrap_cookies(context)
            self._browser = context
            self._page = context.pages[0] if context.pages else context.new_page()
            self._page.goto(BASE + "/", wait_until="domcontentloaded", timeout=45000)
            self._page.wait_for_timeout(2500)
            return self._page

    def _set_mode(self, page, mode: str):
        want_think = mode in ("think", "max")
        try:
            el = page.locator("text=Deep Think").first
            cls = el.get_attribute("class") or ""
            think_on = ("text-primary" in cls) or (
                "bg-" in cls and "text-" in cls and "opacity-100" in cls
            )
        except Exception:
            think_on = False
        try:
            if want_think and not think_on:
                page.locator("text=Deep Think").first.click(timeout=3000)
                page.wait_for_timeout(500)
            elif (not want_think) and think_on:
                page.locator("text=Deep Think").first.click(timeout=3000)
                page.wait_for_timeout(500)
            if mode == "max":
                page.locator("text=Max").first.click(timeout=3000)
                page.wait_for_timeout(300)
        except Exception:
            pass  # mode toggles are best-effort; default lane still works

    def _last_reply(self, page, prompt: str) -> str:
        loc = page.locator("[class*='markdown']")
        best = ""
        for i in range(loc.count()):
            t = (loc.nth(i).inner_text() or "").strip()
            if (
                t
                and prompt[:40] not in t
                and t not in ("Thinking...", "Thinking", "Thought Process", "...")
            ):
                best = t
        return best.replace("Thought Process\n\n", "", 1).strip()

    def chat(
        self,
        prompt: str,
        mode: str = "flash",
        web_search: bool = False,
        chat_ref: str | None = None,
        on_progress=None,
    ) -> dict:
        page = self.ensure()
        if chat_ref and chat_ref in self.chats:
            page.goto(
                f"{BASE}/c/{self.chats[chat_ref]}",
                wait_until="domcontentloaded",
                timeout=45000,
            )
            page.wait_for_timeout(2500)
        else:
            page.goto(BASE + "/", wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(1500)
            try:
                for btn in page.locator(
                    "button[aria-label='Close'], button:has-text('Maybe Later')"
                ).all()[:2]:
                    btn.click(timeout=1500)
                    page.wait_for_timeout(400)
            except Exception:
                pass
        self._set_mode(page, mode)
        box = page.locator("textarea, [contenteditable='true']").nth(0)
        box.wait_for(state="visible", timeout=20000)
        box.fill(prompt)
        box.press("Enter")
        try:
            page.wait_for_url("**/c/**", timeout=15000)
        except Exception:
            pass
        cid = (
            page.url.split("/c/")[1].split("/")[0].split("?")[0]
            if "/c/" in page.url
            else ""
        )
        if cid:
            if chat_ref:
                self.chats[chat_ref] = cid
            else:
                chat_ref = f"chat-{len(self.chats) + 1}"
                self.chats[chat_ref] = cid
        deadline = time.time() + 180
        emitted, last_txt, stable = 0, "", 0
        while time.time() < deadline:
            page.wait_for_timeout(1000)
            cur = self._last_reply(page, prompt)
            if cur and len(cur) > emitted:
                if on_progress and len(cur) - emitted >= 40:
                    try:
                        on_progress(cur[emitted:])
                    except Exception:
                        pass
                emitted, last_txt, stable = len(cur), cur, 0
            elif cur and cur == last_txt:
                stable += 1
                if stable >= 3 and emitted > 0:
                    break
            else:
                stable += 1
                if stable > 30:
                    break
        return {
            "ok": bool(last_txt),
            "reply": last_txt[:16000],
            "chat_ref": chat_ref,
            "mode": mode,
        }

    def vision(self, prompt: str, image_path: str) -> dict:
        with self.chat_lock:
            page = self.ensure()
            page.goto(BASE + "/", wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(1500)
            try:
                for btn in page.locator(
                    "button[aria-label='Close'], button:has-text('Maybe Later')"
                ).all()[:2]:
                    btn.click(timeout=1500)
                    page.wait_for_timeout(300)
            except Exception:
                pass
            fi = page.locator("input[type='file']").first
            fi.set_input_files(image_path, timeout=15000)
            page.wait_for_timeout(2500)
            box = page.locator("textarea, [contenteditable='true']").nth(0)
            box.wait_for(state="visible", timeout=20000)
            box.fill(prompt)
            box.press("Enter")
            try:
                page.wait_for_url("**/c/**", timeout=20000)
            except Exception:
                pass
            deadline = time.time() + 180
            last_txt, stable = "", 0
            while time.time() < deadline:
                page.wait_for_timeout(1200)
                cur = self._last_reply(page, prompt)
                if cur and cur == last_txt:
                    stable += 1
                    if stable >= 3 and cur:
                        break
                else:
                    stable, last_txt = 0, cur
            return {"ok": bool(last_txt), "reply": last_txt[:12000]}

    def cleanup(self) -> dict:
        import urllib.error as _e
        import urllib.request as _u

        tok = ""
        if SESSION_FILE.exists():
            tok = json.loads(SESSION_FILE.read_text(encoding="utf-8")).get("token", "")
        results = {}
        for ref, cid in list(self.chats.items()):
            try:
                r = _u.Request(
                    f"{BASE}/api/v1/chats/{cid}",
                    method="DELETE",
                    headers={"Authorization": "Bearer " + tok},
                )
                with _u.urlopen(r, timeout=20) as resp:
                    results[ref] = resp.status
            except _e.HTTPError as e:
                results[ref] = e.code
            except Exception as e:
                results[ref] = str(e)[:60]
            self.chats.pop(ref, None)
        return {"deleted": results}

    def status(self) -> dict:
        try:
            page = self.ensure()
            return {
                "browser": True,
                "page": page.url[:120],
                "conversations": len(self.chats),
                "looks_logged_in": page.locator("text=New Chat").count() > 0,
            }
        except Exception as e:
            return {"browser": False, "error": str(e)[:200]}

    def idle_reaper(self):
        while True:
            time.sleep(60)
            with self._lock:
                if (
                    self._pw
                    and self._last_used
                    and time.time() - self._last_used > IDLE_KILL_S
                ):
                    try:
                        self._browser.close()
                    except Exception:
                        pass
                    try:
                        self._pw.stop()
                    except Exception:
                        pass
                    self._pw = self._browser = self._page = None


ENGINE = Engine()


def _tools():
    return [
        {
            "name": "glm_chat",
            "description": "Chat with free consumer GLM (chat.z.ai web lane, GLM-5.3-Flash class). "
            "mode: flash (fast) | think (Deep Think) | max (Deep Think+Max). "
            "web_search=true enables search. chat=<ref> continues that conversation.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string"},
                    "mode": {"type": "string", "enum": ["flash", "think", "max"]},
                    "web_search": {"type": "boolean"},
                    "chat": {"type": "string"},
                },
                "required": ["prompt"],
            },
        },
        {
            "name": "glm_stream",
            "description": "glm_chat with streaming partials via MCP progress notifications.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string"},
                    "mode": {"type": "string", "enum": ["flash", "think", "max"]},
                },
                "required": ["prompt"],
            },
        },
        {
            "name": "glm_conversations",
            "description": "List live conversation refs usable as the chat= argument.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "glm_status",
            "description": "Engine/profile health for the free GLM lane.",
            "inputSchema": {"type": "object", "properties": {}},
        },
    ]


def run_mcp_stdio():
    def send(msg):
        sys.stdout.write(json.dumps(msg) + "\n")
        sys.stdout.flush()

    for line in sys.stdin:
        try:
            m = json.loads(line)
        except Exception:
            continue
        mid, method = m.get("id"), m.get("method")
        if method == "initialize":
            send(
                {
                    "jsonrpc": "2.0",
                    "id": mid,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "zai-lane-a", "version": "2.0"},
                    },
                }
            )
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": mid, "result": {"tools": _tools()}})
        elif method == "tools/call":
            p = m.get("params") or {}
            name, args = p.get("name"), p.get("arguments") or {}
            try:
                if name == "glm_chat":
                    out = ENGINE.chat(
                        str(args.get("prompt", "")),
                        mode=args.get("mode", "flash"),
                        web_search=bool(args.get("web_search", False)),
                        chat_ref=args.get("chat"),
                    )
                    send(
                        {
                            "jsonrpc": "2.0",
                            "id": mid,
                            "result": {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": out.get("reply") or json.dumps(out),
                                    }
                                ],
                                "isError": not out.get("ok"),
                            },
                        }
                    )
                elif name == "glm_stream":
                    token = (p.get("_meta") or {}).get("progressToken")

                    def prog(t, token=token):
                        send(
                            {
                                "jsonrpc": "2.0",
                                "method": "notifications/progress",
                                "params": {"progressToken": token, "message": t[:600]},
                            }
                        )

                    out = ENGINE.chat(
                        str(args.get("prompt", "")),
                        mode=args.get("mode", "flash"),
                        on_progress=prog,
                    )
                    send(
                        {
                            "jsonrpc": "2.0",
                            "id": mid,
                            "result": {
                                "content": [
                                    {"type": "text", "text": out.get("reply", "")}
                                ]
                            },
                        }
                    )
                elif name == "glm_vision":
                    out = ENGINE.vision(
                        str(args.get("prompt", "")), str(args.get("image_path", ""))
                    )
                    send(
                        {
                            "jsonrpc": "2.0",
                            "id": mid,
                            "result": {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": out.get("reply") or json.dumps(out),
                                    }
                                ],
                                "isError": not out.get("ok"),
                            },
                        }
                    )
                elif name == "glm_cleanup":
                    send(
                        {
                            "jsonrpc": "2.0",
                            "id": mid,
                            "result": {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": json.dumps(ENGINE.cleanup()),
                                    }
                                ]
                            },
                        }
                    )
                elif name == "glm_conversations":
                    send(
                        {
                            "jsonrpc": "2.0",
                            "id": mid,
                            "result": {
                                "content": [
                                    {"type": "text", "text": json.dumps(ENGINE.chats)}
                                ]
                            },
                        }
                    )
                elif name == "glm_status":
                    send(
                        {
                            "jsonrpc": "2.0",
                            "id": mid,
                            "result": {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": json.dumps(ENGINE.status()),
                                    }
                                ]
                            },
                        }
                    )
                else:
                    send(
                        {
                            "jsonrpc": "2.0",
                            "id": mid,
                            "error": {"code": -32602, "message": "unknown tool"},
                        }
                    )
            except Exception as e:
                send(
                    {
                        "jsonrpc": "2.0",
                        "id": mid,
                        "result": {
                            "content": [{"type": "text", "text": f"[ERROR] {e}"}],
                            "isError": True,
                        },
                    }
                )


def run_http(port: int):
    from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_POST(self):
            if self.path.rstrip("/") not in (
                "/v1/chat/completions",
                "/chat/completions",
            ):
                self.send_response(404)
                self.end_headers()
                return
            body = json.loads(
                self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}"
            )
            model = body.get("model", "glm-web")
            mode = (
                "max"
                if model.endswith("-max")
                else "think"
                if model.endswith("-think")
                else "flash"
            )
            msgs = body.get("messages", [])
            prompt = "\n".join(
                (
                    m.get("content")
                    if isinstance(m.get("content"), str)
                    else " ".join(
                        pp.get("text", "")
                        for pp in m.get("content") or []
                        if isinstance(pp, dict)
                    )
                )
                for m in msgs
                if m.get("role") == "user"
            )
            out = ENGINE.chat(prompt or "", mode=mode)
            rid = "chatcmpl-" + uuid.uuid4().hex[:12]
            if not body.get("stream"):
                resp = {
                    "id": rid,
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": out.get("reply", ""),
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                    },
                }
                data = json.dumps(resp).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            first = True
            reply = out.get("reply", "")
            for cs in range(0, len(reply), 120):
                piece = reply[cs : cs + 120]
                delta = ({"role": "assistant"} if first else {}) | {"content": piece}
                first = False
                evt = {
                    "id": rid,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [{"index": 0, "delta": delta}],
                }
                self.wfile.write(f"data: {json.dumps(evt)}\n\n".encode())
                self.wfile.flush()
            self.wfile.write(b"data: [DONE]\n\n")

        def log_message(self, *a):
            pass

    print(f"zai-lane-a v2 HTTP bridge on :{port} (stream + non-stream)", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()


def run_login():
    os.environ["ZAI_LANE_A_HEADED"] = "1"
    page = ENGINE.ensure()
    page.goto(BASE + "/", wait_until="domcontentloaded")
    print("Browser opened (headed). Log in, then press Enter here.")
    input()
    print("Profile saved at", PROFILE)


if __name__ == "__main__":
    threading.Thread(target=ENGINE.idle_reaper, daemon=True).start()
    mode = sys.argv[1] if len(sys.argv) > 1 else "mcp"
    if mode == "mcp":
        run_mcp_stdio()
    elif mode == "http":
        run_http(int(sys.argv[2]) if len(sys.argv) > 2 else 18319)
    elif mode == "login":
        run_login()
    else:
        print(__doc__)
