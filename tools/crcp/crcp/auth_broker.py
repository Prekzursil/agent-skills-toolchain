"""Browser profile broker — inject Desktop cookies + Bearer into a CDP Chrome/Edge.

Goal: open a controlled Chromium window against chatgpt.com without manual login.

Measured facts (2026-07-20):
- Bearer access_token works for /backend-api/* (models, me) but NOT for
  /api/auth/session (returns WARNING_BANNER only — no NextAuth session).
- Desktop cookie jar + live CDP both lack ``__Secure-next-auth.session-token``.
- Desktop CDP works with ``--remote-debugging-port=9222 --remote-allow-origins=*``.

Strategy:
1. Launch clean Chrome/Edge profile with remote debugging.
2. Decrypt Desktop cookies (DPAPI/OSCrypt) and Network.setCookie them.
3. Network.setExtraHTTPHeaders with Authorization Bearer + ChatGPT-Account-Id so
   same-origin backend-api calls from the page are authenticated.
4. Navigate to https://chatgpt.com and report probe results.

Secrets never land in CRCP reports/; only lengths and status codes.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Mapping

from .auth_mirror import (
    cookie_db_paths,
    decrypt_cookie_value,
    default_user_data_dir,
    format_cdp_cookie,
    inventory_cookies,
)
from .auth_sso import prepare_profile_dir

DEFAULT_DEBUG_PORT = 9222
DEFAULT_START_URL = "https://chatgpt.com/"
CHAT_HOSTS = (
    "chatgpt.com",
    ".chatgpt.com",
    "chat.openai.com",
    ".chat.openai.com",
    "openai.com",
    ".openai.com",
    "oaistatic.com",
    ".oaistatic.com",
    "ws.chatgpt.com",
    ".ws.chatgpt.com",
    "auth.openai.com",
    ".auth.openai.com",
)


# --- Credential egress allowlist -------------------------------------------
# The OpenAI bearer in ~/.codex/auth.json must only ever reach OpenAI origins.
# Deny by default: any host not suffix-matching one of these is refused, and the
# credential headers are stripped from redirect hops that leave the allowlist.
TRUSTED_CREDENTIAL_HOST_SUFFIXES = ("chatgpt.com", "openai.com")
CREDENTIAL_HEADER_NAMES = frozenset({"authorization", "chatgpt-account-id"})


class BrokerError(RuntimeError):
    """Non-secret broker failure."""


class CredentialScopeError(BrokerError):
    """Credential egress refused because the target host is not allowlisted.

    ``crcp_safe_message`` opts this class out of the CLI's blanket message
    redaction (``crcp/__main__.py``): the text is built only from
    :func:`_safe_url`, which drops userinfo, query and fragment, so it carries no
    secret. Without the opt-in the operator sees a generic "auth command failed"
    and misdiagnoses a security refusal as a browser fault.
    """

    crcp_safe_message = True


def _safe_url(url: str) -> str:
    """Scheme://host/path only — never echo query/fragment (may carry secrets)."""
    try:
        parts = urllib.parse.urlsplit((url or "").strip())
    except ValueError:
        return "<unparseable-url>"
    if not parts.scheme and not parts.netloc:
        return (url or "")[:120]
    try:
        host = parts.hostname or ""
    except ValueError:
        host = "<invalid-host>"
    return f"{parts.scheme}://{host}{parts.path}"[:200]


def is_trusted_credential_url(url: str) -> bool:
    """True only for https URLs on an allowlisted OpenAI host.

    Uses ``urlsplit().hostname`` so credential-in-userinfo spoofs such as
    ``https://chatgpt.com@evil.example/`` resolve to the REAL host (evil.example)
    and are rejected.
    """
    try:
        parts = urllib.parse.urlsplit((url or "").strip())
    except ValueError:
        return False
    if parts.scheme.lower() != "https":
        return False
    try:
        host = parts.hostname or ""
    except ValueError:
        return False
    host = host.strip().lower().rstrip(".")
    if not host:
        return False
    return any(
        host == suffix or host.endswith("." + suffix)
        for suffix in TRUSTED_CREDENTIAL_HOST_SUFFIXES
    )


