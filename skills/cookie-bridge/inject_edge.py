#!/usr/bin/env python3
"""Inject cookies into PC Edge on port 9225."""

import json
import socket
import asyncio
import time
import websockets
from pathlib import Path

PORT = 9225


def http_get(path, timeout=10):
    s = socket.create_connection(("127.0.0.1", PORT), timeout=timeout)
    s.send(
        f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{PORT}\r\nConnection: close\r\n\r\n".encode()
    )
    chunks = []
    while True:
        try:
            d = s.recv(65536)
            if not d:
                break
            chunks.append(d)
        except socket.timeout:
            break
    s.close()
    raw = b"".join(chunks).decode(errors="replace")
    return raw.split("\r\n\r\n", 1)[1] if "\r\n\r\n" in raw else raw


async def inject():
    data = json.loads(
        (Path.home() / ".crcp/cookie-bridge/chatgpt_cookies.json").read_text()
    )
    cookies = data["cookies"]
    print(f"Loaded {len(cookies)} cookies from phone extraction")

    # Get tab list
    tabs = json.loads(http_get("/json"))
    tab = tabs[0]  # about:blank tab
    ws_url = tab["webSocketDebuggerUrl"]
    print(f"Target tab: {tab['url']}")

    async with websockets.connect(ws_url, max_size=2**20, open_timeout=10) as ws:
        # Enable Network domain
        await ws.send(json.dumps({"id": 1, "method": "Network.enable"}))
        await asyncio.wait_for(ws.recv(), timeout=5)

        # Inject each cookie
        ok = 0
        fail = 0
        for i, c in enumerate(cookies):
            params = {
                "name": c["name"],
                "value": c["value"],
                "domain": c.get("domain", ".chatgpt.com"),
                "path": c.get("path", "/"),
                "secure": c.get("secure", True),
                "httpOnly": c.get("httpOnly", False),
            }
            # Make session cookies persistent (30 days)
            if c.get("expires", -1) > 0:
                params["expires"] = c["expires"]
            else:
                params["expires"] = time.time() + (30 * 24 * 3600)

            await ws.send(
                json.dumps(
                    {"id": 10 + i, "method": "Network.setCookie", "params": params}
                )
            )
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            success = resp.get("result", {}).get("success", False)
            if success:
                ok += 1
            else:
                fail += 1
                print(f"  FAIL: {c['name']} @ {c.get('domain')} → {resp.get('result')}")

        print(f"\nInjected: {ok}/{ok + fail} cookies")

        # Navigate to ChatGPT
        print("Navigating to chatgpt.com...")
        await ws.send(
            json.dumps(
                {
                    "id": 999,
                    "method": "Page.navigate",
                    "params": {"url": "https://chatgpt.com/"},
                }
            )
        )
        await asyncio.wait_for(ws.recv(), timeout=10)

        # Wait for page load
        await asyncio.sleep(5)

        # Check if logged in
        await ws.send(
            json.dumps(
                {
                    "id": 1000,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": "JSON.stringify({title: document.title, url: location.href, cookie_count: document.cookie.split(';').length})",
                        "returnByValue": True,
                    },
                }
            )
        )
        r = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        state = r.get("result", {}).get("result", {}).get("value", "{}")
        print(f"\nPage state: {state}")
        print("\n✅ Check the Edge window — ChatGPT should be loaded!")


asyncio.run(inject())
