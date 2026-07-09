#!/usr/bin/env python3
"""Biomni Lab MCP wrapper -- a thin FastMCP server over Phylo's ``api.phylo.bio/v2``.

This drives the HOSTED Biomni Lab (https://biomni.phylo.bio, by Phylo Inc.) far
beyond the official 10-tool claude.ai connector: it exposes EFFORT control
(``model_profile`` standard|fast|premium), skill + ``@``-resource attachment, live
runtime introspection (background processes, GPU sandboxes, HPC jobs/pipelines,
machines), usage/billing, and a raw escape hatch to any ``/v2`` endpoint. The REST
surface was reverse-engineered from the app's own network traffic; there is no
published SDK, so every call is a plain Bearer-authenticated JSON request built on
the stdlib (``urllib``) -- ZERO new dependencies, mirroring the compute providers.

Tool names are PRE-NAMESPACED (``bm_*``) so the cloud-hub's collision-prefix never
has to fire. Auth is LAZY -- the token is read per call, not at import -- so
``tools/list`` enumerates for the hub cache even with no ``BIOMNI_TOKEN`` set; a
call without it returns a clear auth hint instead of crashing.

Auth: ``BIOMNI_TOKEN`` = a Bearer access token from a signed-in Biomni session
(WorkOS-issued; there is no API-key product yet, so it is refreshed by the user
when it expires). The cloud-hub injects the ACTIVE ``biomni`` account's token when
it spawns this child, so ``bm_account_switch``/``bm_account_cycle`` rotate between
the user's Biomni accounts (each a ``{BIOMNI_TOKEN: ...}`` env bundle, email-labelled).

$$$ awareness: creating a session and starting processing consume the account's
Biomni usage/credits (the agent runs on real HPC/GPU). ``bm_billing_balance`` /
``bm_billing_subscription`` report remaining usage so a caller can rotate accounts
BEFORE one runs dry. The genuinely destructive raw verbs (a ``DELETE`` via
``bm_api_raw``) are the caller's responsibility -- confirm intent first.

Task flow: ``bm_create_session`` (pick ``model_profile`` = effort) then either let
``submit_initial_message`` kick the first run, or compose ``bm_send_message``
(``content`` with ``@resource`` mentions + ``attached_skills``) -> ``bm_start_processing``.
Poll with ``bm_get_messages`` (reliable) or ``bm_get_streaming`` (best-effort live).
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("biomni")

# Reverse-engineered from the biomni.phylo.bio SPA traffic. Most endpoints live
# under /v2; billing + identity-hash sit at the root (no /v2 prefix).
API_BASE = os.environ.get("BIOMNI_API_BASE", "https://api.phylo.bio").rstrip("/")
WEB_BASE = os.environ.get("BIOMNI_WEB_BASE", "https://biomni.phylo.bio").rstrip("/")
TIMEOUT = 45.0  # seconds for a normal request
STREAM_TIMEOUT = 12.0  # streaming is best-effort; keep the block short
_MAX_CHARS = 200_000  # cap a single tool result so it can't flood the JSON-RPC stream

# The three effort tiers the app calls "Standard / Fast / Max" (GET
# /v2/agent/model-profiles). ``max`` is accepted as a friendly alias for premium.
_PROFILE_ALIASES = {
    "max": "premium",
    "standard": "standard",
    "fast": "fast",
    "premium": "premium",
}
# Valid runtime-introspection sub-resources under /v2/agent/{sess}/...
_RUNTIME_KINDS = (
    "background-processes",
    "gpu-sandboxes",
    "hpc-jobs",
    "hpc-pipelines",
    "machines",
)

# OAuth 2.0 device-code + refresh (RFC 8628) against Phylo's WorkOS issuer.
# Verified from signin.phylo.bio/.well-known/oauth-authorization-server: a PUBLIC
# client (token_endpoint_auth_method "none" -> NO client secret), with a
# device_authorization + token endpoint, grants incl. device_code + refresh_token,
# and the offline_access scope. So the user authorizes in a browser (device flow)
# and the connector auto-mints access tokens from the resulting refresh token --
# BIOMNI_TOKEN then never has to be pasted/refreshed by hand.
SIGNIN_BASE = os.environ.get("BIOMNI_SIGNIN_BASE", "https://signin.phylo.bio").rstrip(
    "/"
)
OAUTH_CLIENT_ID = os.environ.get(
    "BIOMNI_CLIENT_ID", "client_01KEFGHEBJP3XMFBQ0TR34DW77"
)
OAUTH_SCOPE = "openid profile email offline_access"
DEVICE_AUTH_ENDPOINT = SIGNIN_BASE + "/oauth2/device_authorization"
TOKEN_ENDPOINT = SIGNIN_BASE + "/oauth2/token"
_REFRESH_SKEW = 60.0  # mint a new access token this many seconds before expiry

# In-process access-token cache — per SPAWNED child, i.e. per ACTIVE account (the
# hub kills+respawns the child on account switch, so it never leaks across
# accounts). Never persisted; the refresh token is the only durable secret.
_token_cache: dict = {}  # {access_token, expires_at, source}
# A device authorization awaiting the user's browser approval (this session only).
_pending_device: dict = {}  # {device_code, interval, expires_at}


# --------------------------------------------------------------------------- #
# Auth + the single network seam (tests monkeypatch ``_api``)
# --------------------------------------------------------------------------- #
def _broker_mode() -> bool:
    """True when a LOCAL token-broker fronts the API (loopback ``BIOMNI_API_BASE``).

    In broker mode the connector holds NO real token: a local reverse proxy
    (``biomni-mcp/broker.py``) injects the real ``Authorization`` header, reading it
    from a secure store (1Password / OS keyring / chmod-600 file). Enabled by
    ``BIOMNI_BROKER`` being truthy, or by an ``API_BASE`` whose host is loopback.
    """
    if os.environ.get("BIOMNI_BROKER", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return True
    host = urllib.parse.urlsplit(API_BASE).hostname or ""
    return host in ("127.0.0.1", "localhost", "::1")


def _token() -> tuple[str, str]:
    """Resolve a Bearer access token; return (token, error_message).

    Priority: (0) BROKER MODE -- if a local token-broker fronts the API
    (``BIOMNI_BROKER`` / loopback ``BIOMNI_API_BASE``), return a sentinel and let the
    broker inject the real Bearer, so the connector never holds it; (1)
    ``BIOMNI_TOKEN`` -- a static session Bearer token; (2) a refresh token, from
    ``BIOMNI_REFRESH_TOKEN`` (env, per-account) or the device-login state file,
    auto-minted into a short-lived access token cached in-process and refreshed
    ~60s before expiry. A rotated refresh token is persisted back to the state
    file. Never returns/logs the refresh token itself.
    """
    if _broker_mode():
        return "broker", ""
    static = os.environ.get("BIOMNI_TOKEN", "").strip()
    if static:
        return static, ""
    env_refresh = os.environ.get("BIOMNI_REFRESH_TOKEN", "").strip()
    state = {} if env_refresh else _load_state()
    refresh_token = env_refresh or (state.get("refresh_token") or "").strip()
    source = "env" if env_refresh else "state"
    if not refresh_token:
        return "", (
            "No Biomni credentials. Set BIOMNI_TOKEN (a session Bearer token) or "
            "BIOMNI_REFRESH_TOKEN, or run bm_auth_login to sign in via the OAuth "
            "device-code flow (you approve in a browser). The cloud-hub injects the "
            "active `biomni` account's creds; add accounts with bm_account_add."
        )
    cached = _token_cache.get("access_token")
    if cached and _token_cache.get("expires_at", 0.0) - _REFRESH_SKEW > time.time():
        return cached, ""
    data, err = _refresh_access_token(refresh_token)
    if err:
        return "", (
            err + " -- the refresh token may be revoked/expired; run bm_auth_login "
            "to re-authorize (or update BIOMNI_REFRESH_TOKEN)."
        )
    access = str(data["access_token"])
    _token_cache["access_token"] = access
    _token_cache["expires_at"] = time.time() + float(data.get("expires_in") or 3600)
    _token_cache["source"] = source
    new_refresh = data.get("refresh_token")
    if (
        source == "state"
        and isinstance(new_refresh, str)
        and new_refresh
        and new_refresh != refresh_token
    ):
        state["refresh_token"] = new_refresh
        _save_state(state)
    return access, ""


def _api(
    method: str,
    path: str,
    body=None,
    query: dict | None = None,
    token: str = "",
    timeout: float = TIMEOUT,
) -> tuple[int, object]:
    """Issue one Bearer-authenticated request to api.phylo.bio; return (status, parsed).

    ``path`` is an absolute API path (``/v2/...`` or ``/billing/...``). Network
    failures return ``(0, {"error": ...})`` so callers branch on status rather than
    catching. This is the ONE network seam -- unit tests monkeypatch it.
    """
    url = API_BASE + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    data = None
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return resp.status, _parse(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        return exc.code, _parse(exc.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return 0, {"error": f"{method.upper()} {path} failed: {exc}"}


def _parse(text: str) -> object:
    """Best-effort JSON parse; fall back to raw text for non-JSON bodies."""
    stripped = text.strip()
    if not stripped:
        return {}
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return text


# --------------------------------------------------------------------------- #
# OAuth device-code + refresh helpers (RFC 8628) -- the second network seam
# --------------------------------------------------------------------------- #
def _state_path() -> str:
    """Path to the local device-login token store (outside the repo; chmod 600)."""
    return os.environ.get("BIOMNI_TOKEN_STATE") or os.path.join(
        os.path.expanduser("~"), ".biomni-mcp", "token.json"
    )


def _load_state() -> dict:
    """Read the local token state ({refresh_token: ...}); {} if missing/unreadable."""
    try:
        with open(_state_path(), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(state: dict) -> None:
    """Atomically write the token state with restrictive (0600) permissions."""
    path = _state_path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh)
    os.replace(tmp, path)
    try:  # best-effort lockdown (Windows honours only the read-only bit)
        os.chmod(path, 0o600)
    except OSError:
        pass


def _mask(secret) -> str | None:
    """Non-reversible preview of a secret (never the full value) for status output."""
    if not secret or not isinstance(secret, str):
        return None
    return f"...{secret[-4:]}" if len(secret) > 8 else "set"


def _oauth_post(endpoint: str, form: dict) -> tuple[int, object]:
    """POST an ``x-www-form-urlencoded`` body to an OAuth endpoint; (status, parsed).

    Separate from ``_api`` (Bearer+JSON to api.phylo.bio): this is the
    UNauthenticated token/device endpoint seam at the WorkOS issuer. A public
    client, so no client secret is sent. Tests monkeypatch this.
    """
    data = urllib.parse.urlencode(form).encode("utf-8")
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }
    req = urllib.request.Request(endpoint, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:  # noqa: S310
            return resp.status, _parse(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        return exc.code, _parse(exc.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return 0, {"error": f"OAuth POST {endpoint} failed: {exc}"}


def _refresh_access_token(refresh_token: str) -> tuple[dict, str]:
    """Exchange a refresh token for a fresh access token; return (data, error)."""
    status, parsed = _oauth_post(
        TOKEN_ENDPOINT,
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": OAUTH_CLIENT_ID,
        },
    )
    if status == 200 and isinstance(parsed, dict) and parsed.get("access_token"):
        return parsed, ""
    detail = ""
    if isinstance(parsed, dict):
        detail = str(parsed.get("error_description") or parsed.get("error") or parsed)
    return {}, f"token refresh failed (HTTP {status}): {detail}".rstrip(": ")


# --------------------------------------------------------------------------- #
# Uniform result wrappers (mirror the databricks/modal backends' {ok,data} shape)
# --------------------------------------------------------------------------- #
def _fail(error: str, **extra) -> str:
    return json.dumps({"ok": False, "error": error, **extra}, ensure_ascii=False)


def _cap(payload: str) -> str:
    """Truncate an over-long serialized result so it can't flood the stream."""
    if len(payload) <= _MAX_CHARS:
        return payload
    return payload[:_MAX_CHARS] + (
        f"\n...[truncated at {_MAX_CHARS} chars; narrow the query or fetch details "
        f"on the web at {WEB_BASE}]"
    )


