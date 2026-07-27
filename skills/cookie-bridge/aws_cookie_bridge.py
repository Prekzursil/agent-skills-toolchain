#!/usr/bin/env python3
"""Phone → PC bridge for AWS web sessions (IAM Identity Center / console + Okta).

Mirrors the ChatGPT / Databricks cookie_bridge flow:

  python aws_cookie_bridge.py extract   # ADB + phone Chrome CDP → aws_cookies.json
  python aws_cookie_bridge.py status    # metadata only (no values)
  python aws_cookie_bridge.py vault     # DPAPI-protect store into ~/.crcp/secret-vault
  python aws_cookie_bridge.py sync      # extract + vault

Observed phone tab (2026-07-24):
  https://d-996771582c.awsapps.com/start/  (AWS access portal)
  https://bolt.okta.com/app/UserHome       (Bolt SSO)

HARD RULE: never print cookie values. Status/docs list names + lengths + domains only.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STORE = Path.home() / ".crcp" / "cookie-bridge"
COOKIE_FILE = STORE / "aws_cookies.json"
STATUS_FILE = STORE / "aws_cookies_status.json"
VAULT_DIR = Path.home() / ".crcp" / "secret-vault"
VAULT_CONTAINER = VAULT_DIR / "aws-cookies.dpapi"
VAULT_MANIFEST = VAULT_DIR / ".vault-manifest.json"
VAULT_INDEX = VAULT_DIR / "INDEX.md"
PHONE_CDP_PORT = 9223

# IAM Identity Center portal instance observed on phone
AWS_ACCESS_PORTAL = {
    "id": "d-996771582c",
    "host": "d-996771582c.awsapps.com",
    "url": "https://d-996771582c.awsapps.com/start/",
    "label": "AWS access portal (IAM Identity Center)",
}

COOKIE_URLS = [
    "https://d-996771582c.awsapps.com/start/",
    "https://d-996771582c.awsapps.com/start/#/",
    "https://d-996771582c.awsapps.com/start/#/?tab=accounts",
    "https://console.aws.amazon.com/",
    "https://us-east-1.console.aws.amazon.com/",
    "https://eu-central-1.console.aws.amazon.com/",
    "https://eu-west-1.console.aws.amazon.com/",
    "https://signin.aws.amazon.com/",
    "https://us-east-1.signin.aws.amazon.com/",
    "https://portal.sso.amazonaws.com/",
    "https://oidc.us-east-1.amazonaws.com/",
    "https://aws.amazon.com/",
    "https://bolt.okta.com/",
    "https://bolt.okta.com/app/UserHome",
]

# Keep only AWS session surfaces + Bolt Okta SSO. Do NOT pull retail amazon.com shopping.
DOMAIN_KEEP = (
    "awsapps.com",
    "aws.amazon.com",
    "console.aws.amazon.com",
    "signin.aws.amazon.com",
    "amazonaws.com",
    "amazon.com",  # filtered further in domain_allowed (console/signin/aws only)
    "okta.com",
    "oktacdn.com",
)

SESSION_HINTS = (
    "session",
    "sid",
    "jwt",
    "token",
    "auth",
    "xsrf",
    "csrf",
    "aws-waf",
    "awsalb",
    "JSESSION",
    "remember",
    "idx",
    "sso",
    "portal",
    "credential",
    "aws-userInfo",
    "noflush",
    "awsccc",
)


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


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

    last_err: Any = None
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
    if not d:
        return False
    # Explicit allow for AWS surfaces
    if any(
        d == k or d.endswith("." + k)
        for k in (
            "awsapps.com",
            "aws.amazon.com",
            "console.aws.amazon.com",
            "signin.aws.amazon.com",
            "amazonaws.com",
            "okta.com",
            "oktacdn.com",
        )
    ):
        return True
    # amazon.com only if host looks like console/signin/aws — not retail shopping
    if d == "amazon.com" or d.endswith(".amazon.com"):
        return any(
            frag in d
            for frag in (
                "aws.",
                "console.",
                "signin.",
                "sso.",
            )
        )
    return False


def dedupe_cookies(cookies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[tuple[str, str, str], dict[str, Any]] = {}
    for c in cookies:
        if not isinstance(c, dict) or "name" not in c or "value" not in c:
            continue
        domain = c.get("domain") or ""
        if not domain_allowed(domain):
            continue
        key = (c["name"], domain, c.get("path") or "/")
        prev = seen.get(key)
        if prev is None or len(str(c.get("value", ""))) >= len(
            str(prev.get("value", ""))
        ):
            seen[key] = c
    return list(seen.values())


def summarize_cookies(cookies: list[dict[str, Any]]) -> dict[str, Any]:
    by_host: dict[str, int] = {}
    names_meta: list[dict[str, Any]] = []
    sessionish: list[str] = []
    for c in cookies:
        dom = (c.get("domain") or "?").lstrip(".")
        by_host[dom] = by_host.get(dom, 0) + 1
        name = c.get("name") or ""
        val = c.get("value") or ""
        names_meta.append(
            {
                "name": name,
                "domain": c.get("domain") or "",
                "path": c.get("path") or "/",
                "len": len(str(val)),
                "httpOnly": bool(c.get("httpOnly")),
                "secure": bool(c.get("secure")),
                "sameSite": c.get("sameSite"),
                "expires": c.get("expires"),
            }
        )
        if any(h.lower() in name.lower() for h in SESSION_HINTS):
            sessionish.append(f"{dom}:{name}")
    portal_n = sum(
        1
        for c in cookies
        if "awsapps.com" in (c.get("domain") or "")
        or "amazonaws.com" in (c.get("domain") or "")
    )
    console_n = sum(
        1
        for c in cookies
        if "console.aws.amazon.com" in (c.get("domain") or "")
        or "signin.aws.amazon.com" in (c.get("domain") or "")
        or "aws.amazon.com" in (c.get("domain") or "")
    )
    okta_n = sum(1 for c in cookies if "okta" in (c.get("domain") or "").lower())
    return {
        "total": len(cookies),
        "by_host": dict(sorted(by_host.items(), key=lambda x: (-x[1], x[0]))),
        "portal_cookie_count": portal_n,
        "console_cookie_count": console_n,
        "okta_cookie_count": okta_n,
        "sessionish_names": sorted(set(sessionish))[:50],
        "cookie_names": names_meta,
        "has_portal_session": any(
            "awsapps" in (c.get("domain") or "")
            and any(
                h in (c.get("name") or "").lower()
                for h in ("session", "token", "sid", "auth", "xsrf")
            )
            for c in cookies
        ),
        "has_okta_session": any(
            "okta" in (c.get("domain") or "").lower()
            and any(
                h in (c.get("name") or "").lower()
                for h in ("sid", "idx", "session", "token")
            )
            for c in cookies
        ),
    }


def find_tabs(tabs: list[dict[str, Any]]) -> dict[str, Any]:
    pages = [t for t in tabs if t.get("type") in (None, "page", "background_page")]
    portal_tabs: list[dict[str, Any]] = []
    console_tabs: list[dict[str, Any]] = []
    okta_tabs: list[dict[str, Any]] = []
    for t in pages:
        url = t.get("url") or ""
        title = t.get("title") or ""
        if "SharedWorker" in title or "/static/" in url:
            continue
        if "awsapps.com" in url or "portal.sso.amazonaws.com" in url:
            portal_tabs.append(t)
        elif any(
            x in url
            for x in (
                "console.aws.amazon.com",
                "signin.aws.amazon.com",
                "aws.amazon.com/console",
            )
        ):
            console_tabs.append(t)
        elif "bolt.okta.com" in url and "authorize" not in url:
            okta_tabs.append(t)
    return {
        "portal": portal_tabs[:5],
        "console": console_tabs[:5],
        "okta": okta_tabs[:5],
        "total_tabs": len(tabs),
    }


def extract_cookies_from_tab(ws_url: str) -> list[dict[str, Any]]:
    ws = _ws_connect(ws_url)
    try:
        r1 = cdp_call(ws, 1, "Network.getCookies", {"urls": COOKIE_URLS})
        return list((r1 or {}).get("cookies") or [])
    finally:
        try:
            ws.close()
        except Exception:
            pass


def cmd_extract() -> dict[str, Any]:
    print("=== EXTRACT: Phone Chrome → aws_cookies.json ===\n")
    ensure_store()
    ensure_adb_forward()

    try:
        tabs = http_json(PHONE_CDP_PORT, "/json/list", timeout=30)
    except Exception:
        tabs = http_json(PHONE_CDP_PORT, "/json", timeout=30)

    found = find_tabs(tabs)
    print(f"Tabs total: {found['total_tabs']}")
    for t in found["portal"]:
        print(f"  PORTAL: {(t.get('title') or '')[:50]} | {(t.get('url') or '')[:100]}")
    for t in found["console"]:
        print(
            f"  CONSOLE: {(t.get('title') or '')[:50]} | {(t.get('url') or '')[:100]}"
        )
    for t in found["okta"]:
        print(f"  Okta: {(t.get('title') or '')[:50]} | {(t.get('url') or '')[:100]}")

    if not found["portal"] and not found["console"]:
        print(
            "WARNING: no open AWS portal/console tab — will still try cookies "
            "from Okta/other tabs if present"
        )

    sources: list[dict[str, Any]] = []
    sources.extend(found["portal"])
    sources.extend(found["console"])
    sources.extend(found["okta"])
    if not sources:
        for t in tabs:
            u = t.get("url") or ""
            if any(
                x in u
                for x in ("awsapps.com", "aws.amazon.com", "amazonaws.com", "okta.com")
            ):
                if t.get("webSocketDebuggerUrl"):
                    sources.append(t)
                    break
    if not sources:
        raise SystemExit(
            "No AWS/Okta tab with CDP websocket found. "
            "Open https://d-996771582c.awsapps.com/start/ on phone Chrome."
        )

    all_cookies: list[dict[str, Any]] = []
    used = 0
    page_states: list[dict[str, str]] = []
    for t in sources[:8]:
        ws_url = t.get("webSocketDebuggerUrl")
        if not ws_url:
            continue
        print(f"\nExtracting via: {(t.get('url') or '')[:100]}")
        try:
            got = extract_cookies_from_tab(ws_url)
            print(f"  raw cookies from tab: {len(got)}")
            all_cookies.extend(got)
            used += 1
            page_states.append(
                {
                    "title": (t.get("title") or "")[:80],
                    "url": (t.get("url") or "")[:200],
                }
            )
        except Exception as exc:
            print(f"  FAIL: {type(exc).__name__}: {exc}")

    cookies = dedupe_cookies(all_cookies)
    summary = summarize_cookies(cookies)
    print(f"\nDeduped AWS/Okta cookies: {summary['total']}")
    print("Portal cookies:", summary["portal_cookie_count"])
    print("Console cookies:", summary["console_cookie_count"])
    print("Okta cookies:", summary["okta_cookie_count"])
    print("Hosts:", summary["by_host"])
    if summary["sessionish_names"]:
        print("Session-ish names (no values):")
        for n in summary["sessionish_names"][:30]:
            print(f"  {n}")

    if summary["total"] == 0:
        raise SystemExit("ERROR: extracted 0 AWS/Okta cookies")

    # Drop values from the summary cookie_names for the public status file
    status_summary = {k: v for k, v in summary.items() if k != "cookie_names"}
    status_summary["cookie_names"] = [
        {kk: vv for kk, vv in m.items()} for m in summary["cookie_names"]
    ]

    payload = {
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "source": "phone_chrome_cdp",
        "phone_cdp_port": PHONE_CDP_PORT,
        "access_portal": AWS_ACCESS_PORTAL,
        "page_states": page_states,
        "tabs_found": {
            "portal": [
                {"title": t.get("title"), "url": t.get("url")} for t in found["portal"]
            ],
            "console": [
                {"title": t.get("title"), "url": t.get("url")} for t in found["console"]
            ],
            "okta": [
                {"title": t.get("title"), "url": t.get("url")} for t in found["okta"]
            ],
        },
        "cookie_count": len(cookies),
        "summary": summary,
        "extract_sources_used": used,
        "cookies": cookies,
    }
    tmp = COOKIE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(COOKIE_FILE)
    # Restrict ACL on the secret file
    if os.name == "nt":
        try:
            subprocess.run(
                [
                    "icacls",
                    str(COOKIE_FILE),
                    "/inheritance:r",
                    "/grant:r",
                    f"{os.environ.get('USERNAME', '')}:F",
                ],
                capture_output=True,
                timeout=10,
                check=False,
            )
        except Exception:
            pass

    # Public status (no values)
    status_payload = {
        "ok": True,
        "cookie_file": str(COOKIE_FILE),
        "extracted_at": payload["extracted_at"],
        "source": payload["source"],
        "access_portal": AWS_ACCESS_PORTAL,
        "cookie_count": len(cookies),
        "summary": status_summary,
        "tabs_found": payload["tabs_found"],
        "extract_sources_used": used,
        "health": _health_label(status_summary),
    }
    STATUS_FILE.write_text(json.dumps(status_payload, indent=2), encoding="utf-8")
    print(f"\nSaved secrets → {COOKIE_FILE}")
    print(f"Saved status  → {STATUS_FILE}")
    print(f"Health: {status_payload['health']}")
    return payload


def _health_label(summary: dict[str, Any]) -> str:
    if summary.get("has_portal_session") and summary.get("portal_cookie_count", 0) > 0:
        return "GOOD_PORTAL"
    if summary.get("console_cookie_count", 0) > 0:
        return "PARTIAL_CONSOLE"
    if summary.get("has_okta_session"):
        return "OKTA_ONLY"
    if summary.get("total", 0) > 0:
        return "COOKIES_PRESENT"
    return "EMPTY"


def load_cookies() -> dict[str, Any]:
    if not COOKIE_FILE.is_file():
        raise SystemExit(f"missing {COOKIE_FILE} — run extract first")
    return json.loads(COOKIE_FILE.read_text(encoding="utf-8"))


def cmd_status() -> dict[str, Any]:
    if STATUS_FILE.is_file():
        report = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        # refresh age
        try:
            ts = datetime.fromisoformat(
                str(report.get("extracted_at")).replace("Z", "+00:00")
            )
            report["age_hours"] = round(
                (datetime.now(timezone.utc) - ts).total_seconds() / 3600, 2
            )
        except Exception:
            report["age_hours"] = None
        report["vault_present"] = VAULT_CONTAINER.is_file()
        print(json.dumps(report, indent=2, default=str))
        return report
    if not COOKIE_FILE.is_file():
        print("No aws cookie store yet")
        return {"ok": False}
    data = load_cookies()
    cookies = data.get("cookies") or []
    summary = data.get("summary") or summarize_cookies(cookies)
    # strip any accidental values from print path
    safe = {
        "ok": True,
        "cookie_file": str(COOKIE_FILE),
        "extracted_at": data.get("extracted_at"),
        "cookie_count": len(cookies),
        "access_portal": data.get("access_portal"),
        "summary": {
            "total": summary.get("total"),
            "by_host": summary.get("by_host"),
            "portal_cookie_count": summary.get("portal_cookie_count"),
            "console_cookie_count": summary.get("console_cookie_count"),
            "okta_cookie_count": summary.get("okta_cookie_count"),
            "sessionish_names": summary.get("sessionish_names"),
            "has_portal_session": summary.get("has_portal_session"),
            "has_okta_session": summary.get("has_okta_session"),
            "cookie_names": [
                {
                    "name": m.get("name"),
                    "domain": m.get("domain"),
                    "path": m.get("path"),
                    "len": m.get("len"),
                    "httpOnly": m.get("httpOnly"),
                    "secure": m.get("secure"),
                }
                for m in (summary.get("cookie_names") or [])
            ],
        },
        "health": _health_label(summary),
        "vault_present": VAULT_CONTAINER.is_file(),
    }
    print(json.dumps(safe, indent=2, default=str))
    return safe


def dpapi_protect(data: bytes) -> bytes:
    blob_in = DATA_BLOB(
        len(data), ctypes.cast(ctypes.c_char_p(data), ctypes.POINTER(ctypes.c_char))
    )
    blob_out = DATA_BLOB()
    ok = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    )
    if not ok:
        raise OSError("CryptProtectData failed")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def dpapi_unprotect(data: bytes) -> bytes:
    blob_in = DATA_BLOB(
        len(data), ctypes.cast(ctypes.c_char_p(data), ctypes.POINTER(ctypes.c_char))
    )
    blob_out = DATA_BLOB()
    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    )
    if not ok:
        raise OSError("CryptUnprotectData failed")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def cmd_vault() -> dict[str, Any]:
    print("=== VAULT: aws_cookies.json → aws-cookies.dpapi ===\n")
    if not COOKIE_FILE.is_file():
        raise SystemExit(f"missing {COOKIE_FILE} — run extract first")
    raw = COOKIE_FILE.read_bytes()
    # Sanity: must be JSON with cookies, never print values
    data = json.loads(raw.decode("utf-8"))
    n = len(data.get("cookies") or [])
    if n == 0:
        raise SystemExit("refusing to vault empty cookie store")

    VAULT_DIR.mkdir(parents=True, exist_ok=True)
    cipher = dpapi_protect(raw)
    tmp = VAULT_CONTAINER.with_suffix(".tmp")
    tmp.write_bytes(cipher)
    tmp.replace(VAULT_CONTAINER)

    # ACL lock
    if os.name == "nt":
        subprocess.run(
            [
                "icacls",
                str(VAULT_CONTAINER),
                "/inheritance:r",
                "/grant:r",
                f"{os.environ.get('USERDOMAIN', '')}\\{os.environ.get('USERNAME', '')}:F",
            ],
            capture_output=True,
            timeout=15,
            check=False,
        )
        # also lock vault dir lightly
        subprocess.run(
            [
                "icacls",
                str(VAULT_DIR),
                "/inheritance:r",
                "/grant:r",
                f"{os.environ.get('USERDOMAIN', '')}\\{os.environ.get('USERNAME', '')}:(OI)(CI)F",
            ],
            capture_output=True,
            timeout=15,
            check=False,
        )

    # Round-trip verify (length only)
    plain = dpapi_unprotect(VAULT_CONTAINER.read_bytes())
    if len(plain) != len(raw):
        raise SystemExit(f"round-trip size mismatch: plain={len(plain)} raw={len(raw)}")
    # confirm JSON parse without dumping
    rt = json.loads(plain.decode("utf-8"))
    if len(rt.get("cookies") or []) != n:
        raise SystemExit("round-trip cookie count mismatch")

    print(f"VAULTED: {VAULT_CONTAINER.name}")
    print(f"  plaintext_bytes={len(raw)}  cipher_bytes={len(cipher)}  cookies={n}")
    print("  round-trip: DECRYPT-OK")

    _update_vault_manifest(len(cipher), n)
    _append_vault_index(data, n)

    return {
        "ok": True,
        "container": str(VAULT_CONTAINER),
        "plaintext_bytes": len(raw),
        "cipher_bytes": len(cipher),
        "cookie_count": n,
        "roundtrip": "DECRYPT-OK",
    }


def _update_vault_manifest(cipher_bytes: int, cookie_count: int) -> None:
    manifest: dict[str, Any]
    if VAULT_MANIFEST.is_file():
        try:
            manifest = json.loads(VAULT_MANIFEST.read_text(encoding="utf-8"))
        except Exception:
            manifest = {}
    else:
        manifest = {}
    containers = list(manifest.get("containers") or [])
    containers = [c for c in containers if c.get("file") != "aws-cookies.dpapi"]
    containers.append(
        {
            "file": "aws-cookies.dpapi",
            "source": "~/.crcp/cookie-bridge/aws_cookies.json",
            "cipher_bytes": cipher_bytes,
            "cookie_count": cookie_count,
            "updated": datetime.now(timezone.utc).isoformat(),
        }
    )
    manifest["containers"] = containers
    manifest["generated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    manifest["protection"] = "DPAPI CurrentUser"
    VAULT_MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"  manifest updated: {VAULT_MANIFEST}")


def _append_vault_index(data: dict[str, Any], cookie_count: int) -> None:
    """Append AWS cookie metadata section to INDEX.md if missing/outdated."""
    summary = data.get("summary") or {}
    names = summary.get("cookie_names") or []
    lines = [
        "",
        "## AWS cookies (phone extract)",
        "",
        f"**Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "**Source store:** `~/.crcp/cookie-bridge/aws_cookies.json`",
        "**Container:** `aws-cookies.dpapi`",
        f"**Access portal:** `{AWS_ACCESS_PORTAL['host']}`",
        f"**Cookie count:** {cookie_count}",
        f"**Extracted at:** {data.get('extracted_at')}",
        "",
        "> **NO SECRET VALUES.** Names + domains + lengths only.",
        "",
        "| name | domain | path | len | httpOnly | secure |",
        "|---|---|---|---:|---|---|",
    ]
    for m in names:
        lines.append(
            f"| `{m.get('name')}` | `{m.get('domain')}` | `{m.get('path')}` | "
            f"{m.get('len')} | {m.get('httpOnly')} | {m.get('secure')} |"
        )
    lines.append("")
    section = "\n".join(lines)

    if VAULT_INDEX.is_file():
        text = VAULT_INDEX.read_text(encoding="utf-8")
        marker = "## AWS cookies (phone extract)"
        if marker in text:
            # replace existing section to end-of-file or next ##
            pre, rest = text.split(marker, 1)
            # drop rest until next top-level section that isn't continuation, keep trailing if any
            # simplest: truncate at marker and rewrite
            text = pre.rstrip() + "\n" + section
        else:
            text = text.rstrip() + "\n" + section
    else:
        text = (
            "# Secret Vault - INDEX\n\n"
            "> THIS FILE CONTAINS NO SECRET VALUES.\n" + section
        )
    VAULT_INDEX.write_text(text, encoding="utf-8")
    print(f"  INDEX updated: {VAULT_INDEX}")


def cmd_sync() -> dict[str, Any]:
    payload = cmd_extract()
    vault = cmd_vault()
    return {"extract_cookies": payload.get("cookie_count"), "vault": vault}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="AWS phone→PC web session bridge (extract/status/vault)"
    )
    parser.add_argument(
        "command",
        choices=["extract", "status", "vault", "sync"],
        help="extract | status | vault | sync",
    )
    args = parser.parse_args()
    if args.command == "extract":
        cmd_extract()
    elif args.command == "status":
        cmd_status()
    elif args.command == "vault":
        cmd_vault()
    elif args.command == "sync":
        cmd_sync()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
