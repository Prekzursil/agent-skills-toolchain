#!/usr/bin/env python3
"""Phone → PC bridge for Databricks web sessions (3 workspaces + Okta).

Mirrors the ChatGPT cookie_bridge flow:

  python databricks_cookie_bridge.py extract   # ADB + phone Chrome CDP
  python databricks_cookie_bridge.py inject    # main Chrome/Edge/Comet (+ optional Firefox)
  python databricks_cookie_bridge.py sync      # extract + inject
  python databricks_cookie_bridge.py status

Workspaces (from ~/.databrickscfg):
  bolt-datascience  https://bolt-datascience.cloud.databricks.com
  bolt-common       https://bolt-common.cloud.databricks.com
  bolt-geo          https://bolt-geo.cloud.databricks.com
SSO: bolt.okta.com
"""

from __future__ import annotations

import argparse
import json
import os
import re
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
COOKIE_FILE = STORE / "databricks_cookies.json"
REPORT_FILE = STORE / "databricks_inject_report.json"
PHONE_CDP_PORT = 9223

WORKSPACES: dict[str, dict[str, str]] = {
    "bolt-datascience": {
        "host": "bolt-datascience.cloud.databricks.com",
        "url": "https://bolt-datascience.cloud.databricks.com/",
        "org": "3829506390716583",
    },
    "bolt-common": {
        "host": "bolt-common.cloud.databricks.com",
        "url": "https://bolt-common.cloud.databricks.com/",
        "org": "3598988355446810",
    },
    "bolt-geo": {
        "host": "bolt-geo.cloud.databricks.com",
        "url": "https://bolt-geo.cloud.databricks.com/",
        "org": "1492481942411573",
    },
}

COOKIE_URLS = [
    "https://bolt-datascience.cloud.databricks.com/",
    "https://bolt-common.cloud.databricks.com/",
    "https://bolt-geo.cloud.databricks.com/",
    "https://accounts.cloud.databricks.com/",
    "https://login.databricks.com/",
    "https://bolt.okta.com/",
    "https://bolt.okta.com/app/UserHome",
]

DOMAIN_KEEP = (
    "databricks.com",
    "okta.com",
    "oktacdn.com",
)

# Session-ish cookie name fragments (for status only — never print values)
SESSION_HINTS = (
    "session",
    "sid",
    "jwt",
    "token",
    "auth",
    "aws-waf",
    "csrf",
    "JSESSION",
    "remember",
    "idx",
)

# SAFETY: default inject uses ONLY isolated durable profiles under ~/.crcp/cookie-bridge.
# Never points at real Chrome/Edge/Comet User Data. That avoids the prior main-profile
# corruption (login/settings wipe) from kill+CDP on Default.
DURABLE_TARGETS: dict[str, dict[str, Any]] = {
    "chrome-durable": {
        "kind": "chromium",
        "process_names": [],  # do not kill anything
        "exe_candidates": [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            str(Path.home() / r"AppData\Local\Google\Chrome\Application\chrome.exe"),
        ],
        "user_data": STORE / "databricks-durable-profile",
        "profile_directory": "Default",
        "port": 9371,
        "label": "Chrome DURABLE (isolated, safe)",
        "also_apply_chatgpt": True,
    },
    "edge-durable": {
        "kind": "chromium",
        "process_names": [],
        "exe_candidates": [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ],
        "user_data": STORE / "databricks-edge-durable-profile",
        "profile_directory": "Default",
        "port": 9372,
        "label": "Edge DURABLE (isolated, safe)",
        "also_apply_chatgpt": True,
    },
}

# Opt-in only: writing into daily browsers. Requires --danger-main-profiles.
MAIN_TARGETS: dict[str, dict[str, Any]] = {
    "chrome": {
        "kind": "chromium",
        "process_names": ["chrome", "GoogleCrashHandler", "GoogleCrashHandler64"],
        "exe_candidates": [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ],
        "user_data": Path.home() / r".crcp\cookie-bridge\profile-junctions\chrome-ud",
        "real_user_data": Path.home() / r"AppData\Local\Google\Chrome\User Data",
        "profile_directory": "Default",
        "port": 9361,
        "label": "Chrome Default (DANGER)",
    },
    "edge": {
        "kind": "chromium",
        "process_names": ["msedge", "msedgewebview2"],
        "exe_candidates": [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ],
        "user_data": Path.home() / r".crcp\cookie-bridge\profile-junctions\edge-ud",
        "real_user_data": Path.home() / r"AppData\Local\Microsoft\Edge\User Data",
        "profile_directory": "Default",
        "port": 9362,
        "label": "Edge Default (DANGER)",
    },
}