def _call(
    method: str,
    path: str,
    body=None,
    query: dict | None = None,
    timeout: float = TIMEOUT,
) -> str:
    """Token-check -> request -> uniform {ok,status,data|error} JSON string."""
    tok, err = _token()
    if err:
        return _fail(err)
    status, parsed = _api(method, path, body, query, tok, timeout)
    if 200 <= status < 300:
        return _cap(
            json.dumps(
                {"ok": True, "status": status, "data": parsed},
                ensure_ascii=False,
                default=str,
            )
        )
    if status == 401:
        return _fail(
            "Biomni auth rejected (401): the BIOMNI_TOKEN is expired or invalid. "
            "Refresh it from a signed-in session at " + WEB_BASE + ".",
            status=status,
            response=parsed,
        )
    return _fail(f"Biomni API returned HTTP {status}", status=status, response=parsed)


# --------------------------------------------------------------------------- #
# Session lifecycle -- the core agent loop
# --------------------------------------------------------------------------- #
@mcp.tool()
def bm_create_session(
    project_id: str,
    content: str,
    model_profile: str = "standard",
    submit_initial_message: bool = True,
    session_mode: str = "agent",
) -> str:
    """Create a Biomni agent session (a task) and optionally kick off its first run.

    ``POST /v2/agent/sessions/create``. ``model_profile`` is the EFFORT tier --
    standard | fast | premium (``max`` is accepted as an alias for premium). $$$
    with ``submit_initial_message=True`` (default) the ``content`` is submitted and
    the agent starts running immediately (consumes usage); set it False to create an
    empty session then compose ``bm_send_message`` + ``bm_start_processing`` (needed
    to attach skills / ``@``-resources to the first message). ``project_id`` comes
    from ``bm_list_projects`` (or ``bm_create_project``). Returns the ``session_id``
    (``sess_...``) used by every other session tool.
    """
    profile = _PROFILE_ALIASES.get(model_profile.lower().strip(), model_profile)
    body = {
        "project_id": project_id,
        "session_mode": session_mode,
        "content": content,
        "submit_initial_message": submit_initial_message,
        "model_profile": profile,
    }
    return _call("POST", "/v2/agent/sessions/create", body)


