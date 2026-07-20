#!/usr/bin/env python3
"""Durable, re-applicable ChatGPT cookie apply (phone store → PC browser).

Uses an isolated Chromium profile + CDP (not the user's daily Chrome instance).
Re-run anytime after extract:

  python apply_durable.py status
  python apply_durable.py apply
  python apply_durable.py apply --port 9340 --browser edge
  python apply_durable.py verify

Cookies stay under ~/.crcp/cookie-bridge/ with restrictive ACLs.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STORE = Path.home() / ".crcp" / "cookie-bridge"
COOKIE_FILE = STORE / "chatgpt_cookies.json"
STATE_FILE = STORE / "apply_state.json"
CHROME_PROFILE = STORE / "chrome-durable-profile"
EDGE_PROFILE = STORE / "edge-durable-profile"
DEFAULT_PORT = 9340


def _ensure_store() -> None:
    STORE.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        try:
            subprocess.run(
                [
                    "icacls",
                    str(STORE),
                    "/inheritance:r",
                    "/grant:r",
                    f"{os.environ.get('USERNAME', '')}:(OI)(CI)F",
                ],
                capture_output=True,
                timeout=15,
                check=False,
            )
        except Exception:
            pass


def load_store() -> dict[str, Any]:
    if not COOKIE_FILE.is_file():
        raise SystemExit(f"missing cookie store: {COOKIE_FILE} — run extract first")
    return json.loads(COOKIE_FILE.read_text(encoding="utf-8"))


def status() -> dict[str, Any]:
    if not COOKIE_FILE.is_file():
        return {"ok": False, "error": "no cookie store"}
    data = load_store()
    cookies = data.get("cookies") or []
    names = sorted({c.get("name") for c in cookies if isinstance(c, dict)})
    report = {
        "ok": True,
        "cookie_file": str(COOKIE_FILE),
        "extracted_at": data.get("extracted_at"),
        "source": data.get("source"),
        "page_url": data.get("page_url"),
        "cookie_count": len(cookies),
        "has_nextauth_session": any(
            (n or "").startswith("__Secure-next-auth.session-token") for n in names
        ),
        "has_oai_is": "__Secure-oai-is" in names,
        "has_cf_clearance": "cf_clearance" in names,
        "has_client_auth": "oai-client-auth-session" in names,
        "names": names,
        "age_hours": None,
        "last_apply": None,
    }
    try:
        ts = datetime.fromisoformat(str(data.get("extracted_at")).replace("Z", "+00:00"))
        report["age_hours"] = round(
            (datetime.now(timezone.utc) - ts).total_seconds() / 3600, 2
        )
    except Exception:
        pass
    if STATE_FILE.is_file():
        try:
            report["last_apply"] = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return report


def _find_browser(kind: str) -> str:
    local = os.environ.get("LOCALAPPDATA", "")
    pf = os.environ.get("PROGRAMFILES", r"C:\Program Files")
    pf86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
    if kind == "edge":
        candidates = [
            rf"{pf}\Microsoft\Edge\Application\msedge.exe",
            rf"{pf86}\Microsoft\Edge\Application\msedge.exe",
            rf"{local}\Microsoft\Edge\Application\msedge.exe",
        ]
    else:
        candidates = [
            rf"{pf}\Google\Chrome\Application\chrome.exe",
            rf"{pf86}\Google\Chrome\Application\chrome.exe",
            rf"{local}\Google\Chrome\Application\chrome.exe",
        ]
    for path in candidates:
        if path and Path(path).is_file():
            return path
    raise SystemExit(f"{kind} browser executable not found")


def _port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1.0):
            return True
    except OSError:
        return False


def _http_json(port: int, path: str, timeout: float = 10.0) -> Any:
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        headers={"Host": f"127.0.0.1:{port}", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def wait_cdp(port: int, timeout_s: float = 40.0) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    last: Exception | None = None
    while time.time() < deadline:
        try:
            return _http_json(port, "/json/version")
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(0.4)
    raise SystemExit(f"CDP not ready on :{port}: {type(last).__name__ if last else 'timeout'}")


def launch_browser(kind: str, port: int, profile: Path) -> dict[str, Any]:
    profile.mkdir(parents=True, exist_ok=True)
    exe = _find_browser(kind)
    if _port_open(port):
        # Assume it's our previous session if version responds
        try:
            ver = wait_cdp(port, timeout_s=3)
            return {
                "ok": True,
                "reused": True,
                "pid": None,
                "port": port,
                "exe": exe,
                "browser": ver.get("Browser"),
            }
        except SystemExit:
            pass
    args = [
        exe,
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-sync",
        "--disable-background-networking",
        "about:blank",
    ]
    proc = subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    ver = wait_cdp(port)
    return {
        "ok": True,
        "reused": False,
        "pid": proc.pid,
        "port": port,
        "exe": exe,
        "browser": ver.get("Browser"),
        "profile": str(profile),
    }


class Cdp:
    def __init__(self, port: int):
        try:
            import websocket  # type: ignore
        except ImportError:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "websocket-client", "-q"]
            )
            import websocket  # type: ignore
        self._ws_mod = websocket
        ver = wait_cdp(port)
        ws_url = ver.get("webSocketDebuggerUrl")
        if not ws_url:
            raise SystemExit("no browser webSocketDebuggerUrl")
        self.ws = websocket.create_connection(ws_url, timeout=30, suppress_origin=True)
        self._id = 0
        self.session_id: str | None = None
        self.version = ver

    def close(self) -> None:
        try:
            self.ws.close()
        except Exception:
            pass

    def call(self, method: str, params: dict | None = None, *, session: bool = False) -> Any:
        self._id += 1
        msg: dict[str, Any] = {"id": self._id, "method": method}
        if params:
            msg["params"] = params
        if session and self.session_id:
            msg["sessionId"] = self.session_id
        self.ws.send(json.dumps(msg))
        deadline = time.time() + 45
        while time.time() < deadline:
            data = json.loads(self.ws.recv())
            if data.get("id") == self._id:
                if data.get("error"):
                    raise RuntimeError(f"{method}: {data['error']}")
                return data.get("result")
        raise TimeoutError(method)

    def attach_page(self) -> None:
        infos = (self.call("Target.getTargets") or {}).get("targetInfos") or []
        pages = [t for t in infos if t.get("type") == "page"]
        if not pages:
            created = self.call("Target.createTarget", {"url": "about:blank"}) or {}
            tid = created.get("targetId")
        else:
            tid = pages[0]["targetId"]
        att = self.call("Target.attachToTarget", {"targetId": tid, "flatten": True}) or {}
        self.session_id = att.get("sessionId")
        if not self.session_id:
            raise RuntimeError("no sessionId")


def cookie_to_cdp(c: dict[str, Any]) -> dict[str, Any]:
    name = c["name"]
    domain = c.get("domain") or ".chatgpt.com"
    secure = bool(c.get("secure", True))
    host = domain.lstrip(".")
    out: dict[str, Any] = {
        "name": name,
        "value": c["value"],
        "path": c.get("path") or "/",
        "secure": secure,
        "httpOnly": bool(c.get("httpOnly", False)),
        "url": f"{'https' if secure else 'http'}://{host}/",
    }
    # __Host- cookies cannot carry Domain
    if name.startswith("__Host-"):
        out.pop("domain", None)
        out["url"] = "https://chatgpt.com/"
    else:
        out["domain"] = domain
    ss = c.get("sameSite")
    if ss in ("Strict", "Lax", "None"):
        out["sameSite"] = ss
    elif ss == "no_restriction":
        out["sameSite"] = "None"
    exp = c.get("expires")
    if isinstance(exp, (int, float)) and exp > 0:
        out["expires"] = float(exp)
    else:
        # Make session cookies re-applicable for ~30d
        out["expires"] = time.time() + 30 * 24 * 3600
    return out


def apply_cookies(port: int, cookies: list[dict[str, Any]]) -> dict[str, Any]:
    cdp = Cdp(port)
    try:
        cdp.attach_page()
        cdp.call("Network.enable", session=True)
        cdp.call("Page.enable", session=True)
        # Seed domain origin
        cdp.call("Page.navigate", {"url": "https://chatgpt.com/"}, session=True)
        time.sleep(2.5)
        ok = fail = 0
        names_ok: list[str] = []
        fails: list[str] = []
        for c in cookies:
            try:
                payload = cookie_to_cdp(c)
                result = cdp.call("Network.setCookie", payload, session=True) or {}
                if result.get("success", True):
                    ok += 1
                    names_ok.append(payload["name"])
                else:
                    fail += 1
                    fails.append(payload["name"])
            except Exception as exc:
                fail += 1
                fails.append(f"{c.get('name')}:{type(exc).__name__}")
        # Reload with cookies set
        cdp.call("Page.navigate", {"url": "https://chatgpt.com/"}, session=True)
        time.sleep(4)
        # Probe session
        probe = cdp.call(
            "Runtime.evaluate",
            {
                "expression": """