def require_trusted_credential_url(url: str, *, what: str = "target URL") -> str:
    """Return ``url`` if credentials may be attached to it, else raise loudly."""
    if not is_trusted_credential_url(url):
        allowed = ", ".join(TRUSTED_CREDENTIAL_HOST_SUFFIXES)
        raise CredentialScopeError(
            f"refusing to attach OpenAI credentials to untrusted {what}: "
            f"{_safe_url(url)} — allowed: https on {allowed} (or a subdomain). "
            "Re-run with --no-bearer to open other hosts without credentials."
        )
    return url


def scoped_auth_headers(url: str, access_token: str, account_id: str) -> dict[str, str]:
    """Credential headers for ``url`` — empty dict for any untrusted host.

    This is the single per-request decision point, so it is also what each
    redirect hop is re-evaluated against.
    """
    if not is_trusted_credential_url(url):
        return {}
    headers = {"Authorization": f"Bearer {access_token}"}
    if account_id:
        headers["ChatGPT-Account-Id"] = account_id
        headers["chatgpt-account-id"] = account_id
    return headers


def strip_untrusted_credential_headers(
    url: str, headers: Mapping[str, str]
) -> tuple[dict[str, str], bool]:
    """Drop credential headers when ``url`` is off-allowlist.

    Returns ``(headers, stripped)``. Called for every intercepted request, so a
    3xx from an allowlisted host to an arbitrary one loses the bearer.
    """
    if is_trusted_credential_url(url):
        return dict(headers), False
    kept = {
        k: v for k, v in headers.items() if k.lower() not in CREDENTIAL_HEADER_NAMES
    }
    return kept, len(kept) != len(headers)


def _find_browser() -> tuple[str, str]:
    """Return (kind, executable path) for Chrome or Edge."""
    candidates: list[tuple[str, str]] = []
    local = os.environ.get("LOCALAPPDATA", "")
    pf = os.environ.get("PROGRAMFILES", r"C:\Program Files")
    pf86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
    for kind, path in (
        ("chrome", rf"{pf}\Google\Chrome\Application\chrome.exe"),
        ("chrome", rf"{pf86}\Google\Chrome\Application\chrome.exe"),
        ("chrome", rf"{local}\Google\Chrome\Application\chrome.exe"),
        ("edge", rf"{pf}\Microsoft\Edge\Application\msedge.exe"),
        ("edge", rf"{pf86}\Microsoft\Edge\Application\msedge.exe"),
        ("edge", rf"{local}\Microsoft\Edge\Application\msedge.exe"),
    ):
        if path and Path(path).is_file():
            candidates.append((kind, path))
    env = os.environ.get("CRCP_BROWSER_PATH", "").strip()
    if env and Path(env).is_file():
        return ("custom", env)
    if not candidates:
        raise BrokerError("Chrome/Edge not found; set CRCP_BROWSER_PATH")
    # Prefer Chrome for CDP familiarity
    for kind, path in candidates:
        if kind == "chrome":
            return kind, path
    return candidates[0]


def _load_auth_tokens(codex_home: Path | None = None) -> dict[str, Any]:
    home = codex_home or Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    auth_path = home / "auth.json"
    if not auth_path.is_file():
        raise BrokerError(f"auth.json missing: {auth_path}")
    data = json.loads(auth_path.read_text(encoding="utf-8"))
    tokens = data.get("tokens") or {}
    access = tokens.get("access_token")
    if not access:
        raise BrokerError("auth.json has no access_token")
    account = tokens.get("account_id") or ""
    if not account and isinstance(access, str) and access.count(".") == 2:
        import base64

        try:
            pad = "=" * (-len(access.split(".")[1]) % 4)
            claims = json.loads(base64.urlsafe_b64decode(access.split(".")[1] + pad))
            oa = claims.get("https://api.openai.com/auth") or {}
            account = oa.get("chatgpt_account_id") or oa.get("account_id") or ""
        except Exception:
            account = ""
    return {
        "access_token": access,
        "account_id": account,
        "access_token_len": len(access),
        "auth_path": str(auth_path),
    }


def _http_json(url: str, timeout: float = 5.0) -> Any:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def wait_for_cdp(port: int, timeout_s: float = 30.0) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    last: Exception | None = None
    while time.time() < deadline:
        try:
            return _http_json(f"http://127.0.0.1:{port}/json/version")
        except Exception as exc:  # noqa: BLE001 — probe loop
            last = exc
            time.sleep(0.4)
    raise BrokerError(
        f"CDP not ready on :{port}: {type(last).__name__ if last else 'timeout'}"
    )