@mcp.tool()
def bm_send_message(
    session_id: str,
    content: str,
    attached_skills_json: str = "",
    is_clarification_response: bool = False,
) -> str:
    """Send a user message to a session (does NOT start the run -- call bm_start_processing).

    ``POST /v2/agent/{session_id}/user_message``. Two attachment mechanisms:
    * RESOURCES (tools / databases / packages) -> ``@name`` mentions INSIDE
      ``content`` (e.g. ``"@Addgene @airr analyse ..."``). This is how the app
      attaches ``@@``-resources; there is no separate field.
    * SKILLS -> ``attached_skills_json``, a JSON array of skill objects from
      ``bm_list_skills``, each ``{"id","name","category","intent":"use"}``. Only
      ACTIVE skills apply (toggle with ``bm_set_skill_status``).
    Set ``is_clarification_response=True`` when answering the agent's own follow-up
    question. Follow with ``bm_start_processing`` to run the agent on this message.
    """
    body: dict = {
        "content": content,
        "is_clarification_response": is_clarification_response,
    }
    if attached_skills_json.strip():
        try:
            skills = json.loads(attached_skills_json)
        except json.JSONDecodeError as exc:
            return _fail(f"attached_skills_json is not valid JSON: {exc}")
        if not isinstance(skills, list):
            return _fail("attached_skills_json must be a JSON array of skill objects")
        body["attached_skills"] = skills
    return _call("POST", f"/v2/agent/{session_id}/user_message", body)


