"""biomni-hub :: Online (claude.ai Biomni Lab) backend adapter -- Track A.

Routes the hub's 10 canonical tools to the FREE, hosted **Biomni Lab**
(https://biomni.phylo.bio, by Phylo Inc.) over its ``api.phylo.bio/v2`` REST
surface. This is a faithful, dependency-free PORT of the same REST client
cloud-hub ships as its ``bm_*`` tools: identical endpoints, identical
Bearer/broker auth.

Canonical interface (reconciled -- see hub/backends.py::BiomniBackend)
---------------------------------------------------------------------
This adapter now SUBCLASSES :class:`backends.BiomniBackend` and every one of the
ten canonical tools returns a :class:`schema.ToolEnvelope` (not a raw dict), so
the hub's positional dispatch and the online<->databricks golden contract hold.
Lifecycle fields (``task_id``/``project_id``/``message_id``/``status``/
``model_profile``/``cursor``/``done``/``new_log``/``new_messages``) live in the
envelope ``data``; ``biomni_url`` and ``display_instruction`` sit at envelope
level. Handled errors return ``ToolEnvelope.failure(...)`` -- methods never raise
for expected failures (bad ids, auth expiry, empty results).

Extra (non-canonical) affordances kept for the A3 bridge:
  * ``status()``        -- rich, networked availability probe (legacy shape)
  * ``describe()``      -- non-networking readiness row for ``biomni_backends``
  * ``fetch_artifact()``-- online sandbox paths are not API-fetchable -> returns
                           a web-download hint (the databricks backend returns
                           real bytes); consumed by ``features.bridge``.

Auth (identical to the reference client): BROKER (``BIOMNI_BROKER=1`` or a
loopback ``BIOMNI_API_BASE``; a local proxy injects the credential and this
module sends a ``Bearer broker`` sentinel), STATIC (``BIOMNI_TOKEN``), or REFRESH
(``BIOMNI_REFRESH_TOKEN`` -> short-lived access tokens via the WorkOS issuer).
``base_url`` is configurable via ``BIOMNI_API_BASE`` or the ``api_base`` ctor arg.
"""

from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from backends import BiomniBackend
from schema import BackendDescriptor, ResultFile, ToolEnvelope

# --------------------------------------------------------------------------
# Configuration (env-overridable; mirrors biomni-mcp/server.py)
# --------------------------------------------------------------------------
DEFAULT_API_BASE = os.environ.get("BIOMNI_API_BASE", "https://api.phylo.bio")
DEFAULT_WEB_BASE = os.environ.get("BIOMNI_WEB_BASE", "https://biomni.phylo.bio")
# Web deep-link template for a task; provisional -- override if the app path
# differs. ``{session_id}`` is substituted with the phylo session id.
WEB_SESSION_PATH = os.environ.get(
    "BIOMNI_WEB_SESSION_PATH", "/session/{session_id}"
)

TIMEOUT = 45.0
_MAX_CHARS = 200_000

# WorkOS device-code refresh (only used when BIOMNI_REFRESH_TOKEN is set).
SIGNIN_BASE = os.environ.get(
    "BIOMNI_SIGNIN_BASE", "https://signin.phylo.bio"
).rstrip("/")
OAUTH_CLIENT_ID = os.environ.get(
    "BIOMNI_CLIENT_ID", "client_01KEFGHEBJP3XMFBQ0TR34DW77"
)
TOKEN_ENDPOINT = SIGNIN_BASE + "/oauth2/token"
_REFRESH_SKEW = 60.0

_PROFILE_ALIASES = {
    "max": "premium",
    "standard": "standard",
    "fast": "fast",
    "premium": "premium",
}
_TERMINAL_STATES = {
    "completed", "complete", "done", "finished", "succeeded", "success",
    "failed", "error", "errored", "cancelled", "canceled", "stopped",
    "terminated",
}

# States the display_instruction should nudge the caller to keep polling on.
_DISPLAY_RUNNING = (
    "Biomni runs this task asynchronously (typically 30s-10min+). Open "
    "biomni_url to watch it live, or keep calling wait_for_next_update(task_id) "
    "until status is terminal."
)


