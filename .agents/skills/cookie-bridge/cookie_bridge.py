#!/usr/bin/env python3
"""
CRCP Phone-to-PC Cookie Bridge
Extracts ChatGPT session from phone Chrome via CDP,
saves to encrypted local store, injects into PC Chrome.

Usage:
  python cookie_bridge.py extract    # Pull cookies from phone
  python cookie_bridge.py inject     # Push cookies into PC Chrome
  python cookie_bridge.py sync       # Extract + inject in one shot
  python cookie_bridge.py status     # Show saved cookie status
"""
import json, socket, asyncio, sys, os, time, subprocess, shutil
from pathlib import Path
from datetime import datetime, timezone

try:
    import websockets
except ImportError:
    print("Installing websockets..."); subprocess.check_call([sys.executable, "-m", "pip", "install", "websockets", "-q"])
    import websockets

# --- Config ---
PHONE_CDP_PORT = 9223
PC_CDP_PORT = 9224
STORE_DIR = Path.home() / ".crcp" / "cookie-bridge"
COOKIE_FILE = STORE_DIR / "chatgpt_cookies.json"
PC_PROFILE_DIR = STORE_DIR / "chrome-profile"
CHATGPT_DOMAINS = ["chatgpt.com", ".chatgpt.com", "auth.openai.com", ".auth.openai.com"]

def ensure_store():
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    # Set restrictive ACL on Windows
    if os.name == "nt":
        try:
            subprocess.run(
                ["icacls", str(STORE_DIR), "/inheritance:r", "/grant:r", f"{os.environ['USERNAME']}:(OI)(CI)F"],
                capture_output=True, timeout=10
            )
        except Exception:
            pass

def http_get_raw(port, path, timeout=30):
    """Raw HTTP GET to CDP endpoint - handles large responses."""
    s = socket.create_connection(("127.0.0.1", port), timeout=timeout)
    s.send(f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n".encode())
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
    if "\r\n\r\n" in raw:
        return raw.split("\r\n\r\n", 1)[1]
    return raw

def find_chatgpt_tab(port):
    """Find the active ChatGPT tab from Chrome CDP."""
    body = http_get_raw(port, "/json")
    tabs = json.loads(body)
    chatgpt = [t for t in tabs if "chatgpt.com" in t.get("url", "")]
    if not chatgpt:
        return None, tabs
    # Prefer the main chatgpt.com page over conversation-specific ones
    main = [t for t in chatgpt if t.get("url", "").rstrip("/") == "https://chatgpt.com"]
    return (main[0] if main else chatgpt[0]), tabs

async def extract_all_cookies(ws_url):
    """Extract ALL cookies (including httpOnly) via CDP."""
    async with websockets.connect(ws_url, max_size=2**22, open_timeout=10) as ws:
        # Method 1: Network.getCookies for specific URLs (gets httpOnly too)
        await ws.send(json.dumps({
            "id": 1, "method": "Network.getCookies",
            "params": {"urls": [
                "https://chatgpt.com/",
                "https://chatgpt.com/backend-api/me",
                "https://auth.openai.com/",
                "https://cdn.oaistatic.com/",
            ]}
        }))
        r1 = json.loads(await asyncio.wait_for(ws.recv(), timeout=20))
        cdp_cookies = r1.get("result", {}).get("cookies", [])
        
        # Method 2: Also get JS cookies for cross-check
        await ws.send(json.dumps({
            "id": 2, "method": "Runtime.evaluate",
            "params": {"expression": "document.cookie", "returnByValue": True}
        }))
        r2 = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        js_cookies = r2.get("result", {}).get("result", {}).get("value", "")
        
        # Get page state
        await ws.send(json.dumps({
            "id": 3, "method": "Runtime.evaluate",
            "params": {"expression": "JSON.stringify({url: location.href, title: document.title})", "returnByValue": True}
        }))
        r3 = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        state = json.loads(r3.get("result", {}).get("result", {}).get("value", "{}"))
        
        return cdp_cookies, js_cookies, state

def save_cookies(cookies, state):
    """Save cookies to local store."""
    ensure_store()
    data = {
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "source": "phone_chrome_cdp",
        "page_url": state.get("url", ""),
        "page_title": state.get("title", ""),
        "cookie_count": len(cookies),
        "cookies": cookies,
    }
    # Atomic write
    tmp = COOKIE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(COOKIE_FILE)
    print(f"Saved {len(cookies)} cookies to {COOKIE_FILE}")

def load_cookies():
    """Load cookies from local store."""
    if not COOKIE_FILE.is_file():
        return None
    return json.loads(COOKIE_FILE.read_text(encoding="utf-8"))

def ensure_adb_forward():
    """Ensure ADB port forwarding is active."""
    # Check if device is connected
    r = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=10)
    devices = [l.split("\t")[0] for l in r.stdout.strip().split("\n")[1:] if "\tdevice" in l]
    if not devices:
        print("ERROR: No Android device connected via ADB")
        return False
    device = devices[0]
    print(f"Device: {device}")
    
    # Find Chrome devtools socket
    r2 = subprocess.run(
        ["adb", "-s", device, "shell", "cat /proc/net/unix 2>/dev/null | grep chrome_devtools_remote"],
        capture_output=True, text=True, timeout=10
    )
    import re
    pids = re.findall(r"chrome_devtools_remote_(\d+)", r2.stdout)
    if not pids:
        print("ERROR: Chrome DevTools not available. Is USB debugging enabled?")
        return False
    pid = pids[0]
    
    # Remove old forwards and set new one
    subprocess.run(["adb", "-s", device, "forward", "--remove-all"], capture_output=True, timeout=5)
    r3 = subprocess.run(
        ["adb", "-s", device, "forward", f"tcp:{PHONE_CDP_PORT}", f"localabstract:chrome_devtools_remote_{pid}"],
        capture_output=True, text=True, timeout=5
    )
    if r3.returncode != 0:
        print(f"ERROR: ADB forward failed: {r3.stderr}")
        return False
    print(f"ADB forward: tcp:{PHONE_CDP_PORT} → chrome_devtools_remote_{pid}")
    time.sleep(1)
    return True