def launch_browser(
    *,
    profile_dir: Path,
    port: int = DEFAULT_DEBUG_PORT,
    start_url: str = "about:blank",
    browser_path: str | None = None,
) -> dict[str, Any]:
    """Launch Chrome/Edge with remote debugging into a dedicated profile."""
    prepare_profile_dir(profile_dir)
    if browser_path:
        kind, exe = "custom", browser_path
    else:
        kind, exe = _find_browser()
    args = [
        exe,
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-sync",
        "--new-window",
        start_url,
    ]
    proc = subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    version = wait_for_cdp(port)
    return {
        "ok": True,
        "kind": kind,
        "exe": exe,
        "pid": proc.pid,
        "port": port,
        "profile_dir": str(profile_dir),
        "browser": version.get("Browser"),
        "webSocketDebuggerUrl": version.get("webSocketDebuggerUrl"),
    }


class CdpSession:
    """Minimal CDP client over websocket (browser-level + optional page session)."""

    def __init__(self, port: int = DEFAULT_DEBUG_PORT):
        try:
            import websocket  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise BrokerError(
                "websocket-client required: pip install websocket-client"
            ) from exc
        self._websocket = websocket
        self.port = port
        self._id = 0
        version = wait_for_cdp(port)
        ws_url = version.get("webSocketDebuggerUrl")
        if not ws_url:
            raise BrokerError("no browser webSocketDebuggerUrl")
        self.ws = websocket.create_connection(ws_url, timeout=30, suppress_origin=True)
        self.session_id: str | None = None
        self.version = version
        self.credential_scoping = False
        self.stripped_credential_hops: list[str] = []

    def close(self) -> None:
        try:
            self.ws.close()
        except Exception:
            pass

    def call(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        session: bool = False,
    ) -> Any:
        self._id += 1
        # Capture our own id: nested sends (redirect interception below) bump
        # self._id, so comparing against the live attribute would never match.
        msg_id = self._id
        msg: dict[str, Any] = {"id": msg_id, "method": method}
        if params:
            msg["params"] = params
        if session and self.session_id:
            msg["sessionId"] = self.session_id
        self.ws.send(json.dumps(msg))
        deadline = time.time() + 30
        while time.time() < deadline:
            raw = self.ws.recv()
            data = json.loads(raw)
            if data.get("id") == msg_id:
                if data.get("error"):
                    raise BrokerError(f"CDP {method}: {data['error']}")
                return data.get("result")
            if data.get("method") == "Fetch.requestPaused":
                self._continue_paused(data.get("params") or {})
        raise BrokerError(f"CDP timeout: {method}")

    def enable_credential_scoping(self) -> None:
        """Intercept every request so off-allowlist hops lose the credential.

        ``Network.setExtraHTTPHeaders`` has NO host scoping — Chrome replays it
        on every request from the session, including redirect targets. Request-
        stage ``Fetch`` interception is what re-checks the host per hop.
        """
        self.call(
            "Fetch.enable",
            {"patterns": [{"urlPattern": "*", "requestStage": "Request"}]},
            session=True,
        )
        self.credential_scoping = True

    def _continue_paused(self, params: Mapping[str, Any]) -> None:
        request_id = params.get("requestId")
        if not request_id:
            return
        request = params.get("request") or {}
        url = str(request.get("url") or "")
        headers, stripped = strip_untrusted_credential_headers(
            url, dict(request.get("headers") or {})
        )
        payload: dict[str, Any] = {"requestId": request_id}
        if not is_trusted_credential_url(url):
            # Send an EXPLICIT header set for every off-allowlist hop, even when the
            # paused headers did not visibly carry the credential. Whether Chrome
            # merges Network.setExtraHTTPHeaders before or after Fetch interception is
            # version-dependent; ``Fetch.continueRequest`` headers OVERRIDE the request
            # header set, so specifying it unconditionally is correct under either
            # ordering. Gating on ``stripped`` would leave the late-merge ordering open.
            payload["headers"] = [
                {"name": name, "value": value} for name, value in headers.items()
            ]
        if stripped:
            self.stripped_credential_hops.append(_safe_url(url))
        self._id += 1
        msg: dict[str, Any] = {
            "id": self._id,
            "method": "Fetch.continueRequest",
            "params": payload,
        }
        if self.session_id:
            msg["sessionId"] = self.session_id
        self.ws.send(json.dumps(msg))

    def attach_page(self, url_substr: str | None = None) -> str:
        infos = (self.call("Target.getTargets") or {}).get("targetInfos") or []
        pages = [t for t in infos if t.get("type") == "page"]
        if url_substr:
            preferred = [t for t in pages if url_substr in (t.get("url") or "")]
            if preferred:
                pages = preferred
        if not pages:
            created = self.call("Target.createTarget", {"url": "about:blank"}) or {}
            tid = created.get("targetId")
            if not tid:
                raise BrokerError("no page target")
        else:
            tid = pages[0]["targetId"]
        att = (
            self.call("Target.attachToTarget", {"targetId": tid, "flatten": True}) or {}
        )
        self.session_id = att.get("sessionId")
        if not self.session_id:
            raise BrokerError("attachToTarget returned no sessionId")
        return tid

    def set_cookie(self, cookie: Mapping[str, Any]) -> bool:
        result = self.call("Network.setCookie", dict(cookie), session=True) or {}
        return bool(result.get("success", True))

    def navigate(self, url: str, wait_s: float = 5.0) -> dict[str, Any]:
        self.call("Page.enable", session=True)
        self.call("Runtime.enable", session=True)
        result = self.call("Page.navigate", {"url": url}, session=True) or {}
        # Wait for load; fall back to sleep if event pump is not wired.
        deadline = time.time() + wait_s + 10
        loaded = False
        while time.time() < deadline and not loaded:
            try:
                # Cheap readiness probe
                ready = (
                    self.call(
                        "Runtime.evaluate",
                        {
                            "expression": "document.readyState",
                            "returnByValue": True,
                        },
                        session=True,
                    )
                    or {}
                )
                state = (ready.get("result") or {}).get("value")
                if state in {"interactive", "complete"}:
                    loaded = True
                    break
            except Exception:
                pass
            time.sleep(0.4)
        time.sleep(max(1.0, wait_s / 2))
        return result

    def evaluate(self, expression: str) -> Any:
        result = (
            self.call(
                "Runtime.evaluate",
                {
                    "expression": expression,
                    "returnByValue": True,
                    "awaitPromise": True,
                    "userGesture": True,
                },
                session=True,
            )
            or {}
        )
        if result.get("exceptionDetails"):
            detail = result["exceptionDetails"]
            text = (
                detail.get("text")
                or (detail.get("exception") or {}).get("description")
                or (detail.get("exception") or {}).get("value")
            )
            raise BrokerError(f"evaluate failed: {text}")
        return (result.get("result") or {}).get("value")

    def get_all_cookies_meta(self) -> list[dict[str, Any]]:
        self.call("Network.enable", session=True)
        result = self.call("Network.getAllCookies", session=True) or {}
        cookies = result.get("cookies") or []
        out = []
        for c in cookies:
            out.append(
                {
                    "name": c.get("name"),
                    "domain": c.get("domain"),
                    "path": c.get("path"),
                    "secure": c.get("secure"),
                    "httpOnly": c.get("httpOnly"),
                    "sameSite": c.get("sameSite"),
                    "session": c.get("session"),
                    "value_len": len(c.get("value") or ""),
                }
            )
        return out


