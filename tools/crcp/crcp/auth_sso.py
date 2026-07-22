"""PKCE authorization-code login helpers for the CRCP Codex/API rail.

This module does not fabricate NextAuth cookies.  The returned bearer tokens
belong to the Codex/API plane, so the stock ChatGPT web UI may still require a
cookie bridge or its own interactive login.  OIDC discovery advertises only
``authorization_code`` and ``refresh_token`` grants; ``client_credentials`` is
not supported.

High-level login functions return metadata summaries, never raw credentials.
``save_token_bundle`` is an explicit escape hatch for a local operator and
writes sensitive material with owner-only permissions.  It is never called by
default and refuses to write into the CRCP results directory.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import socket
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Callable, Mapping


ISSUER = "https://auth.openai.com"
AUTHORIZE_URL = "https://auth.openai.com/api/accounts/authorize"
TOKEN_URL = "https://auth.openai.com/api/accounts/oauth/token"
DEFAULT_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
DEFAULT_SCOPES = "openid profile email offline_access"
DEFAULT_REDIRECT_URI = "http://127.0.0.1:1455/auth/callback"

_RESULTS_DIR = Path("/dbfs/tmp/crcp-auth-session/results")
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


class CallbackError(ValueError):
    """Raised when an OAuth callback is missing or fails validation."""


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def generate_code_verifier() -> str:
    """Return a high-entropy RFC 7636 verifier using URL-safe characters."""
    return _b64url(secrets.token_bytes(64))


def code_challenge_s256(verifier: str) -> str:
    """Derive the RFC 7636 S256 challenge for *verifier*."""
    if not 43 <= len(verifier) <= 128:
        raise ValueError("PKCE verifier length must be between 43 and 128 characters")
    allowed = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
    if any(char not in allowed for char in verifier):
        raise ValueError("PKCE verifier contains a character outside the RFC 7636 set")
    return _b64url(hashlib.sha256(verifier.encode("ascii")).digest())


def generate_state() -> str:
    """Return an unpredictable OAuth state value."""
    return secrets.token_urlsafe(32)


def generate_nonce() -> str:
    """Return an unpredictable OIDC nonce value."""
    return secrets.token_urlsafe(32)


def build_authorize_url(
    redirect_uri: str,
    *,
    client_id: str = DEFAULT_CLIENT_ID,
    scopes: str = DEFAULT_SCOPES,
    state: str,
    nonce: str,
    code_challenge: str,
) -> str:
    """Build an OIDC authorization URL for a public PKCE client."""
    if not all((redirect_uri, client_id, scopes, state, nonce, code_challenge)):
        raise ValueError("authorization URL parameters must be non-empty")
    query = urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scopes,
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"{AUTHORIZE_URL}?{query}"


def parse_callback_query(query: str, *, expected_state: str) -> str:
    """Validate a callback query and return its one-time authorization code."""
    if not expected_state:
        raise CallbackError("an expected OAuth state is required")
    query = urllib.parse.urlsplit(query).query if "://" in query else query.lstrip("?")
    fields = urllib.parse.parse_qs(query, keep_blank_values=True, strict_parsing=False)
    if "error" in fields:
        raise CallbackError("authorization server returned an OAuth error")
    if len(fields.get("state", [])) != 1:
        raise CallbackError("callback must contain exactly one state value")
    if not hmac.compare_digest(fields["state"][0], expected_state):
        raise CallbackError("OAuth state mismatch")
    if len(fields.get("code", [])) != 1 or not fields["code"][0]:
        raise CallbackError("callback must contain exactly one non-empty code")
    return fields["code"][0]


def _callback_parts(redirect_uri: str) -> tuple[str, int, str]:
    parts = urllib.parse.urlsplit(redirect_uri)
    if parts.scheme != "http" or (parts.hostname or "").lower() not in _LOOPBACK_HOSTS:
        raise ValueError("redirect URI must use HTTP on a loopback host")
    if parts.username is not None or parts.password is not None:
        raise ValueError("redirect URI must not contain user information")
    if parts.query or parts.fragment:
        raise ValueError("redirect URI must not contain a query or fragment")
    try:
        port = parts.port
    except ValueError as exc:
        raise ValueError("redirect URI has an invalid port") from exc
    if port is None or port == 0:
        raise ValueError("redirect URI must contain a non-zero port")
    return parts.hostname or "", port, parts.path or "/"


def _wait_for_callback(
    redirect_uri: str,
    timeout_s: int,
    expected_state: str,
    on_ready: Callable[[], None] | None = None,
) -> str:
    host, port, expected_path = _callback_parts(redirect_uri)
    result: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - inherited HTTP method name
            target = urllib.parse.urlsplit(self.path)
            if target.path != expected_path:
                self.send_error(404)
                return
            try:
                result["code"] = parse_callback_query(
                    target.query, expected_state=expected_state
                )
            except CallbackError as exc:
                result["error"] = str(exc)
                self.send_response(400)
                body = b"Authorization callback rejected. You may close this window."
            else:
                self.send_response(200)
                body = b"Authorization received. You may close this window."
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            # Request targets contain one-time authorization codes.
            return

    class Server(HTTPServer):
        address_family = socket.AF_INET6 if ":" in host else socket.AF_INET

    if timeout_s <= 0:
        raise ValueError("timeout_s must be positive")
    deadline = time.monotonic() + timeout_s
    with Server((host, port), Handler) as server:
        if on_ready is not None:
            on_ready()
        while "code" not in result and "error" not in result:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("timed out waiting for the OAuth callback")
            server.timeout = min(remaining, 1.0)
            server.handle_request()
    if "error" in result:
        raise CallbackError(result["error"])
    return result["code"]


def start_callback_server(
    redirect_uri: str,
    timeout_s: int = 300,
    *,
    expected_state: str,
) -> str:
    """Bind the redirect loopback endpoint and wait for a validated ``?code=``."""
    return _wait_for_callback(redirect_uri, timeout_s, expected_state)


def exchange_code_for_tokens(
    code: str,
    *,
    verifier: str,
    redirect_uri: str,
    client_id: str = DEFAULT_CLIENT_ID,
    timeout_s: int = 30,
) -> dict[str, Any]:
    """Exchange a code using public-client body parameters and no client secret."""
    if not code:
        raise ValueError("authorization code must be non-empty")
    code_challenge_s256(verifier)  # Validate before sending anything.
    payload = urllib.parse.urlencode(
        {
            "grant_type": "authorization_code",
            "client_id": client_id,
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
        }
    ).encode("ascii")
    request = urllib.request.Request(
        TOKEN_URL,
        data=payload,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # Do not include the response body: providers can echo sensitive fields.
        raise RuntimeError(f"token exchange failed with HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError("token exchange transport failed") from exc
    if not isinstance(data, dict):
        raise RuntimeError("token endpoint returned a non-object JSON response")
    return data


def prepare_profile_dir(path: Path | str) -> Path:
    """Create a dedicated controlled-browser profile directory.

    The caller should pass this directory as the browser's user-data directory.
    It is deliberately not populated from or pointed at the locked Desktop
    profile, and it does not copy cookies or credentials.
    """
    profile = Path(path).expanduser().resolve()
    if profile.exists() and not profile.is_dir():
        raise NotADirectoryError(str(profile))
    profile.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        profile.chmod(0o700)
    except OSError:
        # Windows ACLs do not map reliably to POSIX mode bits.
        pass
    return profile


def _decode_jwt_exp(token: str) -> int | None:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        raw = base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4))
        claims = json.loads(raw)
        exp = claims.get("exp")
        return int(exp) if exp is not None else None
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def export_auth_summary(tokens: Mapping[str, Any]) -> dict[str, Any]:
    """Return token presence, lengths, and expiry metadata without token values."""
    now = datetime.now(timezone.utc)
    summary: dict[str, Any] = {"token_fields": {}}
    for name in ("access_token", "id_token", "refresh_token"):
        value = tokens.get(name)
        present = isinstance(value, str) and bool(value)
        field: dict[str, Any] = {
            "present": present,
            "length": len(value) if present else 0,
        }
        if name != "refresh_token" and present:
            exp = _decode_jwt_exp(value)
            field["exp"] = exp
            try:
                field["exp_utc"] = (
                    datetime.fromtimestamp(exp, timezone.utc).isoformat()
                    if exp is not None
                    else None
                )
            except (OverflowError, OSError, ValueError):
                field["exp_utc"] = None
            field["expired"] = exp <= int(now.timestamp()) if exp is not None else None
        summary["token_fields"][name] = field
    expires_in = tokens.get("expires_in")
    summary["expires_in"] = expires_in if isinstance(expires_in, (int, float)) else None
    return summary


def save_token_bundle(path: Path | str, tokens: Mapping[str, Any]) -> Path:
    """WARNING: explicitly persist a sensitive token bundle with mode 0600.

    This is default-off operator functionality.  Never use a shared/report path,
    source tree, or log destination.  The caller owns lifecycle and deletion.
    """
    destination = Path(path).expanduser().resolve()
    try:
        destination.relative_to(_RESULTS_DIR.resolve())
    except ValueError:
        pass
    else:
        raise ValueError("refusing to save credentials in the CRCP results directory")
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.", dir=destination.parent
    )
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            fd = -1
            json.dump(dict(tokens), handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        try:
            destination.chmod(0o600)
        except OSError:
            pass
    except Exception:
        if fd >= 0:
            os.close(fd)
        try:
            Path(temporary).unlink()
        except FileNotFoundError:
            pass
        raise
    return destination


def run_sso_login(
    *,
    open_browser: bool = True,
    timeout_s: int = 300,
    print_url: bool = False,
    code: str | None = None,
    code_verifier: str | None = None,
    redirect_uri: str | None = None,
    client_id: str | None = None,
    scopes: str = DEFAULT_SCOPES,
) -> dict[str, Any]:
    """Run interactive PKCE login or prepare/complete a display-less flow.

    With ``print_url=True`` (or ``open_browser=False``), no server is started;
    the return value contains an authorization URL and continuation verifier.
    Pass the received ``code`` and that ``code_verifier`` on a later call to
    complete the exchange.  The returned completed status contains only safe
    token metadata.
    """
    effective_redirect = redirect_uri or os.environ.get(
        "CRCP_OAUTH_REDIRECT_URI", DEFAULT_REDIRECT_URI
    )
    effective_client = client_id or os.environ.get(
        "CRCP_OAUTH_CLIENT_ID", DEFAULT_CLIENT_ID
    )

    if code is not None:
        if not code_verifier:
            raise ValueError("code_verifier is required when completing with a code")
        tokens = exchange_code_for_tokens(
            code,
            verifier=code_verifier,
            redirect_uri=effective_redirect,
            client_id=effective_client,
        )
        return {"status": "complete", "auth_summary": export_auth_summary(tokens)}

    verifier = code_verifier or generate_code_verifier()
    state = generate_state()
    authorize_url = build_authorize_url(
        effective_redirect,
        client_id=effective_client,
        scopes=scopes,
        state=state,
        nonce=generate_nonce(),
        code_challenge=code_challenge_s256(verifier),
    )

    if print_url or not open_browser:
        return {
            "status": "authorization_required",
            "authorize_url": authorize_url,
            "code_verifier": verifier,
            "redirect_uri": effective_redirect,
        }

    def launch() -> None:
        if not webbrowser.open(authorize_url, new=1, autoraise=True):
            raise RuntimeError(
                "no browser accepted the authorization URL; use print_url mode"
            )

    received_code = _wait_for_callback(
        effective_redirect,
        timeout_s,
        state,
        on_ready=launch,
    )
    tokens = exchange_code_for_tokens(
        received_code,
        verifier=verifier,
        redirect_uri=effective_redirect,
        client_id=effective_client,
    )
    return {"status": "complete", "auth_summary": export_auth_summary(tokens)}