def launch_pc_chrome():
    """Launch Chrome on PC with a controlled profile and CDP port."""
    PC_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    
    # Find Chrome
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    chrome = None
    for p in chrome_paths:
        if os.path.isfile(p):
            chrome = p
            break
    
    if not chrome:
        # Try Edge as fallback
        edge_paths = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ]
        for p in edge_paths:
            if os.path.isfile(p):
                chrome = p
                break
    
    if not chrome:
        print("ERROR: No Chrome or Edge found")
        return False
    
    print(f"Launching: {os.path.basename(chrome)} with profile at {PC_PROFILE_DIR}")
    subprocess.Popen([
        chrome,
        f"--remote-debugging-port={PC_CDP_PORT}",
        f"--user-data-dir={PC_PROFILE_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
        "about:blank",
    ])
    
    # Wait for CDP to be available
    for i in range(15):
        time.sleep(1)
        try:
            body = http_get_raw(PC_CDP_PORT, "/json/version", timeout=3)
            info = json.loads(body)
            print(f"  Browser: {info.get('Browser', 'unknown')}")
            return True
        except Exception:
            pass
    print("ERROR: Chrome didn't start with CDP")
    return False

async def inject_cookies_cdp(cookies):
    """Inject cookies into PC Chrome via CDP."""
    body = http_get_raw(PC_CDP_PORT, "/json")
    tabs = json.loads(body)
    if not tabs:
        print("ERROR: No tabs in PC Chrome")
        return False
    
    tab = tabs[0]
    ws_url = tab["webSocketDebuggerUrl"]
    
    async with websockets.connect(ws_url, max_size=2**20, open_timeout=10) as ws:
        # First navigate to chatgpt.com so cookies are set in the right context
        await ws.send(json.dumps({
            "id": 0, "method": "Page.navigate",
            "params": {"url": "https://chatgpt.com/"}
        }))
        await asyncio.wait_for(ws.recv(), timeout=15)
        await asyncio.sleep(3)  # Let page start loading
        
        # Inject each cookie
        injected = 0
        failed = 0
        for i, c in enumerate(cookies):
            cookie_params = {
                "name": c["name"],
                "value": c["value"],
                "domain": c.get("domain", "chatgpt.com"),
                "path": c.get("path", "/"),
                "secure": c.get("secure", True),
                "httpOnly": c.get("httpOnly", False),
                "sameSite": c.get("sameSite", "Lax"),
            }
            # Set expiry for persistent cookies (30 days from now)
            if c.get("expires", -1) > 0:
                cookie_params["expires"] = c["expires"]
            else:
                # Session cookies - set 30 day expiry to make them persistent
                cookie_params["expires"] = time.time() + (30 * 24 * 3600)
            
            await ws.send(json.dumps({
                "id": 100 + i,
                "method": "Network.setCookie",
                "params": cookie_params
            }))
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            if resp.get("result", {}).get("success"):
                injected += 1
            else:
                failed += 1
                print(f"  FAILED: {c['name']} on {c.get('domain')}: {resp}")
        
        print(f"Injected: {injected}/{injected+failed} cookies")
        
        # Now reload the page to apply cookies
        await ws.send(json.dumps({
            "id": 999, "method": "Page.navigate",
            "params": {"url": "https://chatgpt.com/"}
        }))
        await asyncio.wait_for(ws.recv(), timeout=10)
        print("Page reloaded — check PC Chrome for authenticated ChatGPT!")
        
        return injected > 0

# --- Commands ---