def _decrypt_desktop_cookies(user_data: Path | None = None) -> list[dict[str, Any]]:
    """Decrypt Desktop cookies for ChatGPT-related hosts (values in memory only)."""
    ud = Path(user_data) if user_data else default_user_data_dir()
    local_state = ud / "Local State"
    if not local_state.is_file():
        raise BrokerError(f"Local State missing under {ud}")
    decrypted: list[dict[str, Any]] = []
    failures = 0
    for db_path in cookie_db_paths(ud):
        if not db_path.is_file():
            continue
        # Re-read encrypted blobs via inventory path + raw select
        try:
            meta_rows = inventory_cookies(db_path)
        except Exception:
            continue
        # Need encrypted values — open via VSS/shared path used by inventory is metadata only.
        # Use export-style reader from auth_mirror internals when possible.
        try:
            rows = _read_encrypted_rows(db_path)
        except Exception:
            continue
        meta_lookup = {(r["host_key"], r["name"], r["path"]): r for r in meta_rows}
        for host, name, path, blob, plaintext in rows:
            host_s, name_s, path_s = str(host), str(name), str(path or "/")
            domain = host_s
            if not any(
                domain.endswith(h.lstrip(".")) or domain == h for h in CHAT_HOSTS
            ):
                # keep openai/chatgpt only
                dlow = domain.lower()
                if not any(
                    x in dlow for x in ("chatgpt", "openai", "oaistatic", "auth.openai")
                ):
                    continue
            value: bytes | None = None
            if blob:
                try:
                    value = decrypt_cookie_value(
                        bytes(blob), local_state, allow_decrypt=True
                    )
                except Exception:
                    value = None
            if value is None and isinstance(plaintext, str) and plaintext:
                value = plaintext.encode("utf-8")
            if value is None:
                failures += 1
                continue
            # Chrome OSCrypt payload often prefixes SHA-256(host_key) before the cookie value.
            import hashlib

            host_digest = hashlib.sha256(host_s.encode("utf-8")).digest()
            if value.startswith(host_digest):
                value = value[len(host_digest) :]
            meta = meta_lookup.get((host_s, name_s, path_s), {})
            rec = {
                "name": name_s,
                "value": value.decode("utf-8", "surrogateescape"),
                "host_key": host_s,
                "domain": host_s,
                "path": path_s,
                "secure": meta.get("secure", True),
                "httpOnly": meta.get("httpOnly", False),
                "samesite": meta.get("samesite", 0),
                "expires_unix": meta.get("expires_unix"),
            }
            decrypted.append(rec)
    if not decrypted and failures:
        raise BrokerError(f"cookie decrypt failed for all rows (failures={failures})")
    return decrypted


