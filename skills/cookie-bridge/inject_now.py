#!/usr/bin/env python3
"""Inject saved cookies into already-running PC Chrome on port 9224."""
import json, socket, asyncio, time, sys
import websockets

def http_get_raw(port, path, timeout=10):
    s = socket.create_connection(("127.0.0.1", port), timeout=timeout)
    s.send(f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n".encode())
    chunks = []
    while True:
        try:
            d = s.recv(65536)
            if not d: break
            chunks.append(d)
        except socket.timeout: break
    s.close()
    raw = b"".join(chunks).decode(errors="replace")
    return raw.split("\r\n\r\n", 1)[1] if "\r\n\r\n" in raw else raw

async def inject():
    from pathlib import Path
    cookie_file = Path.home() / ".crcp" / "cookie-bridge" / "chatgpt_cookies.json"
    data = json.loads(cookie_file.read_text(encoding="utf-8"))
    cookies = data["cookies"]
    print(f"Loaded {len(cookies)} cookies")
    
    # Get browser WebSocket URL
    version = json.loads(http_get_raw(9224, "/json/version"))
    browser_ws = version["webSocketDebuggerUrl"]
    print(f"Browser: {version['Browser']}")
    print(f"Connecting to browser WS: {browser_ws}")
    
    async with websockets.connect(browser_ws, max_size=2**22, open_timeout=10) as ws:
        # Create a new tab navigating to chatgpt.com
        await ws.send(json.dumps({
            "id": 1, "method": "Target.createTarget",
            "params": {"url": "about:blank"}
        }))
        r = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        target_id = r.get("result", {}).get("targetId")
        print(f"Created tab: {target_id}")
        
        # Inject cookies at browser level (no need for tab-specific connection)
        injected = 0
        failed = 0
        for i, c in enumerate(cookies):
            params = {
                "name": c["name"],
                "value": c["value"],
                "domain": c.get("domain", ".chatgpt.com"),
                "path": c.get("path", "/"),
                "secure": c.get("secure", True),
                "httpOnly": c.get("httpOnly", False),
            }
            # Convert sameSite 
            ss = c.get("sameSite", "Lax")
            if ss in ("Strict", "Lax", "None"):
                params["sameSite"] = ss
            
            # Make ALL cookies persistent (30 days)
            if c.get("expires", -1) > 0:
                params["expires"] = c["expires"]
            else:
                params["expires"] = time.time() + (30 * 24 * 3600)
            
            await ws.send(json.dumps({
                "id": 100 + i,
                "method": "Storage.setCookie",
                "params": cookie_params_to_storage(params)
            }))
            try:
                resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                if resp.get("result", {}).get("success", True) and "error" not in resp:
                    injected += 1
                else:
                    # Try Network.setCookie via browser target
                    failed += 1
            except:
                failed += 1
        
        print(f"First pass: {injected} ok, {failed} failed")
        
        # Navigate the tab to chatgpt.com now that cookies are set
        # Get the tab's WS URL
        tabs_raw = http_get_raw(9224, "/json")
        tabs = json.loads(tabs_raw)
        
        chatgpt_tab = None
        for t in tabs:
            if t.get("id") == target_id or "about:blank" in t.get("url", ""):
                chatgpt_tab = t
                break
        
        if chatgpt_tab:
            print(f"Navigating tab to chatgpt.com...")
            tab_ws = chatgpt_tab["webSocketDebuggerUrl"]
            async with websockets.connect(tab_ws, max_size=2**20, open_timeout=10) as tws:
                # Also set cookies via Network.setCookie on this target
                for i, c in enumerate(cookies):
                    params = {
                        "name": c["name"],
                        "value": c["value"],
                        "domain": c.get("domain", ".chatgpt.com"),
                        "path": c.get("path", "/"),
                        "secure": c.get("secure", True),
                        "httpOnly": c.get("httpOnly", False),
                    }
                    if c.get("expires", -1) > 0:
                        params["expires"] = c["expires"]
                    else:
                        params["expires"] = time.time() + (30 * 24 * 3600)
                    
                    await tws.send(json.dumps({
                        "id": 200 + i,
                        "method": "Network.setCookie",
                        "params": params
                    }))
                    resp = json.loads(await asyncio.wait_for(tws.recv(), timeout=5))
                
                print(f"Cookies set on tab. Navigating...")
                await tws.send(json.dumps({
                    "id": 999,
                    "method": "Page.navigate",
                    "params": {"url": "https://chatgpt.com/"}
                }))
                await asyncio.wait_for(tws.recv(), timeout=10)
                print("✅ Done! Check your PC Chrome — ChatGPT should be loaded with your session.")

def cookie_params_to_storage(params):
    """Fallback conversion."""
    return params

asyncio.run(inject())
