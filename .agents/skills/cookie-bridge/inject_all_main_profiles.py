#!/usr/bin/env python3
"""DEPRECATED — force-kills browsers and rebinds main profiles (caused Jul-20 corruption).

Use instead:
  python safe_main_cookie_inject.py --browser chrome --payload both
  python safe_main_cookie_inject.py --browser edge --payload both

To run THIS legacy script you MUST set env:
  I_ACCEPT_PROFILE_RISK=1

WARNING: taskkill /F + main User Data CDP rebind can thrash prefs/sessions.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STORE = Path.home() / ".crcp" / "cookie-bridge"
COOKIE_FILE = STORE / "chatgpt_cookies.json"
REPORT_FILE = STORE / "inject_all_main_report.json"

TARGETS: dict[str, dict[str, Any]] = {
    "chrome": {
        "kind": "chromium",
        "process_names": ["chrome", "GoogleCrashHandler", "GoogleCrashHandler64"],
        "exe_candidates": [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            str(Path.home() / r"AppData\Local\Google\Chrome\Application\chrome.exe"),
        ],
        # Junction: Chrome blocks CDP on the real default User Data path.
        "user_data": Path.home()
        / r".crcp\cookie-bridge\profile-junctions\chrome-ud",
        "real_user_data": Path.home() / r"AppData\Local\Google\Chrome\User Data",
        "profile_directory": "Default",
        "port": 9351,
        "label": "Chrome Default (Prekzursil / Your Chrome)",
    },
    "edge": {
        "kind": "chromium",
        "process_names": ["msedge", "msedgewebview2"],
        "exe_candidates": [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ],
        "user_data": Path.home()
        / r".crcp\cookie-bridge\profile-junctions\edge-ud",
        "real_user_data": Path.home() / r"AppData\Local\Microsoft\Edge\User Data",
        "profile_directory": "Default",
        "port": 9352,
        "label": "Edge Default",
    },
    "comet": {
        "kind": "chromium",
        "process_names": ["Comet", "comet"],
        "exe_candidates": [
            str(Path.home() / r"AppData\Local\Perplexity\Comet\Application\comet.exe"),
            r"C:\Program Files\Perplexity\Comet\Application\comet.exe",
            r"C:\Program Files\Comet\Application\comet.exe",
        ],
        "user_data": Path.home() / r"AppData\Local\Perplexity\Comet\User Data",
        "profile_directory": "Default",
        "port": 9353,
        "label": "Comet Default (Prekzursil)",
    },
    "firefox": {
        "kind": "firefox",
        "process_names": ["firefox"],
        "exe_candidates": [
            r"C:\Program Files\Mozilla Firefox\firefox.exe",
            r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
        ],
        "profile_path": Path.home()
        / r"AppData\Roaming\Mozilla\Firefox\Profiles\k4cy1nuq.default-release",
        "label": "Firefox default-release",
    },
}


def load_cookies() -> list[dict[str, Any]]:
    data = json.loads(COOKIE_FILE.read_text(encoding="utf-8"))
    cookies = data.get("cookies") or []
    if not cookies:
        raise SystemExit(f"no cookies in {COOKIE_FILE}")
    return cookies


def find_exe(candidates: list[str]) -> str | None:
    for c in candidates:
        if c and Path(c).is_file():
            return c
    return None


def kill_processes(names: list[str]) -> None:
    for name in names:
        subprocess.run(
            ["taskkill", "/F", "/IM", f"{name}.exe", "/T"],
            capture_output=True,
            text=True,
            check=False,
        )
    # Second pass by process name (PowerShell-less)
    time.sleep(1.5)
    for name in names:
        subprocess.run(
            ["taskkill", "/F", "/IM", f"{name}.exe", "/T"],
            capture_output=True,
            text=True,
            check=False,
        )
    time.sleep(2)


def clear_singleton_locks(user_data: Path) -> None:
    """Remove Chromium singleton lock files so a fresh CDP launch can bind the profile."""
    for name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
        path = user_data / name
        try:
            if path.exists() or path.is_symlink() or path.is_file():
                path.unlink(missing_ok=True)  # type: ignore[call-arg]
        except TypeError:
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                pass
        except OSError:
            pass


def port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), 1.0):
            return True
    except OSError:
        return False


def wait_cdp(port: int, timeout: float = 45.0) -> dict[str, Any]:
    deadline = time.time() + timeout
    last: Exception | None = None
    while time.time() < deadline:
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/json/version",
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                return json.loads(resp.read().decode())
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(0.4)
    raise RuntimeError(f"CDP :{port} not ready: {type(last).__name__ if last else 'timeout'}")


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
    if name.startswith("__Host-"):
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
        out["expires"] = time.time() + 30 * 24 * 3600
    return out


class Cdp:
    def __init__(self, port: int):
        try:
            import websocket  # type: ignore
        except ImportError:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "websocket-client", "-q"]
            )
            import websocket  # type: ignore
        ver = wait_cdp(port)
        ws_url = ver.get("webSocketDebuggerUrl")
        if not ws_url:
            raise RuntimeError("no webSocketDebuggerUrl")
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


def inject_chromium(target: dict[str, Any], cookies: list[dict[str, Any]]) -> dict[str, Any]:
    exe = find_exe(target["exe_candidates"])
    if not exe:
        # Discover Comet exe under LocalAppData
        for root in [
            Path.home() / r"AppData\Local\Perplexity",
            Path(r"C:\Program Files"),
            Path(r"C:\Program Files (x86)"),
        ]:
            if root.is_dir():
                for p in root.rglob("*.exe"):
                    if p.name.lower() in {"comet.exe", "perplexity.exe"}:
                        exe = str(p)
                        break
            if exe:
                break
    if not exe:
        return {"ok": False, "error": "executable_not_found", "label": target["label"]}
    user_data = Path(target["user_data"])
    real_ud = Path(target.get("real_user_data") or user_data)
    if not real_ud.is_dir() and not user_data.is_dir():
        return {"ok": False, "error": f"user_data missing: {user_data}", "label": target["label"]}
    # Ensure junction exists for Chrome/Edge default-path CDP ban
    if target.get("real_user_data") and not user_data.exists():
        user_data.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(user_data), str(real_ud)],
            capture_output=True,
            text=True,
            check=False,
        )

    kill_processes(target["process_names"])
    if "chrome" in target["process_names"] or target.get("label", "").startswith("Chrome"):
        kill_processes(["chrome", "GoogleCrashHandler", "GoogleCrashHandler64"])
    clear_singleton_locks(real_ud)
    clear_singleton_locks(user_data)
    port = int(target["port"])
    # Free the port if something stale holds it
    if port_open(port):
        time.sleep(1)
    args = [
        exe,
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        f"--user-data-dir={user_data}",
        f"--profile-directory={target['profile_directory']}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-mode",
        "--disable-features=ChromeWhatsNewUI",
        "about:blank",
    ]
    # Capture stderr for diagnosis if CDP fails
    err_log = Path(tempfile.gettempdir()) / f"crcp_inject_{port}.err"
    err_fh = open(err_log, "w", encoding="utf-8", errors="replace")
    proc = subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=err_fh,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    try:
        wait_cdp(port, timeout=60.0)
    except Exception as exc:
        err_fh.flush()
        try:
            err_text = err_log.read_text(encoding="utf-8", errors="replace")[-500:]
        except Exception:
            err_text = ""
        return {
            "ok": False,
            "error": f"cdp_start: {type(exc).__name__}: {exc}"[:200],
            "label": target["label"],
            "pid": proc.pid,
            "exe": exe,
            "stderr_tail": err_text,
            "alive": proc.poll() is None,
        }
    finally:
        try:
            err_fh.close()
        except Exception:
            pass

    cdp = Cdp(port)
    try:
        cdp.attach_page()
        cdp.call("Network.enable", session=True)
        cdp.call("Page.enable", session=True)
        cdp.call("Page.navigate", {"url": "https://chatgpt.com/"}, session=True)
        time.sleep(2.5)
        ok = fail = 0
        names: list[str] = []
        fails: list[str] = []
        for c in cookies:
            try:
                payload = cookie_to_cdp(c)
                res = cdp.call("Network.setCookie", payload, session=True) or {}
                if res.get("success", True):
                    ok += 1
                    names.append(payload["name"])
                else:
                    fail += 1
                    fails.append(payload["name"])
            except Exception as exc:
                fail += 1
                fails.append(f"{c.get('name')}:{type(exc).__name__}")
        cdp.call("Page.navigate", {"url": "https://chatgpt.com/"}, session=True)
        time.sleep(4)
        probe = cdp.call(
            "Runtime.evaluate",
            {
                "expression": """