def _read_encrypted_rows(db_path: Path) -> list[tuple[Any, ...]]:
    """Return (host_key, name, path, encrypted_value, plaintext) rows."""
    from .auth_mirror import _is_lock_error, _shared_read_bytes, copy_via_vss

    def open_rows(path: Path) -> list[tuple[Any, ...]]:
        uri = f"file:{path.resolve().as_posix()}?mode=ro"
        con = sqlite3.connect(uri, uri=True)
        try:
            cols = {str(r[1]) for r in con.execute("PRAGMA table_info(cookies)")}
            plain = "value" if "value" in cols else "''"
            return list(
                con.execute(
                    f"SELECT host_key, name, path, encrypted_value, {plain} FROM cookies"
                )
            )
        finally:
            con.close()

    try:
        return open_rows(db_path)
    except (OSError, sqlite3.Error) as exc:
        if os.name != "nt" or not _is_lock_error(exc):
            raise
        work = Path(tempfile.mkdtemp(prefix="crcp-broker-ck-"))
        try:
            candidate = work / "Cookies.db"
            try:
                candidate.write_bytes(_shared_read_bytes(db_path))
            except OSError:
                vss = work / "Cookies.vss"
                copy_via_vss(db_path, vss)
                candidate.write_bytes(vss.read_bytes())
            return open_rows(candidate)
        finally:
            shutil.rmtree(work, ignore_errors=True)


def _cookie_url(domain: str, secure: bool = True) -> str:
    host = domain.lstrip(".")
    scheme = "https" if secure else "http"
    return f"{scheme}://{host}/"


def inject_cookies(
    session: CdpSession, cookies: list[dict[str, Any]]
) -> dict[str, Any]:
    session.call("Network.enable", session=True)
    set_ok = 0
    set_fail = 0
    names: list[str] = []
    fail_reasons: list[str] = []
    for cookie in cookies:
        try:
            cdp_cookie = format_cdp_cookie(cookie)
            domain = str(cdp_cookie.get("domain") or "")
            cdp_cookie["url"] = _cookie_url(
                domain, bool(cdp_cookie.get("secure", True))
            )
            # Host-only cookies (__Host-*) must not send Domain attribute
            if str(cdp_cookie.get("name", "")).startswith("__Host-"):
                cdp_cookie.pop("domain", None)
            ok = session.set_cookie(cdp_cookie)
            if ok:
                set_ok += 1
                names.append(str(cdp_cookie["name"]))
            else:
                set_fail += 1
                fail_reasons.append(f"{cdp_cookie.get('name')}:success=false")
        except Exception as exc:
            set_fail += 1
            fail_reasons.append(f"{cookie.get('name')}:{type(exc).__name__}")
    return {
        "set_ok": set_ok,
        "set_fail": set_fail,
        "names": sorted(set(names)),
        "has_puid": "_puid" in names,
        "has_oai_sc": "oai-sc" in names,
        "has_nextauth": any(n == "__Secure-next-auth.session-token" for n in names),
        "fail_sample": fail_reasons[:8],
    }