@mcp.tool()
def bm_start_processing(session_id: str, message_id: str = "") -> str:
    """Start the agent processing a session message. $$$ consumes usage.

    ``POST /v2/agent/{session_id}/start_processing?message_id=…`` -- the API REQUIRES
    the ``message_id`` (the value ``bm_send_message`` returned) as a query param, so
    pass it. Use after ``bm_send_message``;
    ``bm_create_session(submit_initial_message=True)`` already starts the first run.
    """
    query = {"message_id": message_id} if message_id.strip() else None
    return _call("POST", f"/v2/agent/{session_id}/start_processing", {}, query)


@mcp.tool()
def bm_cancel(session_id: str) -> str:
    """Cancel/stop a running session (``POST /v2/agent/{session_id}/cancel``)."""
    return _call("POST", f"/v2/agent/{session_id}/cancel", {})


@mcp.tool()
def bm_get_session(session_id: str) -> str:
    """Get a session's full state -- status, model_profile, notebook path, iterations.

    ``GET /v2/agent/{session_id}``.
    """
    return _call("GET", f"/v2/agent/{session_id}")


@mcp.tool()
def bm_get_messages(session_id: str) -> str:
    (
        """Get the message/reasoning trace of a session (``GET /v2/agent/{session_id}/messages``).

    The reliable poll for a running or finished task -- the agent's turns, tool
    calls, and outputs. (Detailed reasoning + file previews are richer on the web
    UI at """
        + WEB_BASE
        + """.)
    """
    )
    return _call("GET", f"/v2/agent/{session_id}/messages")


