"""Smoke test: browser_open -> browser_go -> get_text -> close, via SessionManager + BrowserDaemon."""
import asyncio, json

from nodriver_proxy_mcp.browser.session_manager import session_manager


async def main():
    r = session_manager.open("default", headless=True)  # no proxy, plain connect test
    print("open():", r)
    if r.get("status") not in ("ready", "already_open"):
        return

    go = await session_manager.send("default", "go", {"url": "https://example.com"})
    print("go():", json.dumps(go)[:200])

    txt = await session_manager.send("default", "get_text", {"selector": "h1"})
    print("get_text(h1):", json.dumps(txt)[:200])

    title = await session_manager.send("default", "get_text", {"selector": "title"})
    print("get_text(title):", json.dumps(title)[:200])

    print("close():", session_manager.close())

asyncio.run(main())