(async () => {
  try {
    const r = await fetch('https://chatgpt.com/api/auth/session', {credentials:'include'});
    const j = await r.json();
    const keys = j && typeof j==='object' ? Object.keys(j).slice(0,20) : [];
    return {
      status: r.status,
      keys,
      hasUser: !!(j && (j.user || j.accessToken || j.sessionToken)),
      warningOnly: !!(j && keys.length===1 && keys[0]==='WARNING_BANNER'),
      emailPresent: !!(j && j.user && j.user.email)
    };
  } catch (e) {
    return {error: String(e && e.message || e).slice(0,120)};
  }
})()
""",
                "awaitPromise": True,
                "returnByValue": True,
                "userGesture": True,
            },
            session=True,
        ) or {}
        session_probe = (probe.get("result") or {}).get("value") or {}
        meta = cdp.call("Network.getAllCookies", session=True) or {}
        all_c = meta.get("cookies") or []
        return {
            "ok": bool(session_probe.get("hasUser") or ok > 0),
            "status": "WEB_SESSION_OK"
            if session_probe.get("hasUser")
            else "COOKIES_SET_UNVERIFIED",
            "label": target["label"],
            "exe": exe,
            "user_data": str(user_data),
            "profile_directory": target["profile_directory"],
            "port": port,
            "pid": proc.pid,
            "browser": cdp.version.get("Browser"),
            "set_ok": ok,
            "set_fail": fail,
            "names_set_count": len(set(names)),
            "has_nextauth": any(
                n.startswith("__Secure-next-auth.session-token") for n in names
            ),
            "fail_sample": fails[:8],
            "session_probe": session_probe,
            "browser_cookie_count": len(all_c),
            "browser_has_nextauth": any(
                (c.get("name") or "").startswith("__Secure-next-auth.session-token")
                for c in all_c
            ),
        }
    finally:
        cdp.close()


def inject_firefox(target: dict[str, Any], cookies: list[dict[str, Any]]) -> dict[str, Any]:
    """Inject via Selenium into the main Firefox profile."""
    exe = find_exe(target["exe_candidates"])
    profile_path = Path(target["profile_path"])
    if not exe:
        return {"ok": False, "error": "firefox.exe not found", "label": target["label"]}
    if not profile_path.is_dir():
        return {
            "ok": False,
            "error": f"profile missing: {profile_path}",
            "label": target["label"],
        }

    kill_processes(target["process_names"])
    try:
        from selenium import webdriver
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.firefox.service import Service
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "selenium", "-q"])
        from selenium import webdriver
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.firefox.service import Service

    opts = Options()
    opts.binary_location = exe
    # Selenium 4 profile path
    opts.add_argument("-profile")
    opts.add_argument(str(profile_path))
    driver = None
    try:
        driver = webdriver.Firefox(options=opts)
        driver.get("https://chatgpt.com/")
        time.sleep(3)
        try:
            driver.delete_all_cookies()
        except Exception:
            pass
        ok = fail = 0
        fails: list[str] = []
        for c in cookies:
            domain = c.get("domain") or ".chatgpt.com"
            # Selenium only sets cookies for current domain
            if "chatgpt.com" not in domain and "openai.com" not in domain:
                continue
            if "openai.com" in domain and "chatgpt.com" not in domain:
                continue
            try:
                cookie_dict: dict[str, Any] = {
                    "name": c["name"],
                    "value": c["value"],
                    "path": c.get("path") or "/",
                    "secure": bool(c.get("secure", True)),
                }
                if not str(c["name"]).startswith("__Host-"):
                    cookie_dict["domain"] = domain
                if c.get("httpOnly"):
                    cookie_dict["httpOnly"] = True
                exp = c.get("expires")
                if isinstance(exp, (int, float)) and exp > 0:
                    cookie_dict["expiry"] = int(exp)
                else:
                    cookie_dict["expiry"] = int(time.time()) + 30 * 24 * 3600
                ss = c.get("sameSite")
                if ss in ("Strict", "Lax", "None"):
                    cookie_dict["sameSite"] = ss
                driver.add_cookie(cookie_dict)
                ok += 1
            except Exception as exc:
                fail += 1
                fails.append(f"{c.get('name')}:{type(exc).__name__}")

        # auth.openai.com cookies
        auth_cs = [
            c
            for c in cookies
            if "openai.com" in (c.get("domain") or "") and "chatgpt" not in (c.get("domain") or "")
        ]
        if auth_cs:
            driver.get("https://auth.openai.com/")
            time.sleep(2)
            for c in auth_cs:
                try:
                    cookie_dict = {
                        "name": c["name"],
                        "value": c["value"],
                        "path": c.get("path") or "/",
                        "domain": c.get("domain") or ".auth.openai.com",
                        "secure": True,
                    }
                    if c.get("httpOnly"):
                        cookie_dict["httpOnly"] = True
                    driver.add_cookie(cookie_dict)
                    ok += 1
                except Exception as exc:
                    fail += 1
                    fails.append(f"{c.get('name')}:{type(exc).__name__}")

        driver.get("https://chatgpt.com/")
        time.sleep(4)
        session_probe = driver.execute_script(
            """