@mcp.tool()
def bm_get_streaming(session_id: str, timeout_seconds: float = STREAM_TIMEOUT) -> str:
    """Best-effort LIVE stream snapshot of a running session.

    ``GET /v2/agent/{session_id}/streaming``. This may be a long-lived stream, so the
    read is bounded by ``timeout_seconds`` (default 12s); on timeout it returns an
    error hint -- use ``bm_get_messages`` for reliable polling. Useful to peek at an
    actively-processing session without waiting for it to finish.
    """
    return _call("GET", f"/v2/agent/{session_id}/streaming", timeout=timeout_seconds)


# --------------------------------------------------------------------------- #
# Effort tiers + skills (the controls the official connector hides)
# --------------------------------------------------------------------------- #
@mcp.tool()
def bm_list_model_profiles() -> str:
    """List the effort tiers and which is default (``GET /v2/agent/model-profiles``).

    Returns the profiles the account can use -- standard (default) | fast |
    premium ("Max", multimodal) -- the values ``bm_create_session(model_profile=...)``
    accepts.
    """
    return _call("GET", "/v2/agent/model-profiles")


@mcp.tool()
def bm_list_skills() -> str:
    """List the account's Biomni skills catalog (``GET /v2/know-how/all-skills``).

    Each skill has an ``id``, ``name``, ``category``, and active/inactive status.
    Copy the ones you want into ``bm_send_message(attached_skills_json=...)``; toggle
    availability with ``bm_set_skill_status``.
    """
    return _call("GET", "/v2/know-how/all-skills")


@mcp.tool()
def bm_set_skill_status(skill_id: str, status: str) -> str:
    """Activate or deactivate a skill (``PATCH /v2/know-how/skills/{skill_id}/status``).

    ``status`` is ``active`` or ``inactive``. Only active skills are eligible to be
    attached to a message.
    """
    status = status.lower().strip()
    if status not in ("active", "inactive"):
        return _fail("status must be 'active' or 'inactive'")
    return _call("PATCH", f"/v2/know-how/skills/{skill_id}/status", {"status": status})


# --------------------------------------------------------------------------- #
# Projects + sessions
# --------------------------------------------------------------------------- #
@mcp.tool()
def bm_list_projects() -> str:
    """List the account's projects (``GET /v2/projects``). Each has a ``proj_...`` id."""
    return _call("GET", "/v2/projects")