def _ok(**kw: Any) -> dict[str, Any]:
    d: dict[str, Any] = {"ok": True}
    d.update(kw)
    return d


def _err(msg: str, **kw: Any) -> dict[str, Any]:
    d: dict[str, Any] = {"ok": False, "error": msg, "backend": "online"}
    d.update(kw)
    return d


# --------------------------------------------------------------------------
# The single network seam (unit tests monkeypatch ``_request``)
# --------------------------------------------------------------------------
def _parse(text: str) -> object:
    stripped = text.strip()
    if not stripped:
        return {}
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return text


def _extract(data: object, *keys: str, default: Any = None) -> Any:
    """First present key from a dict, tolerating snake/camel id aliases."""
    if isinstance(data, dict):
        for k in keys:
            if k in data and data[k] not in (None, ""):
                return data[k]
        # phylo sometimes nests the payload one level down.
        for wrap in ("data", "session", "project", "result"):
            inner = data.get(wrap)
            if isinstance(inner, dict):
                for k in keys:
                    if inner.get(k) not in (None, ""):
                        return inner[k]
    return default


def _coerce_size(value: Any) -> int:
    """Coerce an API size field to a non-negative int (ResultFile requires it)."""
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return max(0, int(value))
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return 0


@dataclass
class OnlineBiomniAdapter(BiomniBackend):
    """Backend adapter for the hosted, free Biomni Lab (phylo api.phylo.bio/v2).

    Implements the hub's canonical :class:`backends.BiomniBackend` contract (the
    10 tools returning :class:`schema.ToolEnvelope`, plus ``describe`` and the
    bridge helpers ``fetch_artifact``/``status``). Instantiated by the hub only
    when the selector resolves to ``online``. One instance per (api_base,
    account).
    """

    name: str = "online"
    api_base: str = DEFAULT_API_BASE
    web_base: str = DEFAULT_WEB_BASE
    token: str = ""  # explicit override; else resolved from env each call
    timeout: float = TIMEOUT
    _current_project: str | None = field(default=None, repr=False)
    _current_workspace: str | None = field(default=None, repr=False)
    _token_cache: dict[str, Any] = field(default_factory=dict, repr=False)

    # ---- envelope helpers ------------------------------------------------
    def _env_ok(
        self,
        tool: str,
        data: Any = None,
        *,
        biomni_url: str | None = None,
        display_instruction: str | None = None,
    ) -> ToolEnvelope:
        return ToolEnvelope.success(
            self.name, tool, data=data,
            biomni_url=biomni_url, display_instruction=display_instruction,
        )

    def _env_err(self, tool: str, error: str) -> ToolEnvelope:
        return ToolEnvelope.failure(self.name, tool, error)

    def _base(self) -> str:
        return self.api_base.rstrip("/")

    # ---- auth (ported faithfully from biomni-mcp/server.py) --------------
    def _broker_mode(self) -> bool:
        flag = os.environ.get("BIOMNI_BROKER", "").strip().lower()
        if flag in ("1", "true", "yes", "on"):
            return True
        host = urllib.parse.urlsplit(self._base()).hostname or ""
        return host in ("127.0.0.1", "localhost", "::1")

    def _resolve_token(self) -> tuple[str, str]:
        """Return (bearer, error). Priority: broker > explicit > env > refresh."""
        if self._broker_mode():
            return "broker", ""
        if self.token.strip():
            return self.token.strip(), ""
        static = os.environ.get("BIOMNI_TOKEN", "").strip()
        if static:
            return static, ""
        refresh = os.environ.get("BIOMNI_REFRESH_TOKEN", "").strip()
        if not refresh:
            return "", (
                "No Biomni credentials. Set BIOMNI_TOKEN or "
                "BIOMNI_REFRESH_TOKEN, or run in broker mode (BIOMNI_BROKER=1 "
                "with a loopback BIOMNI_API_BASE). The cloud-hub injects the "
                "active `biomni` account's creds when it spawns this backend."
            )
        cached = self._token_cache.get("access_token")
        expires = self._token_cache.get("expires_at", 0.0)
        if cached and expires - _REFRESH_SKEW > time.time():
            return cached, ""
        data, err = self._refresh_access_token(refresh)
        if err:
            return "", err + " -- the refresh token may be revoked/expired."
        access = str(data["access_token"])
        self._token_cache["access_token"] = access
        self._token_cache["expires_at"] = time.time() + float(
            data.get("expires_in") or 3600
        )
        return access, ""

    def _refresh_access_token(self, refresh_token: str) -> tuple[dict, str]:
        form = urllib.parse.urlencode(
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": OAUTH_CLIENT_ID,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            TOKEN_ENDPOINT, data=form, method="POST",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
                status = resp.status
                parsed = _parse(resp.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as exc:
            status = exc.code
            parsed = _parse(exc.read().decode("utf-8", "replace"))
        except (urllib.error.URLError, OSError, ValueError) as exc:
            return {}, f"token refresh failed: {exc}"
        if status == 200 and isinstance(parsed, dict) and parsed.get("access_token"):
            return parsed, ""
        detail = parsed.get("error_description") if isinstance(parsed, dict) else parsed
        return {}, f"token refresh failed (HTTP {status}): {detail}"

    # ---- HTTP (the ONE network seam) -------------------------------------
    def _request(
        self, method: str, path: str, body: Any = None,
        query: dict | None = None, token: str = "",
        timeout: float | None = None,
    ) -> tuple[int, object]:
        """Issue one Bearer-authenticated request; return (status, parsed).

        Network failures return ``(0, {"error": ...})`` so callers branch on
        status rather than catching. Tests monkeypatch this method.
        """
        url = self._base() + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        data = None
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(
            url, data=data, headers=headers, method=method.upper()
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:  # noqa: S310
                return resp.status, _parse(resp.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as exc:
            return exc.code, _parse(exc.read().decode("utf-8", "replace"))
        except (urllib.error.URLError, OSError, ValueError) as exc:
            return 0, {"error": f"{method.upper()} {path} failed: {exc}"}

    def _call(
        self, method: str, path: str, body: Any = None,
        query: dict | None = None, timeout: float | None = None,
    ) -> dict[str, Any]:
        """Token-check -> request -> uniform {ok,status,data|error} dict."""
        tok, err = self._resolve_token()
        if err:
            return _err(err)
        status, parsed = self._request(method, path, body, query, tok, timeout)
        if 200 <= status < 300:
            return {"ok": True, "status": status, "data": parsed}
        if status == 401:
            return _err(
                "Biomni auth rejected (401): the credential is expired or "
                "invalid. Refresh it from a signed-in session at "
                + self.web_base + ".",
                status=status, response=parsed,
            )
        if status == 0:
            return _err(
                _extract(parsed, "error", default=f"network error to {self._base()}"),
                status=0, response=parsed,
            )
        return _err(
            f"Biomni API returned HTTP {status}", status=status, response=parsed
        )

    # ---- web deep link ---------------------------------------------------
    def _biomni_url(self, session_id: str) -> str:
        return self.web_base.rstrip("/") + WEB_SESSION_PATH.format(
            session_id=session_id
        )

    # ---- backend catalog -------------------------------------------------
    def describe(self) -> BackendDescriptor:
        """Non-networking readiness row for the ``biomni_backends`` catalog.

        Derives availability from credential resolution only (no ``/v2/auth/me``
        round-trip), so the catalog never hangs on a down broker. Use
        :meth:`status` for the richer, networked probe.
        """
        tok, err = self._resolve_token()
        available = not err
        mode = "broker" if self._broker_mode() else ("token" if tok else "none")
        detail = err or f"auth={mode} base={self._base()}"
        return BackendDescriptor(
            name=self.name,
            available=available,
            is_default=False,
            status="ready" if available else "unconfigured",
            cost="free hosted tier / per-account Biomni usage credits",
            detail=detail,
        )

    def status(self) -> dict[str, Any]:
        """Rich, networked availability probe (legacy dict shape). Never raises."""
        tok, err = self._resolve_token()
        base_info = {
            "backend": "online",
            "workspace": self._base(),
            "web": self.web_base,
            "execution_model": "hosted-async-agent (phylo Biomni Lab)",
            "auth_mode": (
                "broker" if self._broker_mode() else ("token" if tok else "none")
            ),
            "cost_hint": "free hosted tier / per-account Biomni usage credits "
                         "(rotate accounts via the hub's bm_account_* layer)",
        }
        if err:
            return _err(err, available=False, **base_info)
        me = self._call("GET", "/v2/auth/me")
        if me.get("ok"):
            data = me["data"]
            return _ok(
                available=True,
                identity=_extract(data, "email", "user_name", "username", "name"),
                **base_info,
            )
        return _err(
            me.get("error", "identity probe failed"),
            available=False, probe=me, **base_info,
        )

    # ---- internal control-plane workers (dict-returning) -----------------
    @staticmethod
    def _as_list(data: object, *keys: str) -> list[Any]:
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for k in (*keys, "items", "results", "data"):
                v = data.get(k)
                if isinstance(v, list):
                    return v
        return []

    def _do_create_project(self, name: str, description: str) -> dict[str, Any]:
        r = self._call(
            "POST", "/v2/projects", {"name": name, "description": description}
        )
        if not r.get("ok"):
            return r
        pid = _extract(r["data"], "id", "project_id", "proj_id")
        if pid:
            self._current_project = pid
        return _ok(project_id=pid, name=name, raw=r["data"])

    def _do_list_projects(self) -> dict[str, Any]:
        r = self._call("GET", "/v2/projects")
        if not r.get("ok"):
            return r
        projects = self._as_list(r["data"], "projects")
        return _ok(projects=projects, current_project=self._current_project)

    # ---- canonical control-plane: projects -------------------------------
    def create_project(self, name: str, description: str = "") -> ToolEnvelope:
        r = self._do_create_project(name, description)
        if not r.get("ok"):
            return self._env_err(
                "create_project", r.get("error", "create_project failed")
            )
        return self._env_ok(
            "create_project",
            data={"project_id": r.get("project_id"), "name": name, "raw": r.get("raw")},
        )

    def list_projects(self) -> ToolEnvelope:
        r = self._do_list_projects()
        if not r.get("ok"):
            return self._env_err(
                "list_projects", r.get("error", "list_projects failed")
            )
        return self._env_ok(
            "list_projects",
            data={
                "projects": r.get("projects", []),
                "current_project": r.get("current_project"),
            },
        )

    # ---- canonical control-plane: workspaces (provisional) ---------------
    def list_workspaces(self) -> ToolEnvelope:
        """List logical workspaces. Tries a workspaces route, else derives one
        from the authenticated identity/org (``/v2/auth/me``)."""
        probe = self._call("GET", "/v2/workspaces")
        if probe.get("ok"):
            ws = self._as_list(probe["data"], "workspaces")
            if ws:
                for w in ws:
                    if isinstance(w, dict):
                        w["current"] = (
                            _extract(w, "id", "workspace_id") == self._current_workspace
                        )
                return self._env_ok(
                    "list_workspaces",
                    data={"workspaces": ws, "provisional_route": "/v2/workspaces"},
                )
        me = self._call("GET", "/v2/auth/me")
        if not me.get("ok"):
            return self._env_err(
                "list_workspaces", me.get("error", "cannot resolve workspace")
            )
        data = me["data"]
        wid = _extract(
            data, "organization_id", "org_id", "workspace_id", "id", default="default"
        )
        wname = _extract(
            data, "organization_name", "org_name", "email", "user_name",
            default="biomni-lab",
        )
        if self._current_workspace is None:
            self._current_workspace = wid
        return self._env_ok(
            "list_workspaces",
            data={
                "workspaces": [
                    {
                        "id": wid, "name": wname,
                        "current": wid == self._current_workspace,
                    }
                ],
                "derived_from": "/v2/auth/me",
                "note": "Online Biomni Lab exposes no explicit workspace switch; "
                        "the account IS the workspace.",
            },
        )

    def switch_workspace(self, workspace_id: str) -> ToolEnvelope:
        """Rebind the active workspace (local record is authoritative)."""
        self._current_workspace = workspace_id
        self._call("POST", f"/v2/workspaces/{workspace_id}/activate")  # best-effort
        return self._env_ok(
            "switch_workspace", data={"workspace_id": workspace_id, "current": True}
        )

    # ---- canonical control-plane: file upload (provisional) --------------
    def upload_file(
        self, local_path: str, project_id: str = "", destination: str = ""
    ) -> ToolEnvelope:
        """Upload a file to the account's file space (provisional route)."""
        try:
            with open(local_path, "rb") as fh:
                raw = fh.read()
        except OSError as exc:
            return self._env_err("upload_file", f"cannot read {local_path}: {exc}")
        name = destination or os.path.basename(local_path)
        body: dict[str, Any] = {
            "name": name, "size": len(raw),
            "content_base64": base64.b64encode(raw).decode(),
        }
        if project_id or self._current_project:
            body["project_id"] = project_id or self._current_project
        r = self._call("POST", "/v2/files/upload", body)
        if r.get("ok"):
            return self._env_ok(
                "upload_file",
                data={
                    "name": name, "size": len(raw), "raw": r["data"],
                    "provisional_route": "/v2/files/upload",
                },
            )
        return self._env_err(
            "upload_file",
            "online upload_file could not complete (route provisional / broker "
            "down). Upload via the web app instead: " + self.web_base,
        )

    # ---- task-plane ------------------------------------------------------
    def _resolve_project(self, project_id: str | None) -> tuple[str | None, str | None]:
        """Pick a project id: explicit -> current -> first existing -> create."""
        if project_id:
            return project_id, None
        if self._current_project:
            return self._current_project, None
        lst = self._do_list_projects()
        if lst.get("ok") and lst["projects"]:
            pid = _extract(lst["projects"][0], "id", "project_id", "proj_id")
            if pid:
                self._current_project = pid
                return pid, None
        created = self._do_create_project(name="biomni-hub", description="")
        if created.get("ok") and created.get("project_id"):
            return created["project_id"], None
        return None, "could not resolve or create a project"

    def start_new_task(
        self, project_id: str, prompt: str, model_profile: str = "standard",
        *, attached_skills: list[dict] | None = None,
        resources: list[str] | None = None,
    ) -> ToolEnvelope:
        """Create a Biomni agent session (a task) and start its first run.

        ``attached_skills`` / ``resources`` are keyword-only extensions beyond the
        canonical surface (the hub dispatches only the three positional args).
        """
        pid, perr = self._resolve_project(project_id)
        if perr:
            return self._env_err("start_new_task", perr)
        profile = _PROFILE_ALIASES.get(model_profile.lower().strip(), model_profile)
        content = prompt
        if resources:
            mentions = " ".join(
                m if m.startswith("@") else f"@{m}" for m in resources
            )
            content = f"{mentions} {prompt}".strip()

        compose = bool(attached_skills)
        create = self._call(
            "POST", "/v2/agent/sessions/create",
            {
                "project_id": pid, "session_mode": "agent", "content": content,
                "submit_initial_message": not compose, "model_profile": profile,
            },
        )
        if not create.get("ok"):
            return self._env_err(
                "start_new_task", create.get("error", "start_new_task failed")
            )
        sid = _extract(create["data"], "session_id", "id", "sessionId")
        if not sid:
            return self._env_err("start_new_task", "no session_id in response")

        message_id = None
        if compose:
            msg = self._call(
                "POST", f"/v2/agent/{sid}/user_message",
                {
                    "content": content, "is_clarification_response": False,
                    "attached_skills": attached_skills,
                },
            )
            if not msg.get("ok"):
                return self._env_err(
                    "start_new_task", "task created but attaching skills failed"
                )
            message_id = _extract(msg["data"], "message_id", "id")
            q = {"message_id": message_id} if message_id else None
            run = self._call("POST", f"/v2/agent/{sid}/start_processing", {}, q)
            if not run.get("ok"):
                return self._env_err(
                    "start_new_task", "task created but start_processing failed"
                )

        biomni_url = _extract(create["data"], "url", "web_url") or self._biomni_url(sid)
        return self._env_ok(
            "start_new_task",
            data={
                "task_id": sid, "project_id": pid, "message_id": message_id,
                "status": "running", "model_profile": profile,
            },
            biomni_url=biomni_url,
            display_instruction=_DISPLAY_RUNNING,
        )

    def send_message(
        self, task_id: str, content: str, *,
        attached_skills: list[dict] | None = None,
        is_clarification_response: bool = False,
    ) -> ToolEnvelope:
        """Send a follow-up user message to a task and start processing it."""
        body: dict[str, Any] = {
            "content": content,
            "is_clarification_response": is_clarification_response,
        }
        if attached_skills:
            body["attached_skills"] = attached_skills
        msg = self._call("POST", f"/v2/agent/{task_id}/user_message", body)
        if not msg.get("ok"):
            return self._env_err(
                "send_message", msg.get("error", "send_message failed")
            )
        message_id = _extract(msg["data"], "message_id", "id")
        q = {"message_id": message_id} if message_id else None
        run = self._call("POST", f"/v2/agent/{task_id}/start_processing", {}, q)
        if not run.get("ok"):
            return self._env_err(
                "send_message", "message sent but start_processing failed"
            )
        return self._env_ok(
            "send_message",
            data={"task_id": task_id, "message_id": message_id, "status": "running"},
            biomni_url=self._biomni_url(task_id),
            display_instruction=_DISPLAY_RUNNING,
        )

    def _session_status(self, task_id: str) -> str | None:
        s = self._call("GET", f"/v2/agent/{task_id}")
        if s.get("ok"):
            st = _extract(s["data"], "status", "state")
            return str(st).lower() if st is not None else None
        return None

    def _messages(self, task_id: str) -> list[Any]:
        m = self._call("GET", f"/v2/agent/{task_id}/messages")
        if m.get("ok"):
            return self._as_list(m["data"], "messages")
        return []

    def wait_for_next_update(
        self, task_id: str, timeout_seconds: float = 60.0, *,
        since: int | None = None, poll_interval: float = 3.0,
    ) -> ToolEnvelope:
        """Block (bounded) until the task produces new messages or reaches a
        terminal state; return the incremental update + a ``cursor`` to resume.

        ``since`` is the RESUME cursor (message index already seen); it is
        keyword-only so the hub's positional dispatch order matches the ABC. It
        is preserved (not dropped) because it is the online adapter's incremental
        resume capability -- pass the ``cursor`` from the previous update back in.
        """
        cursor = int(since) if since is not None else 0
        deadline = time.time() + max(0.0, timeout_seconds)
        first = True
        while True:
            msgs = self._messages(task_id)
            status = self._session_status(task_id)
            done = status in _TERMINAL_STATES if status else False
            if len(msgs) > cursor or done or (time.time() >= deadline and not first):
                new = msgs[cursor:]
                data: dict[str, Any] = {
                    "task_id": task_id,
                    "status": status or "unknown",
                    "cursor": len(msgs),
                    "done": done,
                    "new_messages": new[: _MAX_CHARS // 512],
                    "new_log": [str(x)[:4000] for x in new],
                }
                if done:
                    rf = self._do_list_result_files(task_id)
                    if rf.get("ok"):
                        data["result_files"] = rf["result_files"]
                instruction = (
                    "Task finished; call list_result_files(task_id) for outputs."
                    if done else _DISPLAY_RUNNING
                )
                return self._env_ok(
                    "wait_for_next_update", data=data,
                    biomni_url=self._biomni_url(task_id),
                    display_instruction=instruction,
                )
            first = False
            if time.time() >= deadline:
                return self._env_ok(
                    "wait_for_next_update",
                    data={
                        "task_id": task_id, "status": status or "unknown",
                        "cursor": cursor, "done": False, "new_messages": [],
                        "new_log": [], "timed_out": True,
                    },
                    biomni_url=self._biomni_url(task_id),
                    display_instruction=_DISPLAY_RUNNING,
                )
            time.sleep(poll_interval)

    def list_tasks(self, project_id: str = "") -> ToolEnvelope:
        """List a project's sessions/tasks. With no ``project_id``, aggregate."""
        pid = project_id or self._current_project
        if pid:
            r = self._call("GET", f"/v2/agent/projects/{pid}/sessions")
            if not r.get("ok"):
                return self._env_err("list_tasks", r.get("error", "list_tasks failed"))
            return self._env_ok(
                "list_tasks",
                data={
                    "project_id": pid,
                    "tasks": self._as_list(r["data"], "sessions", "tasks"),
                },
            )
        projs = self._do_list_projects()
        if not projs.get("ok"):
            return self._env_err("list_tasks", projs.get("error", "list_tasks failed"))
        tasks: list[Any] = []
        for p in projs["projects"]:
            ppid = _extract(p, "id", "project_id", "proj_id")
            if not ppid:
                continue
            r = self._call("GET", f"/v2/agent/projects/{ppid}/sessions")
            if r.get("ok"):
                for s in self._as_list(r["data"], "sessions", "tasks"):
                    if isinstance(s, dict):
                        s.setdefault("project_id", ppid)
                    tasks.append(s)
        return self._env_ok(
            "list_tasks", data={"project_id": None, "tasks": tasks, "aggregated": True}
        )

    def _do_list_result_files(self, task_id: str) -> dict[str, Any]:
        """Account-wide results (``GET /v2/files/results``), filtered client-side.

        Rows are normalized through :class:`schema.ResultFile`, mapping the
        phylo ``session_id`` onto the canonical ``task_id`` so both backends
        return byte-identical result rows.
        """
        r = self._call("GET", "/v2/files/results")
        if not r.get("ok"):
            return r
        rows = self._as_list(r["data"], "results", "files")
        files: list[dict[str, Any]] = []
        matched_any = False
        for row in rows:
            if not isinstance(row, dict):
                continue
            row_sid = _extract(row, "session_id", "task_id", "sessionId")
            if task_id and row_sid and row_sid != task_id:
                continue
            if row_sid:
                matched_any = True
            rf = ResultFile(
                name=str(_extract(row, "name", "filename", "file_name") or ""),
                size=_coerce_size(_extract(row, "size", "file_size", "bytes")),
                task_id=row_sid,
                path=_extract(row, "path", "sandbox_path"),
            )
            files.append(rf.model_dump())
        note = None
        if task_id:
            note = (
                "filtered by task_id" if matched_any
                else "results rows carry no session id; returning account-wide list"
            )
        return _ok(task_id=task_id or None, result_files=files, note=note)

    def list_result_files(self, task_id: str = "") -> ToolEnvelope:
        r = self._do_list_result_files(task_id)
        if not r.get("ok"):
            return self._env_err(
                "list_result_files", r.get("error", "list_result_files failed")
            )
        return self._env_ok(
            "list_result_files",
            data={
                "task_id": r.get("task_id"),
                "result_files": r.get("result_files", []),
                "note": r.get("note"),
            },
        )

    # ---- bridge affordance (non-canonical) -------------------------------
    def fetch_artifact(self, task_id: str, name: str) -> dict[str, Any]:
        """Return an artifact download HINT (bytes are not API-fetchable online).

        The hosted Biomni sandbox paths are NOT directly fetchable over the API,
        so this returns a web URL hint rather than bytes; the databricks backend
        returns real bytes. Consumed by ``features.bridge`` (returns None bytes).
        """
        dl = self._call(
            "GET", f"/v2/files/results/{task_id}/{urllib.parse.quote(name)}"
        )
        if dl.get("ok"):
            return _ok(task_id=task_id, name=name, raw=dl["data"])
        return _err(
            "online backend cannot stream artifact bytes (sandbox paths are not "
            "API-fetchable). Open biomni_url / download from the web app; or use "
            "the databricks backend, which returns real bytes.",
            task_id=task_id, name=name, biomni_url=self._biomni_url(task_id),
            web=self.web_base,
        )


# Factory the hub's backend selector calls (mirrors databricks.build_adapter).
def build_adapter(**overrides: Any) -> OnlineBiomniAdapter:
    return OnlineBiomniAdapter(**overrides)


# Canonical factory alias accepted by backends._ADAPTER_SPECS.
def get_backend(**overrides: Any) -> OnlineBiomniAdapter:
    return OnlineBiomniAdapter(**overrides)
