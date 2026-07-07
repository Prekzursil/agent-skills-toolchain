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


# --------------------------------------------------------------------------- #
# Auth + the single network seam (tests monkeypatch ``_api``)
# --------------------------------------------------------------------------- #
def _token() -> tuple[str, str]:
    """Read the Bearer token from the env; return (token, error_message)."""
    tok = os.environ.get("BIOMNI_TOKEN", "").strip()
    if not tok:
        return "", (
            "BIOMNI_TOKEN not set. Sign in at " + WEB_BASE + " and provide the "
            "session Bearer token as BIOMNI_TOKEN (the cloud-hub injects the active "
            "`biomni` account's token; add accounts with bm_account_add). There is "
            "no API-key product yet, so refresh the token when it expires."
        )
    return tok, ""


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
def bm_start_processing(session_id: str) -> str:
    """Start the agent processing the session's latest message. $$$ consumes usage.

    ``POST /v2/agent/{session_id}/start_processing``. Use after ``bm_send_message``;
    ``bm_create_session(submit_initial_message=True)`` already starts the first run.
    """
    return _call("POST", f"/v2/agent/{session_id}/start_processing", {})


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


@mcp.tool()
def bm_whoami() -> str:
    """Show the authenticated Biomni identity (``GET /v2/auth/me``).

    Confirms which account the active BIOMNI_TOKEN maps to (pair with
    ``bm_account_current`` to see which named account is active in the hub).
    """
    return _call("GET", "/v2/auth/me")


@mcp.tool()
def bm_capabilities() -> str:
    """List the account's platform capabilities/feature flags (``GET /v2/capabilities``)."""
    return _call("GET", "/v2/capabilities")


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