@mcp.tool()
def bm_create_project(name: str, description: str = "") -> str:
    """Create a project (``POST /v2/projects``); returns its ``proj_...`` id.

    Sessions are created inside a project (``bm_create_session(project_id=...)``).
    """
    return _call("POST", "/v2/projects", {"name": name, "description": description})


@mcp.tool()
def bm_list_sessions(project_id: str) -> str:
    """List a project's sessions/tasks (``GET /v2/agent/projects/{project_id}/sessions``)."""
    return _call("GET", f"/v2/agent/projects/{project_id}/sessions")


# --------------------------------------------------------------------------- #
# Live runtime introspection ("see it live")
# --------------------------------------------------------------------------- #
@mcp.tool()
def bm_session_runtime(session_id: str, kind: str = "background-processes") -> str:
    """Introspect a session's live compute (``GET /v2/agent/{session_id}/{kind}``).

    ``kind`` is one of: background-processes | gpu-sandboxes | hpc-jobs |
    hpc-pipelines | machines. Shows what the agent is actually running on the
    backend -- long-running processes, GPU sandboxes, HPC jobs/pipelines, and the
    machines allocated to the session.
    """
    kind = kind.strip()
    if kind not in _RUNTIME_KINDS:
        return _fail(f"kind must be one of {list(_RUNTIME_KINDS)}")
    return _call("GET", f"/v2/agent/{session_id}/{kind}")


# --------------------------------------------------------------------------- #
# Files / results
# --------------------------------------------------------------------------- #
@mcp.tool()
def bm_list_results() -> str:
    (
        """List result files across the account (``GET /v2/files/results``).

    Names + sizes only; download the actual files from the web app at
    """
        + WEB_BASE
        + """ (the sandbox paths are not directly fetchable).
    """
    )
    return _call("GET", "/v2/files/results")


@mcp.tool()
def bm_files_tree() -> str:
    """List the account's file tree (``GET /v2/files/tree``)."""
    return _call("GET", "/v2/files/tree")


# --------------------------------------------------------------------------- #
# Usage / billing (rotate accounts BEFORE one runs dry) + identity
# --------------------------------------------------------------------------- #
@mcp.tool()
def bm_billing_balance() -> str:
    """Show the account's remaining usage/credit balance (``GET /billing/balance``).

    Poll this to decide when to ``bm_account_cycle`` to a fresh Biomni account
    before the active one is exhausted.
    """
    return _call("GET", "/billing/balance")


@mcp.tool()
def bm_billing_subscription() -> str:
    """Show the account's subscription/plan (``GET /billing/subscription``)."""
    return _call("GET", "/billing/subscription")


def _scrub_secrets(node) -> None:
    """Recursively replace secret-bearing values in a parsed JSON tree, in place.

    Redacts ``external_api_keys`` (the user's stored third-party keys) and any field
    whose name looks like a secret, so a user's own credentials never enter an
    agent's context. Key NAMES are kept (so you still see WHICH keys are set); only
    the values are replaced with ``"[redacted]"``.
    """
    _secretish = ("api_key", "apikey", "secret", "token", "password", "credential")
    if isinstance(node, dict):
        for key, val in node.items():
            low = key.lower()
            if low == "external_api_keys" and isinstance(val, dict):
                node[key] = dict.fromkeys(val, "[redacted]")
            elif any(t in low for t in _secretish) and isinstance(val, str) and val:
                node[key] = "[redacted]"
            else:
                _scrub_secrets(val)
    elif isinstance(node, list):
        for item in node:
            _scrub_secrets(item)


def _redact_secrets(payload: str) -> str:
    """Redact secret-bearing fields from a JSON result string; pass through on error."""
    try:
        obj = json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        return payload
    _scrub_secrets(obj)
    return json.dumps(obj, ensure_ascii=False, default=str)


@mcp.tool()
def bm_whoami() -> str:
    """Show the authenticated Biomni identity (``GET /v2/auth/me``) -- secrets REDACTED.

    Confirms which account the active session maps to (pair with
    ``bm_account_current`` for the hub-side name). The response's stored
    ``external_api_keys`` and any token-like fields are REDACTED so a user's own
    third-party credentials never enter an agent's context.
    """
    return _redact_secrets(_call("GET", "/v2/auth/me"))


