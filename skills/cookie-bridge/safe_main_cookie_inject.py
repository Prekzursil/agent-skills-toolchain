#!/usr/bin/env python3
"""Safe main-profile cookie inject (ChatGPT + Databricks) without profile corruption.

Rules (hard):
  - Additive Network.setCookie ONLY (never delete cookies / wipe jar)
  - Never rewrite Preferences / Login Data / History / Bookmarks
  - One browser at a time; refuse if that browser is still running
  - Pre-snapshot critical files; post-integrity on account_info + login count
  - Graceful Browser.close — no taskkill /F by default
  - Does NOT touch July-8 sso-mirror trees

Usage:
  python safe_main_cookie_inject.py --dry-run --browser chrome
  python safe_main_cookie_inject.py --browser chrome --payload both
  python safe_main_cookie_inject.py --browser edge --payload both
  python safe_main_cookie_inject.py --browser chrome,edge --payload both

Requires target browser(s) fully quit before --apply (default when not --dry-run).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STORE = Path.home() / ".crcp" / "cookie-bridge"
LOCAL = Path(os.environ.get("LOCALAPPDATA", ""))
CHATGPT_FILE = STORE / "chatgpt_cookies.json"
DATABRICKS_FILE = STORE / "databricks_cookies.json"

BROWSERS: dict[str, dict[str, Any]] = {
    "chrome": {
        "process": "chrome",
        "exe": [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            str(Path.home() / r"AppData\Local\Google\Chrome\Application\chrome.exe"),
        ],
        "real_user_data": LOCAL / r"Google\Chrome\User Data",
        "junction": STORE / "profile-junctions" / "chrome-ud",
        "profile_directory": "Default",
        "port": 9381,
        "label": "Chrome Default",
    },
    "edge": {
        "process": "msedge",
        "exe": [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ],
        "real_user_data": LOCAL / r"Microsoft\Edge\User Data",
        "junction": STORE / "profile-junctions" / "edge-ud",
        "profile_directory": "Default",
        "port": 9382,
        "label": "Edge Default",
    },
    "comet": {
        "process": "Comet",
        "exe": [
            str(Path.home() / r"AppData\Local\Perplexity\Comet\Application\comet.exe"),
            r"C:\Program Files\Perplexity\Comet\Application\comet.exe",
        ],
        "real_user_data": LOCAL / r"Perplexity\Comet\User Data",
        "junction": None,  # Comet allows CDP on real path
        "profile_directory": "Default",
        "port": 9383,
        "label": "Comet Default",
    },
}

SEED_URLS_CHATGPT = [
    "https://chatgpt.com/",
    "https://auth.openai.com/",
]
SEED_URLS_DATABRICKS = [
    "https://bolt.okta.com/",
    "https://bolt-datascience.cloud.databricks.com/",
    "https://bolt-common.cloud.databricks.com/",
    "https://bolt-geo.cloud.databricks.com/",
]


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def process_running(name: str) -> int:
    """Return approximate process count for name.exe (0 if none)."""
    r = subprocess.run(
        ["tasklist", "/FI", f"IMAGENAME eq {name}.exe", "/NH"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    out = r.stdout or ""
    # tasklist prints "INFO: No tasks..." when empty
    if "no tasks" in out.lower():
        return 0
    return sum(1 for line in out.splitlines() if f"{name.lower()}.exe" in line.lower())


def find_exe(cands: list[str]) -> str | None:
    for c in cands:
        if c and Path(c).is_file():
            return c
    return None


def ensure_junction(junction: Path, real: Path) -> None:
    if junction.exists() or junction.is_symlink():
        return
    junction.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(real)],
        capture_output=True,
        text=True,
        check=False,
    )


def load_payload(kind: str) -> list[dict[str, Any]]:
    cookies: list[dict[str, Any]] = []
    if kind in ("chatgpt", "both"):
        if not CHATGPT_FILE.is_file():
            raise SystemExit(f"missing {CHATGPT_FILE}")
        data = json.loads(CHATGPT_FILE.read_text(encoding="utf-8"))
        cookies.extend(data.get("cookies") or [])
    if kind in ("databricks", "both"):
        if not DATABRICKS_FILE.is_file():
            raise SystemExit(f"missing {DATABRICKS_FILE}")
        data = json.loads(DATABRICKS_FILE.read_text(encoding="utf-8"))
        cookies.extend(data.get("cookies") or [])
    if not cookies:
        raise SystemExit("payload empty")
    return cookies


def summarize_cookies(cookies: list[dict[str, Any]]) -> dict[str, Any]:
    hosts: dict[str, int] = {}
    names: list[str] = []
    for c in cookies:
        h = (c.get("domain") or "?").lstrip(".")
        hosts[h] = hosts.get(h, 0) + 1
        names.append(str(c.get("name") or ""))
    return {
        "count": len(cookies),
        "hosts": dict(sorted(hosts.items(), key=lambda x: (-x[1], x[0]))),
        "has_dbauth": any(n == "DBAUTH" for n in names),
        "has_nextauth": any(
            n.startswith("__Secure-next-auth.session-token") for n in names
        ),
        "has_okta_idx": any(n == "idx" for n in names),
    }


def account_emails(pref_path: Path) -> list[str]:
    if not pref_path.is_file():
        return []
    try:
        j = json.loads(pref_path.read_text(encoding="utf-8"))
    except Exception:
        return ["<unreadable>"]
    out = []
    for a in j.get("account_info") or []:
        if isinstance(a, dict) and a.get("email"):
            out.append(str(a["email"]))
    return out


def sqlite_count(db_path: Path, table: str) -> int | None:
    if not db_path.is_file():
        return None
    tmp = Path(tempfile.gettempdir()) / f"crcp_probe_{os.getpid()}_{db_path.name}"
    try:
        shutil.copy2(db_path, tmp)
        con = sqlite3.connect(str(tmp))
        n = con.execute(f"SELECT COUNT(*) FROM [{table}]").fetchone()[0]
        con.close()
        return int(n)
    except Exception:
        return None
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


def measure_profile(default_dir: Path) -> dict[str, Any]:
    pref = default_dir / "Preferences"
    login = default_dir / "Login Data"
    history = default_dir / "History"
    cookies = default_dir / "Network" / "Cookies"
    bookmarks = default_dir / "Bookmarks"
    return {
        "account_emails": account_emails(pref),
        "pref_size": pref.stat().st_size if pref.is_file() else 0,
        "pref_mtime": pref.stat().st_mtime if pref.is_file() else 0,
        "login_count": sqlite_count(login, "logins"),
        "history_urls": sqlite_count(history, "urls"),
        "cookies_size": cookies.stat().st_size if cookies.is_file() else 0,
        "bookmarks_size": bookmarks.stat().st_size if bookmarks.is_file() else 0,
    }


def snapshot_profile(browser: str, cfg: dict[str, Any], snap_root: Path) -> Path:
    real_ud = Path(cfg["real_user_data"])
    default = real_ud / cfg["profile_directory"]
    dest = snap_root / browser
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "Network").mkdir(exist_ok=True)

    copies = [
        (default / "Preferences", dest / "Preferences"),
        (default / "Secure Preferences", dest / "Secure Preferences"),
        (default / "Login Data", dest / "Login Data"),
        (default / "Bookmarks", dest / "Bookmarks"),
        (default / "Network" / "Cookies", dest / "Network" / "Cookies"),
        (default / "Network" / "Cookies-journal", dest / "Network" / "Cookies-journal"),
        (real_ud / "Local State", dest / "Local State"),
    ]
    # History can be huge — copy only if < 80MB else record stats only
    hist = default / "History"
    if hist.is_file() and hist.stat().st_size < 80 * 1024 * 1024:
        copies.append((hist, dest / "History"))

    copied = []
    for src, dst in copies:
        if src.is_file():
            try:
                shutil.copy2(src, dst)
                copied.append(str(src.name))
            except Exception as exc:
                copied.append(f"{src.name}:FAIL:{type(exc).__name__}")
    meta = {
        "browser": browser,
        "default": str(default),
        "copied": copied,
        "baseline": measure_profile(default),
        "at": datetime.now(timezone.utc).isoformat(),
    }
    (dest / "snapshot_meta.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    return dest


def rollback_from_snapshot(cfg: dict[str, Any], snap_dir: Path) -> list[str]:
    """Restore Preferences + Cookies only (safest integrity recovery)."""
    real_ud = Path(cfg["real_user_data"])
    default = real_ud / cfg["profile_directory"]
    restored = []
    pairs = [
        (snap_dir / "Preferences", default / "Preferences"),
        (snap_dir / "Secure Preferences", default / "Secure Preferences"),
        (snap_dir / "Network" / "Cookies", default / "Network" / "Cookies"),
        (
            snap_dir / "Network" / "Cookies-journal",
            default / "Network" / "Cookies-journal",
        ),
    ]
    for src, dst in pairs:
        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            restored.append(str(dst))
    return restored


def integrity_ok(
    before: dict[str, Any], after: dict[str, Any]
) -> tuple[bool, list[str]]:
    issues = []
    if before.get("account_emails") != after.get("account_emails"):
        issues.append(
            f"account_emails changed: {before.get('account_emails')} → {after.get('account_emails')}"
        )
    bl = before.get("login_count")
    al = after.get("login_count")
    if bl is not None and al is not None and al < bl:
        issues.append(f"login_count decreased: {bl} → {al}")
    bh = before.get("history_urls")
    ah = after.get("history_urls")
    if bh is not None and ah is not None and ah < max(0, bh - 5):
        issues.append(f"history_urls dropped sharply: {bh} → {ah}")
    bb = before.get("bookmarks_size") or 0
    ab = after.get("bookmarks_size") or 0
    if bb and ab and ab + 100 < bb:  # allow tiny rewrite noise
        issues.append(f"bookmarks_size shrank: {bb} → {ab}")
    if (after.get("cookies_size") or 0) == 0 and (before.get("cookies_size") or 0) > 0:
        issues.append("cookies file empty after inject")
    return (len(issues) == 0, issues)


def port_open(port: int) -> bool:
    import socket

    try:
        with socket.create_connection(("127.0.0.1", port), 1.0):
            return True
    except OSError:
        return False


def http_json(port: int, path: str, timeout: float = 10.0) -> Any:
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        headers={"Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


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


def _ws_connect(ws_url: str):
    try:
        import websocket  # type: ignore
    except ImportError:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "websocket-client", "-q"]
        )
        import websocket  # type: ignore
    return websocket.create_connection(ws_url, timeout=45, suppress_origin=True)


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
        self,
        method: str,
        params: dict | None = None,
        *,
        session: bool = False,
        timeout: float = 45,
    ) -> Any:
        self._id += 1
        msg: dict[str, Any] = {"id": self._id, "method": method}
        if params:
            msg["params"] = params
        if session and self.session_id:
            msg["sessionId"] = self.session_id
        self.ws.send(json.dumps(msg))
        deadline = time.time() + timeout
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
        # host-only; keep url, no domain
        if "chatgpt" in host:
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


def group_seed_urls(payload: str) -> list[str]:
    urls: list[str] = []
    if payload in ("chatgpt", "both"):
        urls.extend(SEED_URLS_CHATGPT)
    if payload in ("databricks", "both"):
        urls.extend(SEED_URLS_DATABRICKS)
    # unique preserve order
    seen = set()
    out = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def clear_singleton(user_data: Path) -> None:
    for name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
        p = user_data / name
        try:
            if p.exists() or p.is_symlink() or p.is_file():
                p.unlink(missing_ok=True)  # type: ignore[call-arg]
        except Exception:
            try:
                if p.exists():
                    p.unlink()
            except OSError:
                pass


def inject_one(
    browser: str,
    payload: str,
    cookies: list[dict[str, Any]],
    *,
    dry_run: bool,
    snap_root: Path,
    force_kill: bool = False,
) -> dict[str, Any]:
    cfg = BROWSERS[browser]
    proc = cfg["process"]
    real_ud = Path(cfg["real_user_data"])
    default = real_ud / cfg["profile_directory"]
    report: dict[str, Any] = {
        "browser": browser,
        "label": cfg["label"],
        "payload": payload,
        "dry_run": dry_run,
    }

    if not default.is_dir():
        report["ok"] = False
        report["error"] = f"profile missing: {default}"
        return report

    nproc = process_running(proc)
    report["process_count_start"] = nproc
    if nproc > 0 and not dry_run:
        report["ok"] = False
        report["error"] = f"{proc}.exe still running ({nproc})"
        report["hint"] = f"Fully quit {cfg['label']} (Task Manager), then re-run"
        return report

    baseline = measure_profile(default)
    report["baseline"] = baseline
    print(f"\n=== {cfg['label']} ===")
    print("  accounts:", baseline.get("account_emails"))
    print(
        "  logins:",
        baseline.get("login_count"),
        "history_urls:",
        baseline.get("history_urls"),
    )
    if nproc > 0:
        print(f"  note: {proc}.exe running ({nproc}) — dry-run only; apply will refuse")

    snap_dir = snapshot_profile(browser, cfg, snap_root)
    report["snapshot"] = str(snap_dir)
    print(f"  snapshot → {snap_dir}")

    if dry_run:
        report["ok"] = True
        report["action"] = "dry_run_snapshot_only"
        report["apply_blocked_until_quit"] = nproc > 0
        return report

    exe = find_exe(cfg["exe"])
    if not exe:
        report["ok"] = False
        report["error"] = "exe_not_found"
        return report

    user_data_arg = real_ud
    if cfg.get("junction") is not None:
        ensure_junction(Path(cfg["junction"]), real_ud)
        user_data_arg = Path(cfg["junction"])

    port = int(cfg["port"])
    clear_singleton(real_ud)
    clear_singleton(user_data_arg)

    args = [
        exe,
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        f"--user-data-dir={user_data_arg}",
        f"--profile-directory={cfg['profile_directory']}",
        "--no-first-run",
        "--no-default-browser-check",
        "about:blank",
    ]
    err_log = Path(tempfile.gettempdir()) / f"crcp_safe_inject_{browser}.err"
    err_fh = open(err_log, "w", encoding="utf-8", errors="replace")
    proc_h = subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=err_fh,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    report["pid"] = proc_h.pid
    try:
        wait_cdp(port, timeout=70)
    except Exception as exc:
        err_fh.flush()
        report["ok"] = False
        report["error"] = f"cdp_start:{type(exc).__name__}:{exc}"
        try:
            report["stderr_tail"] = err_log.read_text(
                encoding="utf-8", errors="replace"
            )[-400:]
        except Exception:
            pass
        # try graceful — still no /F unless forced
        try:
            proc_h.terminate()
        except Exception:
            pass
        return report
    finally:
        try:
            err_fh.close()
        except Exception:
            pass

    cdp = Cdp(port)
    set_ok = set_fail = 0
    fails: list[str] = []
    probes: dict[str, Any] = {}
    try:
        cdp.attach_page()
        cdp.call("Network.enable", session=True)
        cdp.call("Page.enable", session=True)

        for url in group_seed_urls(payload):
            try:
                cdp.call("Page.navigate", {"url": url}, session=True)
                time.sleep(1.5)
            except Exception as exc:
                print(f"  seed fail {url}: {type(exc).__name__}")

        for c in cookies:
            try:
                payload_c = cookie_to_cdp(c)
                res = cdp.call("Network.setCookie", payload_c, session=True) or {}
                if res.get("success", True):
                    set_ok += 1
                else:
                    set_fail += 1
                    fails.append(str(payload_c.get("name")))
            except Exception as exc:
                set_fail += 1
                fails.append(f"{c.get('name')}:{type(exc).__name__}")

        report["set_ok"] = set_ok
        report["set_fail"] = set_fail
        report["fail_sample"] = fails[:12]
        print(f"  set_ok={set_ok} set_fail={set_fail}")

        # Probes
        if payload in ("chatgpt", "both"):
            cdp.call("Page.navigate", {"url": "https://chatgpt.com/"}, session=True)
            time.sleep(4)
            pr = (
                cdp.call(
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
      hasUser: !!(j && (j.user || j.accessToken || j.sessionToken)),
      emailPresent: !!(j && j.user && j.user.email),
      keys
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
                )
                or {}
            )
            probes["chatgpt"] = (pr.get("result") or {}).get("value") or {}

        if payload in ("databricks", "both"):
            cdp.call(
                "Page.navigate",
                {"url": "https://bolt-datascience.cloud.databricks.com/"},
                session=True,
            )
            time.sleep(5)
            pr = (
                cdp.call(
                    "Runtime.evaluate",
                    {
                        "expression": """