(async () => {
  const out = {};
  async function hit(k, u) {
    try {
      const r = await fetch(u, {credentials:'include', headers:{'Accept':'application/json'}});
      const ct = r.headers.get('content-type')||'';
      let keys=null, warningOnly=false, hasUser=false, email=null;
      if (ct.includes('json')) {
        const j = await r.json();
        if (j && typeof j==='object' && !Array.isArray(j)) {
          keys = Object.keys(j).slice(0,40);
          warningOnly = keys.length===1 && keys[0]==='WARNING_BANNER';
          hasUser = !!(j.user || j.accessToken || j.expires);
          if (j.user && j.user.email) email = String(j.user.email).slice(0,80);
        }
      }
      out[k] = {status:r.status, keys, warningOnly, hasUser, emailPresent: !!email};
    } catch(e) { out[k] = {error: String(e&&e.message||e).slice(0,120)}; }
  }
  await hit('session','https://chatgpt.com/api/auth/session');
  await hit('me','https://chatgpt.com/backend-api/me');
  return out;
})()
""",
                "awaitPromise": True,
                "returnByValue": True,
                "userGesture": True,
            },
            session=True,
        ) or {}
        value = (probe.get("result") or {}).get("value") or {}
        meta = cdp.call("Network.getAllCookies", session=True) or {}
        all_c = meta.get("cookies") or []
        return {
            "set_ok": ok,
            "set_fail": fail,
            "names_set": sorted(set(names_ok)),
            "fail_sample": fails[:10],
            "probes": value,
            "browser_cookie_count": len(all_c),
            "browser_has_nextauth": any(
                (c.get("name") or "").startswith("__Secure-next-auth.session-token")
                for c in all_c
            ),
            "browser_has_oai_is": any(c.get("name") == "__Secure-oai-is" for c in all_c),
        }
    finally:
        cdp.close()


def apply(
    *,
    browser: str = "chrome",
    port: int = DEFAULT_PORT,
    keep_open: bool = True,
) -> dict[str, Any]:
    _ensure_store()
    data = load_store()
    cookies = data.get("cookies") or []
    profile = EDGE_PROFILE if browser == "edge" else CHROME_PROFILE
    launch = launch_browser(browser, port, profile)
    result = apply_cookies(port, cookies)
    session = result.get("probes", {}).get("session") or {}
    me = result.get("probes", {}).get("me") or {}
    web_logged_in = bool(
        session.get("hasUser")
        or (session.get("status") == 200 and not session.get("warningOnly"))
    )
    api_ok = me.get("status") == 200
    report = {
        "ok": web_logged_in or api_ok,
        "status": (
            "WEB_SESSION_OK"
            if web_logged_in
            else "API_ONLY"
            if api_ok
            else "FAILED"
        ),
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "source_extracted_at": data.get("extracted_at"),
        "launch": {
            k: launch[k]
            for k in ("ok", "reused", "pid", "port", "browser", "profile")
            if k in launch
        },
        "inject": {
            "set_ok": result["set_ok"],
            "set_fail": result["set_fail"],
            "names_set_count": len(result["names_set"]),
            "has_nextauth_in_set": any(
                n.startswith("__Secure-next-auth.session-token") for n in result["names_set"]
            ),
            "has_oai_is_in_set": "__Secure-oai-is" in result["names_set"],
            "fail_sample": result["fail_sample"],
        },
        "probes": result["probes"],
        "browser_cookies": {
            "count": result["browser_cookie_count"],
            "has_nextauth": result["browser_has_nextauth"],
            "has_oai_is": result["browser_has_oai_is"],
        },
        "durable": {
            "cookie_store": str(COOKIE_FILE),
            "profile_dir": str(profile),
            "reapply": f'python "{Path(__file__).resolve()}" apply --browser {browser} --port {port}',
            "extract_again": f'python "{STORE / "cookie_bridge.py"}" extract',
            "note": "Re-extract from phone when cookies expire (~days/weeks). Profile reuses cookies after set.",
        },
        "keep_open": keep_open,
        "cdp": f"http://127.0.0.1:{port}/json",
    }
    STATE_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main(argv: list[str]) -> int:
    _ensure_store()
    if not argv or argv[0] in {"-h", "--help", "help"}:
        print(__doc__)
        return 0
    cmd = argv[0]
    if cmd == "status":
        print(json.dumps(status(), indent=2))
        return 0
    if cmd == "verify":
        st = status()
        last = st.get("last_apply") or {}
        print(json.dumps({"store": st, "last_apply_status": last.get("status")}, indent=2))
        return 0 if st.get("ok") else 1
    if cmd == "apply":
        browser = "chrome"
        port = DEFAULT_PORT
        args = argv[1:]
        i = 0
        while i < len(args):
            if args[i] == "--browser" and i + 1 < len(args):
                browser = args[i + 1]
                i += 2
            elif args[i] == "--port" and i + 1 < len(args):
                port = int(args[i + 1])
                i += 2
            else:
                i += 1
        report = apply(browser=browser, port=port)
        print(json.dumps(report, indent=2))
        return 0 if report.get("ok") else 1
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