@mcp.tool()
def bm_capabilities() -> str:
    """List the account's platform capabilities/feature flags (``GET /v2/capabilities``)."""
    return _call("GET", "/v2/capabilities")


# --------------------------------------------------------------------------- #
# OAuth device-code login + auto-refresh (you approve in a browser)
# --------------------------------------------------------------------------- #
@mcp.tool()
def bm_auth_login() -> str:
    """Start OAuth device-code login -- returns a code + URL for YOU to approve.

    ``POST {signin}/oauth2/device_authorization``. Open the returned
    ``verification_uri_complete`` in a browser and approve (you sign in there --
    this tool never sees your password). Then call ``bm_auth_poll`` to finish. On
    success the refresh token is stored locally (chmod 600, never echoed) and the
    connector auto-mints access tokens from it, so BIOMNI_TOKEN no longer expires
    on you. For multi-account rotation, promote it to a per-account
    BIOMNI_REFRESH_TOKEN instead (see bm_auth_status).
    """
    status, parsed = _oauth_post(
        DEVICE_AUTH_ENDPOINT, {"client_id": OAUTH_CLIENT_ID, "scope": OAUTH_SCOPE}
    )
    if status != 200 or not isinstance(parsed, dict) or not parsed.get("device_code"):
        return _fail(f"device authorization failed (HTTP {status})", response=parsed)
    _pending_device.clear()
    _pending_device.update(
        device_code=str(parsed["device_code"]),
        interval=float(parsed.get("interval") or 5),
        expires_at=time.time() + float(parsed.get("expires_in") or 600),
    )
    return json.dumps(
        {
            "ok": True,
            "action_required": "Open the URL, approve, then call bm_auth_poll.",
            "user_code": parsed.get("user_code"),
            "verification_uri": parsed.get("verification_uri"),
            "verification_uri_complete": parsed.get("verification_uri_complete")
            or parsed.get("verification_uri"),
            "expires_in": parsed.get("expires_in"),
        },
        ensure_ascii=False,
    )


@mcp.tool()
def bm_auth_poll(max_wait_seconds: float = 25.0) -> str:
    """Finish device-code login: poll for approval, then save the refresh token.

    ``POST {signin}/oauth2/token`` (grant_type=device_code). Call after
    ``bm_auth_login`` once you've approved in the browser. Polls up to
    ``max_wait_seconds`` (respecting the server ``interval``); returns
    ``authorization_pending`` if you haven't approved yet -- just call it again. On
    success the tokens are written to the local state file (chmod 600) and only the
    identity/expiry are returned -- NEVER the token values.
    """
    if not _pending_device.get("device_code"):
        return _fail("no pending login; call bm_auth_login first")
    if time.time() > _pending_device.get("expires_at", 0.0):
        _pending_device.clear()
        return _fail("the device code expired; call bm_auth_login again")
    interval = max(1.0, float(_pending_device.get("interval", 5.0)))
    deadline = time.time() + max(0.0, max_wait_seconds)
    while True:
        status, parsed = _oauth_post(
            TOKEN_ENDPOINT,
            {
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": _pending_device["device_code"],
                "client_id": OAUTH_CLIENT_ID,
            },
        )
        if status == 200 and isinstance(parsed, dict) and parsed.get("access_token"):
            state = _load_state()
            if parsed.get("refresh_token"):
                state["refresh_token"] = str(parsed["refresh_token"])
            _save_state(state)
            _pending_device.clear()
            _token_cache.clear()  # force a fresh mint on the next API call
            return json.dumps(
                {
                    "ok": True,
                    "authenticated": True,
                    "saved_to": _state_path(),
                    "has_refresh_token": bool(parsed.get("refresh_token")),
                    "access_token_expires_in": parsed.get("expires_in"),
                    "note": "Refresh token stored locally; the connector auto-mints "
                    "access tokens from it. For account rotation, set it as a "
                    "per-account BIOMNI_REFRESH_TOKEN.",
                },
                ensure_ascii=False,
            )
        err = parsed.get("error") if isinstance(parsed, dict) else None
        if err in ("authorization_pending", "slow_down"):
            if err == "slow_down":
                interval += 5
            if time.time() >= deadline:
                return json.dumps(
                    {
                        "ok": False,
                        "pending": True,
                        "error": err,
                        "hint": "approve at the bm_auth_login URL, then call "
                        "bm_auth_poll again",
                    },
                    ensure_ascii=False,
                )
            time.sleep(interval)
            continue
        return _fail(f"device token exchange failed (HTTP {status})", response=parsed)