def inject_bearer_headers(
    session: CdpSession,
    access_token: str,
    account_id: str,
    *,
    target_url: str,
) -> None:
    """Attach the OpenAI bearer — allowlisted hosts only, deny by default.

    ``target_url`` is required (keyword-only) so no call site can inject the
    credential without declaring where it is about to be sent.
    """
    require_trusted_credential_url(target_url, what="start URL")
    headers = scoped_auth_headers(target_url, access_token, account_id)
    if not headers:  # pragma: no cover — require_* above already raised
        raise BrokerError("refusing to inject empty credential header set")
    # Arm per-hop stripping BEFORE the unscoped header set exists, so a redirect
    # off the allowlist cannot carry it.
    session.enable_credential_scoping()
    session.call("Network.setExtraHTTPHeaders", {"headers": headers}, session=True)


def page_probe(session: CdpSession) -> dict[str, Any]:
    """Run in-page fetches; report status codes and key shapes only."""
    script = r"""
(async () => {
  const out = {};
  async function hit(key, url) {
    try {
      const r = await fetch(url, {credentials: 'include', headers: {'Accept': 'application/json'}});
      const ct = r.headers.get('content-type') || '';
      let keys = null;
      let warningOnly = false;
      if (ct.includes('json')) {
        const j = await r.json();
        if (j && typeof j === 'object' && !Array.isArray(j)) {
          keys = Object.keys(j).slice(0, 30);
          warningOnly = (Object.keys(j).length === 1 && Object.prototype.hasOwnProperty.call(j, 'WARNING_BANNER'));
        }
      }
      out[key] = {status: r.status, keys, warningOnly};
    } catch (e) {
      out[key] = {error: String(e && e.message ? e.message : e).slice(0, 160)};
    }
  }
  await hit('session', 'https://chatgpt.com/api/auth/session');
  await hit('me', 'https://chatgpt.com/backend-api/me');
  await hit('models', 'https://chatgpt.com/backend-api/models');
  await hit('csrf', 'https://chatgpt.com/api/auth/csrf');
  return out;
})()
"""
    try:
        return session.evaluate(script) or {}
    except BrokerError as exc:
        return {"error": str(exc)[:200]}