(() => {
  const u = location.href;
  const t = document.title || '';
  const body = (document.body && document.body.innerText || '').slice(0, 400);
  const looksLogin = /sign in|log in|okta|authenticate/i.test(t + ' ' + body + ' ' + u);
  const looksApp = /workspace|databricks|sql|catalog|compute|home/i.test(t + ' ' + body) && !looksLogin;
  return {url: u.slice(0,160), title: t.slice(0,80), looksLogin, looksApp};
})()
""",
                        "returnByValue": True,
                    },
                    session=True,
                )
                or {}
            )
            probes["databricks_ds"] = (pr.get("result") or {}).get("value") or {}

        report["probes"] = probes
        print("  probes:", json.dumps(probes)[:400])

        # Graceful close
        try:
            cdp.call("Browser.close", timeout=10)
        except Exception as exc:
            report["close_note"] = f"Browser.close: {type(exc).__name__}"
    finally:
        cdp.close()

    # Wait for process exit
    dead = False
    for _ in range(40):
        if process_running(proc) == 0:
            dead = True
            break
        time.sleep(0.5)
    report["process_exited"] = dead
    if not dead:
        if force_kill:
            subprocess.run(
                ["taskkill", "/F", "/IM", f"{proc}.exe", "/T"],
                capture_output=True,
                check=False,
            )
            time.sleep(2)
            report["force_killed"] = True
            dead = process_running(proc) == 0
        else:
            report["ok"] = False
            report["error"] = "browser_did_not_exit_gracefully"
            report["hint"] = (
                "Close it manually, then re-check integrity; avoid /F if possible"
            )
            return report

    if dead:
        clear_singleton(real_ud)

    time.sleep(1.5)
    after = measure_profile(default)
    report["after"] = after
    ok_int, issues = integrity_ok(baseline, after)
    report["integrity_ok"] = ok_int
    report["integrity_issues"] = issues

    if not ok_int:
        print("  INTEGRITY FAIL:", issues)
        try:
            restored = rollback_from_snapshot(cfg, snap_dir)
            report["rollback"] = restored
            report["ok"] = False
            report["error"] = "integrity_failed_rolled_back"
        except Exception as exc:
            report["ok"] = False
            report["error"] = f"integrity_failed_rollback_error:{exc}"
        return report

    # Probe soft-fail still counts as cookies set if integrity ok
    chatgpt_ok = True
    dbx_ok = True
    if payload in ("chatgpt", "both"):
        chatgpt_ok = bool((probes.get("chatgpt") or {}).get("hasUser"))
    if payload in ("databricks", "both"):
        dbx_ok = bool((probes.get("databricks_ds") or {}).get("looksApp")) or not (
            probes.get("databricks_ds") or {}
        ).get("looksLogin", True)

    report["ok"] = set_ok > 0 and ok_int
    report["status"] = (
        "WEB_LIKELY_OK"
        if report["ok"]
        and (chatgpt_ok or payload == "databricks")
        and (dbx_ok or payload == "chatgpt")
        else ("COOKIES_SET_INTEGRITY_OK" if report["ok"] else "FAILED")
    )
    report["probe_chatgpt_ok"] = chatgpt_ok if payload in ("chatgpt", "both") else None
    report["probe_dbx_ok"] = dbx_ok if payload in ("databricks", "both") else None
    print(f"  status={report['status']} integrity_ok={ok_int}")
    return report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Safe main-profile cookie inject")
    p.add_argument(
        "--browser",
        default="chrome",
        help="comma list: chrome,edge,comet",
    )
    p.add_argument(
        "--payload",
        choices=["chatgpt", "databricks", "both"],
        default="both",
    )
    p.add_argument("--dry-run", action="store_true", help="snapshot+baseline only")
    p.add_argument(
        "--force-kill",
        action="store_true",
        help="If Browser.close fails, taskkill /F (NOT recommended)",
    )
    args = p.parse_args(argv)

    browsers = [b.strip() for b in args.browser.split(",") if b.strip()]
    for b in browsers:
        if b not in BROWSERS:
            print(f"unknown browser: {b}", file=sys.stderr)
            return 2

    cookies = load_payload(args.payload)
    summary = summarize_cookies(cookies)
    print("Payload:", args.payload, summary)
    print("Mode:", "DRY-RUN" if args.dry_run else "APPLY")
    print("Rules: setCookie only · no deletes · no prefs rewrite · no Jul8 SSO")

    stamp = utc_stamp()
    snap_root = STORE / f"pre-main-inject-{stamp}"
    snap_root.mkdir(parents=True, exist_ok=True)

    results = []
    for b in browsers:
        try:
            results.append(
                inject_one(
                    b,
                    args.payload,
                    cookies,
                    dry_run=args.dry_run,
                    snap_root=snap_root,
                    force_kill=args.force_kill,
                )
            )
        except Exception as exc:
            results.append(
                {
                    "browser": b,
                    "ok": False,
                    "error": f"{type(exc).__name__}:{exc}"[:240],
                }
            )

    report = {
        "at": datetime.now(timezone.utc).isoformat(),
        "payload": args.payload,
        "cookie_summary": summary,
        "dry_run": args.dry_run,
        "snap_root": str(snap_root),
        "results": results,
    }
    out = STORE / f"safe_main_inject_report_{stamp}.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("\nReport:", out)
    print("Snapshots:", snap_root)

    ok_n = sum(1 for r in results if r.get("ok"))
    print(f"Done: {ok_n}/{len(results)} ok")

    busy = [r for r in results if "still running" in str(r.get("error", ""))]
    if busy and not args.dry_run:
        print("\nQuit these browsers, then re-run the same command:")
        for r in busy:
            print(" -", r.get("browser"), r.get("hint"))

    return 0 if ok_n == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