const done = arguments[0];
fetch('https://chatgpt.com/api/auth/session', {credentials:'include'})
  .then(r => r.json().then(j => ({status:r.status, j})))
  .then(({status, j}) => {
    const keys = j && typeof j==='object' ? Object.keys(j).slice(0,20) : [];
    done({
      status,
      keys,
      hasUser: !!(j && (j.user || j.accessToken || j.sessionToken)),
      warningOnly: !!(j && keys.length===1 && keys[0]==='WARNING_BANNER'),
      emailPresent: !!(j && j.user && j.user.email)
    });
  })
  .catch(e => done({error: String(e).slice(0,120)}));
"""
        )
        # execute_async_script
        try:
            session_probe = driver.execute_async_script(
                """
var done = arguments[0];
fetch('https://chatgpt.com/api/auth/session', {credentials:'include'})
  .then(r => r.json().then(j => ({status:r.status, j})))
  .then(({status, j}) => {
    const keys = j && typeof j==='object' ? Object.keys(j).slice(0,20) : [];
    done({
      status: status,
      keys: keys,
      hasUser: !!(j && (j.user || j.accessToken || j.sessionToken)),
      warningOnly: !!(j && keys.length===1 && keys[0]==='WARNING_BANNER'),
      emailPresent: !!(j && j.user && j.user.email)
    });
  })
  .catch(e => done({error: String(e).slice(0,120)}));