# Back-compat alias
TARGETS = DURABLE_TARGETS


def ensure_store() -> None:
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


def http_json(port: int, path: str, timeout: float = 20.0) -> Any:
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        headers={"Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def ensure_adb_forward() -> str:
    r = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=15)
    devices = [
        line.split("\t")[0]
        for line in r.stdout.strip().splitlines()[1:]
        if "\tdevice" in line
    ]
    if not devices:
        raise SystemExit("ERROR: No Android device connected via ADB")
    device = devices[0]
    print(f"Device: {device}")

    # Prefer already-working forward (avoid slow /proc/net/unix on some phones).
    try:
        ver = http_json(PHONE_CDP_PORT, "/json/version", timeout=3)
        print(
            f"Reusing existing CDP :{PHONE_CDP_PORT} → "
            f"{ver.get('Browser')} ({ver.get('Android-Package')})"
        )
        return device
    except Exception:
        pass

    sock_candidates = ["chrome_devtools_remote"]
    # Optional fast grep (short timeout); ignore if it hangs.
    try:
        r2 = subprocess.run(
            [
                "adb",
                "-s",
                device,
                "shell",
                "toybox grep chrome_devtools_remote /proc/net/unix 2>/dev/null | head -20",
            ],
            capture_output=True,
            text=True,
            timeout=8,
        )
        found = re.findall(r"chrome_devtools_remote(?:_\d+)?", r2.stdout or "")
        for s in found:
            if s not in sock_candidates:
                sock_candidates.append(s)
    except Exception as exc:
        print(f"note: socket scan skipped ({type(exc).__name__})")

    last_err = None
    for sock in sock_candidates:
        subprocess.run(
            ["adb", "-s", device, "forward", "--remove", f"tcp:{PHONE_CDP_PORT}"],
            capture_output=True,
            timeout=5,
            check=False,
        )
        r3 = subprocess.run(
            [
                "adb",
                "-s",
                device,
                "forward",
                f"tcp:{PHONE_CDP_PORT}",
                f"localabstract:{sock}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r3.returncode != 0:
            last_err = r3.stderr or r3.stdout
            continue
        try:
            ver = http_json(PHONE_CDP_PORT, "/json/version", timeout=5)
            print(f"ADB forward: tcp:{PHONE_CDP_PORT} → localabstract:{sock}")
            print(f"Phone Chrome: {ver.get('Browser')} ({ver.get('Android-Package')})")
            return device
        except Exception as exc:
            last_err = exc
            continue

    raise SystemExit(
        f"ERROR: could not attach phone Chrome CDP. last_err={last_err!r}. "
        "Open Chrome on phone + enable USB debugging."
    )


def _ws_connect(ws_url: str):
    try:
        import websocket  # type: ignore
    except ImportError:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "websocket-client", "-q"]
        )
        import websocket  # type: ignore
    # Phone CDP often needs suppress_origin
    return websocket.create_connection(ws_url, timeout=45, suppress_origin=True)


def cdp_call(ws, mid: int, method: str, params: dict | None = None) -> Any:
    msg: dict[str, Any] = {"id": mid, "method": method}
    if params:
        msg["params"] = params
    ws.send(json.dumps(msg))
    deadline = time.time() + 40
    while time.time() < deadline:
        data = json.loads(ws.recv())
        if data.get("id") == mid:
            if data.get("error"):
                raise RuntimeError(f"{method}: {data['error']}")
            return data.get("result")
    raise TimeoutError(method)


def domain_allowed(domain: str) -> bool:
    d = (domain or "").lower().lstrip(".")
    return any(d == k or d.endswith("." + k) or k in d for k in DOMAIN_KEEP)