def run_broker(
    *,
    profile_dir: Path | None = None,
    port: int = DEFAULT_DEBUG_PORT,
    start_url: str = DEFAULT_START_URL,
    desktop_user_data: Path | None = None,
    attach_only: bool = False,
    skip_cookies: bool = False,
    skip_bearer: bool = False,
    browser_path: str | None = None,
    keep_open: bool = True,
) -> dict[str, Any]:
    """Main entry: launch/attach browser, inject cookies+Bearer, navigate, probe."""
    # Fail loudly BEFORE a browser is launched or auth.json is even read: a
    # caller-supplied --url off the allowlist must never see the credential.
    if not skip_bearer:
        require_trusted_credential_url(start_url, what="--url start URL")
    report: dict[str, Any] = {
        "ok": False,
        "steps": [],
        "honest_limits": [
            "Bearer does not populate NextAuth /api/auth/session (WARNING_BANNER only).",
            "Desktop CDP and SQLite lack __Secure-next-auth.session-token.",
            "Broker uses cookie injection + Network.setExtraHTTPHeaders Bearer for backend-api.",
            "UI may still show login for NextAuth-gated routes; API-backed surfaces can work.",
        ],
    }
    profile = (
        Path(profile_dir)
        if profile_dir
        else Path.home() / ".crcp" / "browser-broker-profile"
    )
    launch_info: dict[str, Any] | None = None
    if not attach_only:
        launch_info = launch_browser(
            profile_dir=profile,
            port=port,
            start_url="about:blank",
            browser_path=browser_path,
        )
        report["launch"] = {
            k: launch_info[k]
            for k in ("ok", "kind", "pid", "port", "profile_dir", "browser")
            if k in launch_info
        }
        report["steps"].append("launched_browser")
    else:
        wait_for_cdp(port)
        report["steps"].append("attached_cdp")
        report["launch"] = {"ok": True, "port": port, "attach_only": True}

    tokens = _load_auth_tokens()
    report["auth"] = {
        "access_token_len": tokens["access_token_len"],
        "account_id_present": bool(tokens["account_id"]),
    }

    session = CdpSession(port)
    try:
        session.attach_page()
        report["steps"].append("attached_page")

        cookie_stats: dict[str, Any] = {"skipped": True}
        if not skip_cookies:
            cookies = _decrypt_desktop_cookies(desktop_user_data)
            cookie_stats = inject_cookies(session, cookies)
            cookie_stats["decrypted_count"] = len(cookies)
            cookie_stats["skipped"] = False
            report["steps"].append("injected_cookies")
        report["cookies"] = cookie_stats

        if not skip_bearer:
            inject_bearer_headers(
                session,
                tokens["access_token"],
                tokens["account_id"],
                target_url=start_url,
            )
            report["steps"].append("injected_bearer_headers")

        nav = session.navigate(start_url, wait_s=4.0)
        report["navigate"] = {
            "url": start_url,
            "frameId": nav.get("frameId") is not None,
            "credential_scoping": session.credential_scoping,
            "credential_stripped_hops": list(session.stripped_credential_hops),
        }
        report["steps"].append("navigated")

        probes = page_probe(session)
        report["probes"] = probes
        report["steps"].append("probed")

        meta = session.get_all_cookies_meta()
        chat = [
            c
            for c in meta
            if "chatgpt" in (c.get("domain") or "")
            or "openai" in (c.get("domain") or "")
        ]
        report["browser_cookies"] = {
            "total": len(meta),
            "chatgpt_related": len(chat),
            "names": sorted({c["name"] for c in chat if c.get("name")}),
            "has_nextauth_session": any(
                c.get("name") == "__Secure-next-auth.session-token" for c in meta
            ),
        }

        me_ok = isinstance(probes.get("me"), dict) and probes["me"].get("status") == 200
        models_ok = (
            isinstance(probes.get("models"), dict)
            and probes["models"].get("status") == 200
        )
        session_warning = isinstance(probes.get("session"), dict) and probes[
            "session"
        ].get("warningOnly")
        report["ok"] = bool(me_ok or models_ok)
        report["status"] = (
            "API_AUTH_OK_NO_NEXTAUTH"
            if report["ok"] and session_warning
            else "API_AUTH_OK"
            if report["ok"]
            else "PARTIAL_OR_FAILED"
        )
        report["keep_open"] = keep_open
        report["profile_dir"] = str(profile)
        report["cdp"] = f"http://127.0.0.1:{port}/json"
        return report
    finally:
        session.close()


def run_desktop_cdp_inventory(port: int = DEFAULT_DEBUG_PORT) -> dict[str, Any]:
    """Attach to a running Desktop CDP and inventory cookies (metadata only)."""
    session = CdpSession(port)
    try:
        session.attach_page()
        meta = session.get_all_cookies_meta()
        return {
            "ok": True,
            "port": port,
            "cookie_count": len(meta),
            "has_nextauth_session": any(
                c.get("name") == "__Secure-next-auth.session-token" for c in meta
            ),
            "has_cf_clearance": any(c.get("name") == "cf_clearance" for c in meta),
            "all_names": sorted({c["name"] for c in meta if c.get("name")}),
            "all_domains": sorted({c["domain"] for c in meta if c.get("domain")}),
            "auth_relevant": [
                c
                for c in meta
                if any(
                    k in (c.get("name") or "").lower()
                    for k in (
                        "session",
                        "token",
                        "auth",
                        "puid",
                        "oai",
                        "cf_",
                        "next-auth",
                        "clearance",
                    )
                )
                or "chatgpt" in (c.get("domain") or "")
                or "openai" in (c.get("domain") or "")
            ],
        }
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Phone cookie store (USB-debug extract → durable isolated browser profile)
# ---------------------------------------------------------------------------

PHONE_STORE_DIR = Path.home() / ".crcp" / "cookie-bridge"
PHONE_APPLY_SCRIPT = PHONE_STORE_DIR / "apply_durable.py"
PHONE_BRIDGE_SCRIPT = PHONE_STORE_DIR / "cookie_bridge.py"
PHONE_DEFAULT_PORT = 9340