@mcp.tool()
def bm_auth_status() -> str:
    """Report the current auth source + access-token freshness (tokens masked).

    Shows whether creds come from BIOMNI_TOKEN (static), BIOMNI_REFRESH_TOKEN
    (env, rotates with the account), or the device-login state file -- plus the
    cached access token's remaining lifetime. Never reveals token values.
    """
    static = bool(os.environ.get("BIOMNI_TOKEN", "").strip())
    env_refresh = bool(os.environ.get("BIOMNI_REFRESH_TOKEN", "").strip())
    has_state_refresh = bool((_load_state().get("refresh_token") or "").strip())
    if static:
        source = "BIOMNI_TOKEN (static)"
    elif env_refresh:
        source = "BIOMNI_REFRESH_TOKEN (env)"
    elif has_state_refresh:
        source = "device-login state file"
    else:
        source = "none"
    remaining = None
    if _token_cache.get("expires_at"):
        remaining = round(float(_token_cache["expires_at"]) - time.time(), 1)
    return json.dumps(
        {
            "ok": True,
            "authenticated": source != "none",
            "auth_source": source,
            "cached_access_token": _mask(_token_cache.get("access_token")),
            "access_token_expires_in_seconds": remaining,
            "state_file": _state_path(),
            "client_id": OAUTH_CLIENT_ID,
        },
        ensure_ascii=False,
    )


@mcp.tool()
def bm_auth_logout() -> str:
    """Clear the locally-stored device-login refresh token + in-process token cache.

    Deletes the state file (does NOT touch the BIOMNI_TOKEN / BIOMNI_REFRESH_TOKEN
    env vars -- those are user-owned). Re-run bm_auth_login to sign in again.
    """
    path = _state_path()
    removed = False
    try:
        os.remove(path)
        removed = True
    except OSError:
        pass
    _token_cache.clear()
    _pending_device.clear()
    return json.dumps(
        {"ok": True, "cleared_state_file": removed, "path": path}, ensure_ascii=False
    )


# --------------------------------------------------------------------------- #
# Raw escape hatch to ANY endpoint
# --------------------------------------------------------------------------- #
@mcp.tool()
def bm_api_raw(
    method: str, path: str, body_json: str = "", query_json: str = ""
) -> str:
    """Call ANY api.phylo.bio endpoint -- the escape hatch for uncovered routes.

    ``method`` GET|POST|PUT|PATCH|DELETE; ``path`` is an absolute API path starting
    with ``/`` (e.g. ``/v2/users/me/memory``, ``/v2/mcp/servers``,
    ``/v2/cloud-storage/connections``). ``body_json``/``query_json`` are optional JSON
    strings. Caution: this can reach mutating/destructive routes (a ``DELETE`` on a
    project) on the user's OWN account -- confirm intent before calling those.
    """
    if not path.startswith("/"):
        return _fail("path must be an absolute API path starting with '/'")
    try:
        body = json.loads(body_json) if body_json.strip() else None
        query = json.loads(query_json) if query_json.strip() else None
    except json.JSONDecodeError as exc:
        return _fail(f"body_json/query_json must be valid JSON: {exc}")
    if query is not None and not isinstance(query, dict):
        return _fail("query_json must be a JSON object of string->value")
    return _call(method, path, body, query)


if __name__ == "__main__":
    mcp.run()