def dedupe_cookies(cookies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[tuple[str, str, str], dict[str, Any]] = {}
    for c in cookies:
        if not isinstance(c, dict) or "name" not in c or "value" not in c:
            continue
        domain = c.get("domain") or ""
        if not domain_allowed(domain):
            continue
        key = (c["name"], domain, c.get("path") or "/")
        # Prefer longer value / later expires when duplicate
        prev = seen.get(key)
        if prev is None or len(str(c.get("value", ""))) >= len(
            str(prev.get("value", ""))
        ):
            seen[key] = c
    return list(seen.values())


def summarize_cookies(cookies: list[dict[str, Any]]) -> dict[str, Any]:
    by_host: dict[str, int] = {}
    sessionish: list[str] = []
    for c in cookies:
        dom = (c.get("domain") or "?").lstrip(".")
        by_host[dom] = by_host.get(dom, 0) + 1
        name = c.get("name") or ""
        if any(h.lower() in name.lower() for h in SESSION_HINTS):
            sessionish.append(f"{dom}:{name}")
    per_ws = {}
    for name, meta in WORKSPACES.items():
        host = meta["host"]
        per_ws[name] = sum(
            1
            for c in cookies
            if host in (c.get("domain") or "") or (c.get("domain") or "").endswith(host)
        )
    okta_n = sum(1 for c in cookies if "okta" in (c.get("domain") or "").lower())
    return {
        "total": len(cookies),
        "by_host": dict(sorted(by_host.items(), key=lambda x: (-x[1], x[0]))),
        "per_workspace": per_ws,
        "okta_cookie_count": okta_n,
        "sessionish_names": sorted(set(sessionish))[:40],
    }


def find_tabs(tabs: list[dict[str, Any]]) -> dict[str, Any]:
    pages = [t for t in tabs if t.get("type") in (None, "page", "background_page")]
    ws_tabs: dict[str, dict[str, Any]] = {}
    okta_tabs = []
    for t in pages:
        url = t.get("url") or ""
        for name, meta in WORKSPACES.items():
            if meta["host"] in url and name not in ws_tabs:
                # Prefer non-worker main document
                if "SharedWorker" in (t.get("title") or ""):
                    continue
                if "/static/" in url:
                    continue
                ws_tabs[name] = t
        if "bolt.okta.com" in url and "authorize" not in url:
            okta_tabs.append(t)
    return {"workspaces": ws_tabs, "okta": okta_tabs[:3], "total_tabs": len(tabs)}


def extract_cookies_from_tab(ws_url: str) -> list[dict[str, Any]]:
    ws = _ws_connect(ws_url)
    try:
        # Scoped getCookies includes httpOnly; avoid getAllCookies (can hang on busy phones).
        r1 = cdp_call(ws, 1, "Network.getCookies", {"urls": COOKIE_URLS})
        cookies = list((r1 or {}).get("cookies") or [])
        return cookies
    finally:
        try:
            ws.close()
        except Exception:
            pass


def cmd_extract() -> dict[str, Any]:
    print("=== EXTRACT: Phone Chrome → databricks_cookies.json ===\n")
    ensure_store()
    ensure_adb_forward()

    tabs = http_json(PHONE_CDP_PORT, "/json/list", timeout=30)
    found = find_tabs(tabs)
    print(f"Tabs total: {found['total_tabs']}")
    for name, t in found["workspaces"].items():
        print(
            f"  WS {name}: {(t.get('title') or '')[:50]} | {(t.get('url') or '')[:90]}"
        )
    for t in found["okta"]:
        print(f"  Okta: {(t.get('title') or '')[:50]} | {(t.get('url') or '')[:90]}")

    missing = [n for n in WORKSPACES if n not in found["workspaces"]]
    if missing:
        print(f"WARNING: missing open tabs for: {missing}")
        print("  (will still try cookies from other open DBX/Okta tabs)")

    # Use first available page with a websocket
    sources: list[dict[str, Any]] = []
    for t in found["workspaces"].values():
        sources.append(t)
    sources.extend(found["okta"])
    if not sources:
        # fallback: any databricks url
        for t in tabs:
            u = t.get("url") or ""
            if "databricks.com" in u and t.get("webSocketDebuggerUrl"):
                sources.append(t)
                break
    if not sources:
        raise SystemExit("No Databricks/Okta tab with CDP websocket found")

    all_cookies: list[dict[str, Any]] = []
    used = 0
    for t in sources[:6]:
        ws_url = t.get("webSocketDebuggerUrl")
        if not ws_url:
            continue
        print(f"\nExtracting via: {(t.get('url') or '')[:100]}")
        try:
            got = extract_cookies_from_tab(ws_url)
            print(f"  raw cookies from tab: {len(got)}")
            all_cookies.extend(got)
            used += 1
        except Exception as exc:
            print(f"  FAIL: {type(exc).__name__}: {exc}")

    cookies = dedupe_cookies(all_cookies)
    summary = summarize_cookies(cookies)
    print(f"\nDeduped DBX/Okta cookies: {summary['total']}")
    print("Per workspace cookie counts:", summary["per_workspace"])
    print("Okta cookies:", summary["okta_cookie_count"])
    print("Hosts:", summary["by_host"])
    if summary["sessionish_names"]:
        print("Session-ish names (no values):")
        for n in summary["sessionish_names"][:25]:
            print(f"  {n}")

    if summary["total"] == 0:
        raise SystemExit("ERROR: extracted 0 databricks/okta cookies")

    payload = {
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "source": "phone_chrome_cdp",
        "phone_cdp_port": PHONE_CDP_PORT,
        "workspaces": {
            k: {
                "host": v["host"],
                "url": v["url"],
                "org": v["org"],
                "tab_found": k in found["workspaces"],
                "tab_url": (found["workspaces"].get(k) or {}).get("url"),
            }
            for k, v in WORKSPACES.items()
        },
        "okta_tabs": [
            {"title": t.get("title"), "url": t.get("url")} for t in found["okta"]
        ],
        "cookie_count": len(cookies),
        "summary": summary,
        "extract_sources_used": used,
        "cookies": cookies,
    }
    tmp = COOKIE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(COOKIE_FILE)
    print(f"\nSaved → {COOKIE_FILE}")
    return payload


def load_cookies() -> dict[str, Any]:
    if not COOKIE_FILE.is_file():
        raise SystemExit(f"missing {COOKIE_FILE} — run extract first")
    return json.loads(COOKIE_FILE.read_text(encoding="utf-8"))


def cmd_status() -> dict[str, Any]:
    if not COOKIE_FILE.is_file():
        print("No databricks cookie store yet")
        return {"ok": False}
    data = load_cookies()
    cookies = data.get("cookies") or []
    summary = data.get("summary") or summarize_cookies(cookies)
    age_h = None
    try:
        ts = datetime.fromisoformat(
            str(data.get("extracted_at")).replace("Z", "+00:00")
        )
        age_h = round((datetime.now(timezone.utc) - ts).total_seconds() / 3600, 2)
    except Exception:
        pass
    report = {
        "ok": True,
        "cookie_file": str(COOKIE_FILE),
        "extracted_at": data.get("extracted_at"),
        "age_hours": age_h,
        "cookie_count": len(cookies),
        "summary": summary,
        "workspaces": data.get("workspaces"),
    }
    print(json.dumps(report, indent=2, default=str))
    return report


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


def wait_cdp(port: int, timeout: float = 60.0) -> dict[str, Any]:
    deadline = time.time() + timeout
    last: Exception | None = None
    while time.time() < deadline:
        try:
            return http_json(port, "/json/version", timeout=3)
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(0.4)
    raise RuntimeError(
        f"CDP :{port} not ready: {type(last).__name__ if last else 'timeout'}"
    )


def cookie_to_cdp(c: dict[str, Any]) -> dict[str, Any]:
    name = c["name"]
    domain = c.get("domain") or ".cloud.databricks.com"
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
        # must not set Domain; keep url
        pass
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
        ver = wait_cdp(port)
        ws_url = ver.get("webSocketDebuggerUrl")
        if not ws_url:
            raise RuntimeError("no webSocketDebuggerUrl")
        self.ws = _ws_connect(ws_url)
        self._id = 0
        self.session_id: str | None = None
        self.version = ver

    def close(self) -> None:
        try:
            self.ws.close()
        except Exception:
            pass

    def call(
        self, method: str, params: dict | None = None, *, session: bool = False
    ) -> Any:
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
        att = (
            self.call("Target.attachToTarget", {"targetId": tid, "flatten": True}) or {}
        )
        self.session_id = att.get("sessionId")
        if not self.session_id:
            raise RuntimeError("no sessionId")


def inject_chromium(
    target: dict[str, Any],
    cookies: list[dict[str, Any]],
    *,
    allow_kill: bool = False,
) -> dict[str, Any]:
    exe = find_exe(target["exe_candidates"])
    if not exe:
        return {"ok": False, "error": "executable_not_found", "label": target["label"]}

    user_data = Path(target["user_data"])
    real_ud = Path(target.get("real_user_data") or user_data)

    # Refuse to touch real daily User Data unless explicitly allowed
    real_chrome = Path.home() / r"AppData\Local\Google\Chrome\User Data"
    real_edge = Path.home() / r"AppData\Local\Microsoft\Edge\User Data"
    real_comet = Path.home() / r"AppData\Local\Perplexity\Comet\User Data"
    resolved = real_ud.resolve() if real_ud.exists() else real_ud
    is_main = any(
        str(resolved).lower().startswith(str(p.resolve() if p.exists() else p).lower())
        for p in (real_chrome, real_edge, real_comet)
    )
    if is_main and not allow_kill:
        return {
            "ok": False,
            "error": "refused_main_profile_without_--danger-main-profiles",
            "label": target["label"],
            "path": str(resolved),
        }

    if target.get("real_user_data") and not user_data.exists() and allow_kill:
        user_data.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(user_data), str(real_ud)],
            capture_output=True,
            text=True,
            check=False,
        )

    print(f"\n--- Inject → {target['label']} ---")
    print(f"  profile: {user_data}")
    # Only kill when targeting main profiles (opt-in danger path)
    if allow_kill and target.get("process_names"):
        print("  WARNING: killing browser processes for main-profile bind")
        kill_processes(target["process_names"])
        clear_singleton_locks(real_ud)
        clear_singleton_locks(user_data)
    else:
        # Isolated profile: clear only THIS profile's singleton locks, never kill daily browsers
        user_data.mkdir(parents=True, exist_ok=True)
        clear_singleton_locks(user_data)

    port = int(target["port"])
    if port_open(port):
        # Prefer reuse of our durable instance rather than fighting another process
        try:
            wait_cdp(port, timeout=3.0)
            print(f"  reusing CDP already on :{port}")
        except Exception:
            pass

    args = [
        exe,
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        f"--user-data-dir={user_data}",
        f"--profile-directory={target['profile_directory']}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-mode",
        "about:blank",
    ]
    proc_pid = None
    reused = False
    if not port_open(port):
        err_log = Path(tempfile.gettempdir()) / f"crcp_dbx_inject_{port}.err"
        err_fh = open(err_log, "w", encoding="utf-8", errors="replace")
        proc = subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=err_fh,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
        proc_pid = proc.pid
        try:
            wait_cdp(port, timeout=70.0)
        except Exception as exc:
            err_fh.flush()
            try:
                err_text = err_log.read_text(encoding="utf-8", errors="replace")[-400:]
            except Exception:
                err_text = ""
            return {
                "ok": False,
                "error": f"cdp_start: {type(exc).__name__}: {exc}"[:200],
                "label": target["label"],
                "pid": proc_pid,
                "stderr_tail": err_text,
            }
        finally:
            try:
                err_fh.close()
            except Exception:
                pass
    else:
        reused = True
        try:
            wait_cdp(port, timeout=10.0)
        except Exception as exc:
            return {
                "ok": False,
                "error": f"cdp_reuse: {type(exc).__name__}: {exc}"[:200],
                "label": target["label"],
            }

    cdp = Cdp(port)
    try:
        cdp.attach_page()
        cdp.call("Network.enable", session=True)
        cdp.call("Page.enable", session=True)

        # Seed each origin before setting host cookies
        seed_urls = [
            "https://bolt.okta.com/",
            "https://bolt-datascience.cloud.databricks.com/",
            "https://bolt-common.cloud.databricks.com/",
            "https://bolt-geo.cloud.databricks.com/",
        ]
        for url in seed_urls:
            try:
                cdp.call("Page.navigate", {"url": url}, session=True)
                time.sleep(1.2)
            except Exception as exc:
                print(f"  seed {url}: {type(exc).__name__}")

        ok = fail = 0
        fails: list[str] = []
        for c in cookies:
            try:
                payload = cookie_to_cdp(c)
                res = cdp.call("Network.setCookie", payload, session=True) or {}
                if res.get("success", True):
                    ok += 1
                else:
                    fail += 1
                    fails.append(payload["name"])
            except Exception as exc:
                fail += 1
                fails.append(f"{c.get('name')}:{type(exc).__name__}")

        # Open the three workspaces + okta for visual check
        open_urls = [
            "https://bolt-datascience.cloud.databricks.com/",
            "https://bolt-common.cloud.databricks.com/",
            "https://bolt-geo.cloud.databricks.com/",
            "https://bolt.okta.com/app/UserHome",
        ]
        for url in open_urls:
            try:
                cdp.call("Target.createTarget", {"url": url})
            except Exception:
                pass

        # Probe first workspace for logged-in signal (no cookie values)
        cdp.call(
            "Page.navigate",
            {"url": "https://bolt-datascience.cloud.databricks.com/"},
            session=True,
        )
        time.sleep(5)
        probe = (
            cdp.call(
                "Runtime.evaluate",
                {
                    "expression": """
(() => {
  const u = location.href;
  const t = document.title || '';
  const body = (document.body && document.body.innerText || '').slice(0, 500);
  const looksLogin = /sign in|log in|okta|authenticate/i.test(t + ' ' + body + ' ' + u);
  const looksApp = /workspace|databricks|sql|catalog|compute/i.test(t + ' ' + body)
    && !looksLogin;
  return {
    url: u.slice(0, 160),
    title: t.slice(0, 80),
    looksLogin,
    looksApp,
    hasDatabricksHost: /cloud\\.databricks\\.com/i.test(u)
  };
})()
""",
                    "returnByValue": True,
                },
                session=True,
            )
            or {}
        )
        page_probe = (probe.get("result") or {}).get("value") or {}

        result = {
            "ok": ok > 0,
            "status": "WEB_LIKELY_OK"
            if page_probe.get("looksApp")
            else ("COOKIES_SET" if ok > 0 else "FAILED"),
            "label": target["label"],
            "exe": exe,
            "user_data": str(user_data),
            "port": port,
            "pid": proc_pid,
            "reused_cdp": reused,
            "browser": cdp.version.get("Browser"),
            "set_ok": ok,
            "set_fail": fail,
            "fail_sample": fails[:10],
            "page_probe": page_probe,
            "main_profile_touched": bool(is_main),
        }
        print(
            f"  set_ok={ok} set_fail={fail} status={result['status']} "
            f"title={page_probe.get('title')!r}"
        )
        return result
    finally:
        cdp.close()