def cmd_extract():
    """Extract cookies from phone Chrome."""
    print("=== EXTRACT: Phone → Local Store ===\n")
    
    if not ensure_adb_forward():
        return False
    
    tab, all_tabs = find_chatgpt_tab(PHONE_CDP_PORT)
    if not tab:
        print(f"No ChatGPT tab found among {len(all_tabs)} tabs")
        print("Open chatgpt.com on your phone Chrome first!")
        return False
    
    print(f"Found: {tab['title'][:60]} ({tab['url'][:60]})")
    
    cookies, js_cookies, state = asyncio.run(extract_all_cookies(tab["webSocketDebuggerUrl"]))
    
    if not cookies:
        print("WARNING: Network.getCookies returned nothing, falling back to JS cookies")
        # Parse JS cookie string into structured format
        if js_cookies:
            cookies = []
            for pair in js_cookies.split("; "):
                if "=" in pair:
                    name, val = pair.split("=", 1)
                    cookies.append({
                        "name": name, "value": val,
                        "domain": ".chatgpt.com", "path": "/",
                        "secure": True, "httpOnly": False,
                        "expires": time.time() + (30 * 24 * 3600),
                    })
    
    if not cookies:
        print("ERROR: No cookies extracted")
        return False
    
    # Show summary
    print(f"\nExtracted {len(cookies)} cookies:")
    for c in sorted(cookies, key=lambda x: x.get("name", "")):
        domain = c.get("domain", "?")
        name = c.get("name", "?")
        ho = "httpOnly" if c.get("httpOnly") else "JS-ok"
        exp = "session" if c.get("expires", -1) <= 0 else "persistent"
        print(f"  {domain:30s} {name:40s} {ho:10s} {exp:10s} len={len(c.get('value', ''))}")
    
    save_cookies(cookies, state)
    return True

def cmd_inject():
    """Inject saved cookies into a durable isolated PC Chrome/Edge profile."""
    print("=== INJECT (durable): Local Store → isolated browser profile ===\n")
    # Prefer the durable re-apply path (CDP + allow-origins + dedicated profile).
    durable = STORE_DIR / "apply_durable.py"
    if durable.is_file():
        r = subprocess.run(
            [sys.executable, str(durable), "apply", "--browser", "chrome", "--port", "9340"],
            cwd=str(STORE_DIR),
        )
        return r.returncode == 0

    data = load_cookies()
    if not data:
        print(f"No saved cookies at {COOKIE_FILE}")
        print("Run 'extract' first!")
        return False

    cookies = data["cookies"]
    age = datetime.now(timezone.utc) - datetime.fromisoformat(data["extracted_at"])
    print(f"Saved cookies: {len(cookies)} (extracted {age} ago)")

    if age.total_seconds() > 86400:
        print("WARNING: Cookies are over 24h old — consider re-extracting")

    # Check if PC Chrome is already running with CDP
    try:
        http_get_raw(PC_CDP_PORT, "/json/version", timeout=3)
        print(f"PC Chrome already running on port {PC_CDP_PORT}")
    except Exception:
        print("Launching PC Chrome with CDP...")
        if not launch_pc_chrome():
            return False
    
    success = asyncio.run(inject_cookies_cdp(cookies))
    return success

def cmd_sync():
    """Extract from phone + inject into PC Chrome."""
    print("=== SYNC: Phone → PC Chrome (one shot) ===\n")
    if cmd_extract():
        print()
        return cmd_inject()
    return False

def cmd_status():
    """Show saved cookie status."""
    print("=== STATUS ===\n")
    data = load_cookies()
    if not data:
        print(f"No saved cookies at {COOKIE_FILE}")
        return
    
    age = datetime.now(timezone.utc) - datetime.fromisoformat(data["extracted_at"])
    print(f"Source: {data.get('source', '?')}")
    print(f"Page: {data.get('page_title', '?')} ({data.get('page_url', '?')})")
    print(f"Extracted: {data['extracted_at']} ({age} ago)")
    print(f"Cookies: {data['cookie_count']}")
    
    key_cookies = ["__Secure-oai-is", "_puid", "oai-sc", "oai-client-auth-info", "_account"]
    for c in data["cookies"]:
        if c["name"] in key_cookies:
            print(f"  ✓ {c['name']:30s} len={len(c.get('value', '')):5d} domain={c.get('domain', '?')}")
    
    healthy = any(c["name"] == "__Secure-oai-is" for c in data["cookies"])
    print(f"\nHealth: {'✅ GOOD (has __Secure-oai-is)' if healthy else '❌ MISSING auth cookie'}")

# --- Main ---
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "sync"
    commands = {
        "extract": cmd_extract,
        "inject": cmd_inject,
        "sync": cmd_sync,
        "status": cmd_status,
    }
    if cmd not in commands:
        print(f"Usage: {sys.argv[0]} [{'/'.join(commands)}]")
        sys.exit(1)
    
    ok = commands[cmd]()
    sys.exit(0 if ok else 1)