"""
            )
        except Exception as exc:
            session_probe = {"error": type(exc).__name__}

        return {
            "ok": bool((session_probe or {}).get("hasUser") or ok > 0),
            "status": "WEB_SESSION_OK"
            if (session_probe or {}).get("hasUser")
            else "COOKIES_SET_UNVERIFIED",
            "label": target["label"],
            "exe": exe,
            "profile_path": str(profile_path),
            "set_ok": ok,
            "set_fail": fail,
            "fail_sample": fails[:8],
            "session_probe": session_probe,
            "left_open": True,
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}"[:240],
            "label": target["label"],
            "exe": exe,
            "profile_path": str(profile_path),
        }
    # leave Firefox open with session (do not driver.quit)


def main() -> int:
    if os.environ.get("I_ACCEPT_PROFILE_RISK") != "1":
        print(
            "REFUSED: inject_all_main_profiles.py is deprecated (Jul-20 profile corruption).\n"
            "Use: python safe_main_cookie_inject.py --browser chrome --payload both\n"
            "Or set I_ACCEPT_PROFILE_RISK=1 only if you fully understand the risk."
        )
        return 2

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help="comma list: chrome,edge,comet,firefox")
    parser.add_argument("--skip", help="comma list to skip")
    args = parser.parse_args()
    only = {x.strip() for x in (args.only or "").split(",") if x.strip()} or set(TARGETS)
    skip = {x.strip() for x in (args.skip or "").split(",") if x.strip()}
    selected = [k for k in TARGETS if k in only and k not in skip]

    cookies = load_cookies()
    print(f"Loaded {len(cookies)} cookies from {COOKIE_FILE}")
    results: dict[str, Any] = {
        "at": datetime.now(timezone.utc).isoformat(),
        "source_store": str(COOKIE_FILE),
        "cookie_count": len(cookies),
        "targets": {},
    }
    for key in selected:
        target = TARGETS[key]
        print(f"\n=== {key}: {target['label']} ===")
        if target["kind"] == "chromium":
            report = inject_chromium(target, cookies)
        else:
            report = inject_firefox(target, cookies)
        results["targets"][key] = report
        print(json.dumps({k: report[k] for k in report if k != "fail_sample"}, indent=2, default=str))

    ok_count = sum(1 for r in results["targets"].values() if r.get("ok"))
    results["summary"] = {
        "ok_count": ok_count,
        "total": len(results["targets"]),
        "web_session_ok": [
            k
            for k, r in results["targets"].items()
            if r.get("status") == "WEB_SESSION_OK"
        ],
    }
    REPORT_FILE.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\n# wrote {REPORT_FILE}")
    print(json.dumps(results["summary"], indent=2))
    return 0 if ok_count == len(results["targets"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