def load_chatgpt_cookies() -> list[dict[str, Any]]:
    path = STORE / "chatgpt_cookies.json"
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return list(data.get("cookies") or [])
    except Exception:
        return []


def cmd_inject(
    only: list[str] | None = None,
    *,
    danger_main: bool = False,
    with_chatgpt: bool = True,
) -> dict[str, Any]:
    print("=== INJECT: databricks cookies → ISOLATED durable profiles (safe) ===\n")
    if danger_main:
        print(
            "!!! DANGER: --danger-main-profiles enabled — may kill daily browsers !!!"
        )
    else:
        print("Safe mode: will NOT kill Chrome/Edge/Comet daily processes.")
        print("Safe mode: will NOT write into AppData\\...\\User Data main profiles.")

    data = load_cookies()
    cookies = list(data.get("cookies") or [])
    if not cookies:
        raise SystemExit("cookie store empty — run extract first")

    chatgpt_n = 0
    if with_chatgpt:
        cg = load_chatgpt_cookies()
        if cg:
            # Merge ChatGPT into same durable browser so one window has both
            cookies = dedupe_cookies(cookies + cg) if False else (cookies + cg)
            # don't filter chatgpt through databricks domain filter — append as-is
            chatgpt_n = len(cg)
            print(
                f"Also applying ChatGPT cookies from store: {chatgpt_n} (re-login restore)"
            )
        else:
            print("No chatgpt_cookies.json found — DBX only")

    summary = data.get("summary") or summarize_cookies(
        [c for c in cookies if domain_allowed(c.get("domain") or "")]
    )
    print(
        f"DBX cookies: {data.get('cookie_count')} | workspaces: {summary.get('per_workspace')} "
        f"| total to set (incl optional chatgpt): {len(cookies)}"
    )

    targets = dict(DURABLE_TARGETS)
    allow_kill = False
    if danger_main:
        targets.update(MAIN_TARGETS)
        allow_kill = True
    if only:
        targets = {k: v for k, v in targets.items() if k in only}
        if not targets:
            raise SystemExit(
                f"no matching targets in {only}; known={list(DURABLE_TARGETS)}"
            )

    results = []
    for key, target in targets.items():
        try:
            results.append(
                inject_chromium(
                    target, cookies, allow_kill=allow_kill and key in MAIN_TARGETS
                )
            )
        except Exception as exc:
            results.append(
                {
                    "ok": False,
                    "label": target.get("label", key),
                    "error": f"{type(exc).__name__}: {exc}"[:200],
                }
            )

    report = {
        "injected_at": datetime.now(timezone.utc).isoformat(),
        "mode": "danger_main" if danger_main else "durable_isolated",
        "cookie_source": str(COOKIE_FILE),
        "cookie_count_dbx": data.get("cookie_count"),
        "cookie_count_chatgpt_merged": chatgpt_n,
        "extracted_at": data.get("extracted_at"),
        "results": results,
        "how_to_open": {
            "chrome_durable": (
                r'start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" '
                r'--user-data-dir="%USERPROFILE%\.crcp\cookie-bridge\databricks-durable-profile" '
                r"--profile-directory=Default "
                r"https://bolt-datascience.cloud.databricks.com/"
            ),
            "note": "Use this isolated profile for Databricks. Daily Chrome is untouched.",
        },
    }
    REPORT_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nReport → {REPORT_FILE}")
    ok_n = sum(1 for r in results if r.get("ok"))
    print(f"Done: {ok_n}/{len(results)} profiles ok")
    return report