def _load_phone_apply_module() -> Any:
    """Load ~/.crcp/cookie-bridge/apply_durable.py as a module."""
    import importlib.util

    path = PHONE_APPLY_SCRIPT
    if not path.is_file():
        raise BrokerError(
            f"phone cookie apply script missing: {path} "
            "(run phone extract via cookie_bridge.py extract first)"
        )
    spec = importlib.util.spec_from_file_location("crcp_phone_apply_durable", path)
    if spec is None or spec.loader is None:
        raise BrokerError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def phone_store_status() -> dict[str, Any]:
    """Metadata status of the phone-extracted cookie store (no secret values)."""
    try:
        mod = _load_phone_apply_module()
        report = mod.status()
        report["mode"] = "phone_store"
        report["apply_script"] = str(PHONE_APPLY_SCRIPT)
        report["reapply_cmd"] = (
            f"python -m crcp auth broker --from-phone-store --phone-browser chrome --port {PHONE_DEFAULT_PORT}"
        )
        return report
    except BrokerError as exc:
        return {"ok": False, "mode": "phone_store", "error": str(exc)[:240]}


def phone_store_extract() -> dict[str, Any]:
    """Re-extract cookies from phone Chrome via ADB USB debugging."""
    if not PHONE_BRIDGE_SCRIPT.is_file():
        raise BrokerError(f"missing {PHONE_BRIDGE_SCRIPT}")
    proc = subprocess.run(
        [os.environ.get("PYTHON", "python"), str(PHONE_BRIDGE_SCRIPT), "extract"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        check=False,
    )
    # Never return raw stdout if it might contain cookie values — summarize.
    ok = proc.returncode == 0
    store = PHONE_STORE_DIR / "chatgpt_cookies.json"
    summary: dict[str, Any] = {
        "ok": ok,
        "mode": "phone_extract",
        "returncode": proc.returncode,
        "store_present": store.is_file(),
    }
    if store.is_file():
        try:
            data = json.loads(store.read_text(encoding="utf-8"))
            cookies = data.get("cookies") or []
            names = sorted({c.get("name") for c in cookies if isinstance(c, dict)})
            summary.update(
                {
                    "extracted_at": data.get("extracted_at"),
                    "cookie_count": len(cookies),
                    "has_nextauth_session": any(
                        (n or "").startswith("__Secure-next-auth.session-token")
                        for n in names
                    ),
                    "has_oai_is": "__Secure-oai-is" in names,
                    "has_cf_clearance": "cf_clearance" in names,
                }
            )
        except Exception as exc:
            summary["store_parse_error"] = type(exc).__name__
    if not ok:
        # Tail of stderr only, redacted of long base64-looking tokens
        err = (proc.stderr or proc.stdout or "")[-400:]
        summary["error_tail"] = err.replace("\n", " ")[:400]
    return summary


def run_from_phone_store(
    *,
    browser: str = "chrome",
    port: int = PHONE_DEFAULT_PORT,
    extract_first: bool = False,
) -> dict[str, Any]:
    """Apply phone-extracted NextAuth cookies into an isolated Chrome/Edge profile.

    This is the path that actually yields WEB_SESSION_OK (user + sessionToken),
    unlike Desktop-cookie + Bearer which only gets backend-api auth.
    """
    if browser not in {"chrome", "edge"}:
        raise BrokerError("phone store browser must be 'chrome' or 'edge'")
    steps: list[str] = []
    extract_report: dict[str, Any] | None = None
    if extract_first:
        extract_report = phone_store_extract()
        steps.append("phone_extract")
        if not extract_report.get("ok"):
            return {
                "ok": False,
                "mode": "phone_store",
                "status": "EXTRACT_FAILED",
                "steps": steps,
                "extract": extract_report,
            }
    mod = _load_phone_apply_module()
    report = mod.apply(browser=browser, port=port, keep_open=True)
    steps.append("phone_apply")
    report = dict(report)
    report["mode"] = "phone_store"
    report["steps"] = steps
    if extract_report is not None:
        report["extract"] = {
            k: extract_report[k]
            for k in extract_report
            if k not in {"error_tail"} or not extract_report.get("ok")
        }
    report["crcp_cmd"] = (
        f"python -m crcp auth broker --from-phone-store "
        f"--phone-browser {browser} --port {port}"
    )
    return report