def cmd_sync(
    only: list[str] | None = None, *, danger_main: bool = False
) -> dict[str, Any]:
    cmd_extract()
    print()
    return cmd_inject(only=only, danger_main=danger_main)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Databricks phone→PC web session bridge (safe durable default)"
    )
    p.add_argument(
        "command",
        choices=["extract", "inject", "sync", "status"],
        help="extract | inject | sync | status",
    )
    p.add_argument(
        "--only",
        default="",
        help="comma list: chrome-durable,edge-durable (or danger: chrome,edge)",
    )
    p.add_argument(
        "--danger-main-profiles",
        action="store_true",
        help="OPT-IN: also inject into daily Chrome/Edge (kills those browsers). Default OFF.",
    )
    p.add_argument(
        "--no-chatgpt",
        action="store_true",
        help="Do not merge saved ChatGPT cookies into durable profile",
    )
    args = p.parse_args(argv)
    only = [x.strip() for x in args.only.split(",") if x.strip()] or None
    if args.command == "extract":
        cmd_extract()
    elif args.command == "status":
        cmd_status()
    elif args.command == "inject":
        cmd_inject(
            only=only,
            danger_main=args.danger_main_profiles,
            with_chatgpt=not args.no_chatgpt,
        )
    elif args.command == "sync":
        cmd_sync(only=only, danger_main=args.danger_main_profiles)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
