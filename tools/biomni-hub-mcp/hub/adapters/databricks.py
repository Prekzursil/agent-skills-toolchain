"""biomni-hub :: Databricks backend adapter (Track B).

Self-hosts Biomni on the owner-authorized **bolt-datascience** Databricks
workspace and exposes it through the *same* 10-tool canonical surface as the
online (claude.ai Biomni Lab) backend. The hub authors that surface ONCE in a
shared schema; this module only implements the backend-specific plumbing.

==============================================================================
WHY THIS SHAPE  (empirically forced -- see databricks/deploy/README.md)
==============================================================================
Phase-1 probing of bolt-datascience with the owner's PAT established hard
constraints that dictate the execution model:

  1. ``jobs/runs/submit`` with ``new_cluster`` is REJECTED:
        PERMISSION_DENIED: You are not authorized to create clusters.
     -> the "ephemeral Jobs" pattern is unavailable to this identity.

  2. The identity CAN start an all-purpose cluster it already owns
     (``0708-143705-igywn40c``, r5.2xlarge / 15.4 LTS / x86_64), created
     under the workspace cluster policy.

  3. That cluster is ``workload_type.clients = {jobs:false, notebooks:true}``
     -> it refuses Jobs runs but accepts the **Command Execution API**
        (contexts + commands), i.e. the notebook/REPL path.

Therefore the ONLY viable execution model is the **warm Command/Context API**:
start (or reuse) the owned all-purpose cluster, create ONE long-lived Python
execution context on its driver, and drive Biomni by sending commands into
that persistent REPL. The REPL keeps a live ``biomni.agent.A1`` object and an
in-process task registry across calls -- which is exactly what Biomni's
async, multi-turn agent model wants anyway. Ephemeral-Jobs support is kept as
a *disabled* code path that activates automatically if a future identity gains
cluster-create + jobs entitlement.

==============================================================================
MAPPING  canonical tool  ->  Databricks mechanism
==============================================================================
  create_project        local metadata store (JSON on the UC Volume / DBFS)
  list_projects         "
  list_workspaces       synthesized: one logical workspace == one cluster
  switch_workspace      rebind self.cluster_id (+ tear down old context)
  upload_file           dbfs.put / files.upload -> the task input dir
  start_new_task        exec: spawn A1().go_stream(prompt) on a daemon thread,
                          register task_id -> {status, log, result_dir}
  send_message          exec: push a follow-up turn into a running task
  wait_for_next_update  exec: poll the in-REPL registry; return new log lines
                          + status (async task model, 30s..10min+)
  list_tasks            exec: dump the registry
  list_result_files     files/dbfs list of the task result dir (name + size)
  fetch_artifact        files.download / dbfs.read -> REAL bytes (base64)

Everything crosses the wire as small JSON blobs printed by the driver and
parsed here -- never large payloads inline (artifacts stream via the Files
API). All methods FAIL CLOSED: any Databricks error is caught and surfaced as
a structured error dict so the hub's backend selector can fall back to online.

This module depends only on ``databricks-sdk`` (already the transport used by
cloud-hub's dbx_* tools). It reads the active profile from the standard
``DATABRICKS_HOST`` / ``DATABRICKS_TOKEN`` env (the ``bolt-ds`` account).
"""

from __future__ import annotations

import base64
import json
import os
import textwrap
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from backends import BiomniBackend
from schema import BackendDescriptor, ResultFile, ToolEnvelope

try:  # databricks-sdk is the only backend dependency
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.compute import Language
    _SDK_OK = True
except Exception:  # pragma: no cover - import guard
    WorkspaceClient = object  # type: ignore
    Language = None  # type: ignore
    _SDK_OK = False


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
# The owned, policy-created all-purpose cluster proven startable in Phase-1.
DEFAULT_CLUSTER_ID = os.environ.get(
    "BIOMNI_DBX_CLUSTER_ID", "0708-143705-igywn40c"
)
# Unity Catalog Volume that holds the Biomni data lake + per-task IO.
# Provisioned ONCE (see databricks/deploy/provision.py). Falls back to DBFS if
# the workspace has no UC Volume the identity can write (SQL/UC varies).
DEFAULT_DATA_ROOT = os.environ.get(
    "BIOMNI_DBX_DATA_ROOT", "dbfs:/biomni-hub"
)
# Databricks secret holding the Claude key Biomni's A1 uses as its LLM.
# NOTE (Phase-1 verified): the workspace's pre-existing ``anthropic`` scope is
# NOT readable by this identity (secrets/list + dbutils.get both denied), so
# the deploy creates an OWNED scope ``biomni-hub`` and stores the key there.
# Read-back through dbutils.secrets.get was proven to work for this scope.
DEFAULT_LLM_SECRET = os.environ.get(
    "BIOMNI_DBX_LLM_SECRET", "biomni-hub/anthropic_api_key"
)
DEFAULT_LLM_MODEL = os.environ.get(
    "BIOMNI_DBX_LLM_MODEL", "claude-sonnet-4-20250514"
)
# Reduced install for Phase-1; swap for the full biomni_e1 image later.
# Verified on bolt-datascience: ``pip install biomni`` alone is insufficient --
# biomni.agent.A1 also needs langchain_openai + langchain_anthropic, and the
# install MUST be notebook-scoped %pip (subprocess pip is shadowed by DBR's
# preinstalled pydantic v1 -> ImportError PydanticDeprecationWarning).
DEFAULT_PIP_SPEC = os.environ.get(
    "BIOMNI_DBX_PIP_SPEC", "biomni langchain_openai langchain_anthropic"
)

CLUSTER_START_TIMEOUT_S = int(os.environ.get("BIOMNI_DBX_START_TIMEOUT", "600"))
EXEC_POLL_TIMEOUT_S = int(os.environ.get("BIOMNI_DBX_EXEC_TIMEOUT", "1800"))


def _ok(**kw: Any) -> dict[str, Any]:
    d = {"ok": True}
    d.update(kw)
    return d


def _err(msg: str, **kw: Any) -> dict[str, Any]:
    d = {"ok": False, "error": msg, "backend": "databricks"}
    d.update(kw)
    return d


def _coerce_size(value: Any) -> int:
    """Coerce a DBFS size field to a non-negative int (ResultFile requires it)."""
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return max(0, int(value))
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return 0


# --------------------------------------------------------------------------
# The persistent driver-side program.
# --------------------------------------------------------------------------
# Sent ONCE into the execution context. Installs reduced biomni (idempotent),
# and defines a global task registry + helpers that later commands call. Keeps
# A1 objects and task threads alive for the life of the context (the whole
# point of the warm-context pattern).
#
# The real content lives in deploy/bootstrap.py; it is embedded here so the
# adapter is self-contained (no file upload needed to boot the REPL).
BOOTSTRAP = textwrap.dedent(
    r'''
    import os, sys, json, time, threading, traceback, subprocess, importlib

    _BIOMNI_HUB = globals().setdefault("_BIOMNI_HUB", {
        "tasks": {},          # task_id -> {status, log[], result_dir, agent}
        "ready": False,
        "biomni_version": None,
        "install_log": "",
        "data_root": None,
        "llm_model": None,
    })

    def _hub_emit(obj):
        print("@@BIOMNI_HUB@@" + json.dumps(obj) + "@@END@@")

    def hub_setup(data_root, llm_model):
        # Libraries are installed OUT-OF-BAND by adapter.boot() via notebook
        # -scoped %pip + dbutils.library.restartPython() BEFORE this program is
        # (re)sent -- subprocess pip inside the REPL is shadowed by DBR's
        # preinstalled pydantic v1, so we never install here.
        H = _BIOMNI_HUB
        H["data_root"] = data_root
        H["llm_model"] = llm_model
        local_root = data_root.replace("dbfs:/", "/dbfs/")
        os.makedirs(local_root, exist_ok=True)
        os.makedirs(os.path.join(local_root, "tasks"), exist_ok=True)
        import biomni  # must already be importable post-%pip  # noqa
        from biomni.agent import A1  # noqa: F401  fail loud if deps missing
        H["biomni_version"] = getattr(biomni, "__version__", "unknown")
        H["ready"] = True
        _hub_emit({"op": "setup", "ready": True,
                   "biomni_version": H["biomni_version"]})

    def _run_agent(task_id, prompt, llm_secret_scope, llm_secret_key):
        H = _BIOMNI_HUB
        rec = H["tasks"][task_id]
        try:
            # Resolve the LLM key from the OWNED Databricks secret at run time
            # (read-back verified for the biomni-hub scope). A1 accepts api_key
            # directly (verified signature), and we also export the env var for
            # any langchain sub-client that reads it.
            key = dbutils.secrets.get(llm_secret_scope, llm_secret_key)  # noqa
            os.environ["ANTHROPIC_API_KEY"] = key
            from biomni.agent import A1
            local_root = H["data_root"].replace("dbfs:/", "/dbfs/")
            agent = A1(path=os.path.join(local_root, "tasks", task_id),
                       llm=H["llm_model"], api_key=key)
            rec["agent"] = agent
            rec["status"] = "running"
            # Stream so wait_for_next_update sees incremental log lines.
            gen = agent.go_stream(prompt) if hasattr(agent, "go_stream") \
                else iter([agent.go(prompt)])
            for step in gen:
                rec["log"].append(str(step)[:4000])
            rec["status"] = "completed"
        except Exception as e:
            rec["status"] = "failed"
            rec["log"].append("ERROR: " + repr(e))
            rec["log"].append(traceback.format_exc()[-2000:])

    def hub_start_task(prompt, llm_secret_scope, llm_secret_key):
        H = _BIOMNI_HUB
        task_id = "t_" + os.urandom(4).hex()
        local_root = H["data_root"].replace("dbfs:/", "/dbfs/")
        result_dir = os.path.join(local_root, "tasks", task_id)
        os.makedirs(result_dir, exist_ok=True)
        H["tasks"][task_id] = {"status": "queued", "log": [],
                               "result_dir": result_dir, "cursor": 0,
                               "agent": None}
        th = threading.Thread(target=_run_agent, daemon=True,
                              args=(task_id, prompt, llm_secret_scope,
                                    llm_secret_key))
        th.start()
        _hub_emit({"op": "start_task", "task_id": task_id, "status": "queued"})

    def hub_wait_update(task_id, since=None):
        rec = _BIOMNI_HUB["tasks"].get(task_id)
        if rec is None:
            _hub_emit({"op": "wait", "error": "unknown task_id"}); return
        cur = rec["cursor"] if since is None else int(since)
        new = rec["log"][cur:]
        rec["cursor"] = len(rec["log"])
        _hub_emit({"op": "wait", "task_id": task_id, "status": rec["status"],
                   "cursor": rec["cursor"], "new_log": new})

    def hub_send_message(task_id, message):
        rec = _BIOMNI_HUB["tasks"].get(task_id)
        if rec is None or rec.get("agent") is None:
            _hub_emit({"op": "send", "error": "no live agent for task"}); return
        try:
            ag = rec["agent"]
            fn = getattr(ag, "add_message", None) or getattr(ag, "go", None)
            rec["log"].append("USER: " + message)
            if fn:
                out = fn(message)
                rec["log"].append(str(out)[:4000])
            _hub_emit({"op": "send", "task_id": task_id, "status": "ok"})
        except Exception as e:
            _hub_emit({"op": "send", "error": repr(e)})

    def hub_list_tasks():
        H = _BIOMNI_HUB
        _hub_emit({"op": "list_tasks", "tasks": {
            k: {"status": v["status"], "log_len": len(v["log"]),
                "result_dir": v["result_dir"]}
            for k, v in H["tasks"].items()}})
    '''
)


# --------------------------------------------------------------------------
# Adapter
# --------------------------------------------------------------------------
@dataclass
class DatabricksBiomniAdapter(BiomniBackend):
    """Backend adapter for self-hosted Biomni on Databricks.

    Subclasses :class:`backends.BiomniBackend`: the 10 canonical tools each
    return a :class:`schema.ToolEnvelope` (lifecycle fields in ``data``;
    ``biomni_url``/``display_instruction`` at envelope level), plus ``describe``
    and the bridge helpers ``fetch_artifact``/``status``. Instantiated by the hub
    only when the selector resolves to ``databricks``; one instance per (host,
    cluster).
    """

    name: str = "databricks"
    cluster_id: str = DEFAULT_CLUSTER_ID
    data_root: str = DEFAULT_DATA_ROOT
    llm_secret: str = DEFAULT_LLM_SECRET
    llm_model: str = DEFAULT_LLM_MODEL
    pip_spec: str = DEFAULT_PIP_SPEC
    _w: Any = field(default=None, repr=False)
    _context_id: str | None = field(default=None, repr=False)
    _booted: bool = field(default=False, repr=False)

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

    # ---- lifecycle -------------------------------------------------------
    def _client(self) -> Any:
        if self._w is None:
            if not _SDK_OK:
                raise RuntimeError("databricks-sdk not installed")
            self._w = WorkspaceClient()  # reads DATABRICKS_HOST/TOKEN
        return self._w

    def status(self) -> dict[str, Any]:
        """Backend availability for the ``biomni_backends`` catalog tool.

        Mirrors cloud-hub's ``compute_catalog`` entry shape: availability,
        state, and a coarse cost hint. Never raises -- fail closed.
        """
        try:
            w = self._client()
            me = w.current_user.me()
            c = w.clusters.get(self.cluster_id)
            return _ok(
                backend="databricks",
                available=True,
                workspace=w.config.host,
                identity=getattr(me, "user_name", None),
                cluster_id=self.cluster_id,
                cluster_state=str(getattr(c, "state", "?")),
                node_type=getattr(c, "node_type_id", None),
                execution_model="warm-command-context",
                booted=self._booted,
                biomni_ready=self._booted,
                cost_hint="per-second all-purpose DBU while cluster RUNNING; "
                          "autoterminates when idle",
            )
        except Exception as e:  # noqa: BLE001
            return _err(f"status probe failed: {e!r}", available=False)

    def describe(self) -> BackendDescriptor:
        """Non-networking readiness row for the ``biomni_backends`` catalog.

        Reports config-level readiness (SDK present + ``DATABRICKS_HOST``/
        ``DATABRICKS_TOKEN`` set) WITHOUT a live cluster round-trip, so the
        catalog never blocks on a cold/absent cluster. Use :meth:`status` for the
        richer, networked probe (live cluster state).
        """
        if not _SDK_OK:
            return BackendDescriptor(
                name=self.name, available=False, is_default=False,
                status="unconfigured", cost="unknown",
                detail="databricks-sdk not installed",
            )
        configured = bool(
            os.environ.get("DATABRICKS_HOST") and os.environ.get("DATABRICKS_TOKEN")
        )
        detail = (
            f"cluster={self.cluster_id} data_root={self.data_root} "
            f"booted={self._booted}"
            if configured
            else "set DATABRICKS_HOST / DATABRICKS_TOKEN (bolt-ds account/PAT)"
        )
        return BackendDescriptor(
            name=self.name,
            available=configured,
            is_default=False,
            status="ready" if configured else "unconfigured",
            cost="per-second all-purpose DBU while cluster RUNNING; "
                 "autoterminates when idle",
            detail=detail,
        )

    def ensure_cluster(self) -> dict[str, Any]:
        """Start the owned cluster if not RUNNING and wait until ready."""
        try:
            w = self._client()
            c = w.clusters.get(self.cluster_id)
            state = str(getattr(c, "state", ""))
            if state != "RUNNING":
                w.clusters.start(self.cluster_id)
                deadline = time.time() + CLUSTER_START_TIMEOUT_S
                while time.time() < deadline:
                    c = w.clusters.get(self.cluster_id)
                    state = str(getattr(c, "state", ""))
                    if "RUNNING" in state:
                        break
                    if any(s in state for s in ("ERROR", "TERMINATED")):
                        return _err(f"cluster entered {state} while starting")
                    time.sleep(15)
            return _ok(cluster_id=self.cluster_id, state=state)
        except Exception as e:  # noqa: BLE001
            return _err(f"ensure_cluster failed: {e!r}")

    def _ensure_context(self) -> str:
        w = self._client()
        if self._context_id:
            try:
                st = w.command_execution.context_status(
                    cluster_id=self.cluster_id, context_id=self._context_id)
                if "Running" in str(getattr(st, "status", "")):
                    return self._context_id
            except Exception:
                self._context_id = None
        ctx = w.command_execution.create_and_wait(
            cluster_id=self.cluster_id,
            language=Language.PYTHON if Language else "python")
        self._context_id = ctx.id
        return self._context_id

    def _exec(self, code: str) -> str:
        """Run python in the persistent context; return raw stdout."""
        w = self._client()
        ctx = self._ensure_context()
        res = w.command_execution.execute_and_wait(
            cluster_id=self.cluster_id, context_id=ctx,
            language=Language.PYTHON if Language else "python",
            command=code, timeout=None)
        data = getattr(res.results, "data", None) if res.results else None
        cause = getattr(res.results, "cause", None) if res.results else None
        return data if data is not None else (cause or "")

    @staticmethod
    def _parse_emit(stdout: str) -> dict[str, Any]:
        """Pull the last @@BIOMNI_HUB@@...@@END@@ JSON blob from stdout."""
        marker, end = "@@BIOMNI_HUB@@", "@@END@@"
        i = stdout.rfind(marker)
        if i == -1:
            return {"_raw": stdout[-2000:]}
        j = stdout.find(end, i)
        try:
            return json.loads(stdout[i + len(marker):j])
        except Exception:
            return {"_raw": stdout[-2000:]}

    def boot(self, reinstall: bool = False) -> dict[str, Any]:
        """Bring the warm context up to a biomni-ready state (idempotent).

        Verified sequence on bolt-datascience (Phase-1):
          1. ensure the owned cluster is RUNNING;
          2. notebook-scoped ``%pip install <pip_spec>`` (NOT subprocess pip --
             that gets shadowed by DBR's pydantic v1);
          3. ``dbutils.library.restartPython()`` so the new libs take path
             precedence (this resets REPL globals, so it must precede the defs);
          4. (re)send BOOTSTRAP to define the task registry + helpers;
          5. ``hub_setup`` to make dirs and confirm ``from biomni.agent import
             A1`` succeeds -> emits ``ready:true``.

        A already-warm context (``self._booted``) short-circuits unless
        ``reinstall`` is set.
        """
        if self._booted and not reinstall:
            return _ok(already_booted=True)
        started = self.ensure_cluster()
        if not started.get("ok"):
            return started
        try:
            # Steps 2-3: idempotent install + restart. %pip is a no-op cost
            # when the libs are already present in the ephemeral env.
            self._exec(f"%pip install --quiet {self.pip_spec}")
            self._exec("dbutils.library.restartPython()")
            # Step 4: defs (globals were wiped by the restart).
            self._exec(BOOTSTRAP)
            # Step 5: setup + import check.
            out = self._exec(
                f"hub_setup({self.data_root!r}, {self.llm_model!r})")
            emit = self._parse_emit(out)
            self._booted = bool(emit.get("ready"))
            return _ok(**emit) if self._booted else _err(
                "biomni setup did not report ready", detail=emit)
        except Exception as e:  # noqa: BLE001
            return _err(f"boot failed: {e!r}")

    def _ensure_booted(self) -> dict[str, Any] | None:
        if not self._booted:
            b = self.boot()
            if not b.get("ok"):
                return b
        return None

    # ---- canonical control-plane (synthesized on Databricks) -------------
    def _meta_path(self) -> str:
        return self.data_root.rstrip("/") + "/hub_meta.json"

    def _read_meta(self) -> dict[str, Any]:
        try:
            w = self._client()
            raw = w.dbfs.read(self._meta_path()).data
            return json.loads(base64.b64decode(raw).decode())
        except Exception:
            return {"projects": {}, "current_project": None}

    def _write_meta(self, meta: dict[str, Any]) -> None:
        w = self._client()
        blob = base64.b64encode(json.dumps(meta).encode()).decode()
        w.dbfs.put(self._meta_path(), contents=blob, overwrite=True)

    def create_project(self, name: str, description: str = "") -> ToolEnvelope:
        try:
            meta = self._read_meta()
            pid = "p_" + uuid.uuid4().hex[:8]
            meta["projects"][pid] = {"id": pid, "name": name,
                                     "description": description,
                                     "created": time.time()}
            meta["current_project"] = pid
            self._write_meta(meta)
        except Exception as e:  # noqa: BLE001
            return self._env_err("create_project", f"create_project failed: {e!r}")
        return self._env_ok(
            "create_project", data={"project_id": pid, "name": name}
        )

    def list_projects(self) -> ToolEnvelope:
        try:
            projects = list(self._read_meta()["projects"].values())
        except Exception as e:  # noqa: BLE001
            return self._env_err("list_projects", f"list_projects failed: {e!r}")
        return self._env_ok("list_projects", data={"projects": projects})

    def list_workspaces(self) -> ToolEnvelope:
        # One logical workspace == one Databricks cluster.
        s = self.status()
        return self._env_ok(
            "list_workspaces",
            data={
                "workspaces": [
                    {
                        "id": self.cluster_id,
                        "name": f"databricks::{self.cluster_id}",
                        "state": s.get("cluster_state"), "current": True,
                    }
                ]
            },
        )

    def switch_workspace(self, workspace_id: str) -> ToolEnvelope:
        if workspace_id != self.cluster_id:
            self._context_id = None
            self._booted = False
            self.cluster_id = workspace_id
        return self._env_ok(
            "switch_workspace", data={"workspace_id": self.cluster_id, "current": True}
        )

    def upload_file(
        self, local_path: str, project_id: str = "", destination: str = ""
    ) -> ToolEnvelope:
        try:
            w = self._client()
            name = destination or os.path.basename(local_path)
            dest = self.data_root.rstrip("/") + "/inputs/" + name
            with open(local_path, "rb") as fh:
                blob = base64.b64encode(fh.read()).decode()
            w.dbfs.put(dest, contents=blob, overwrite=True)
            return self._env_ok(
                "upload_file", data={"dest": dest, "name": name}
            )
        except Exception as e:  # noqa: BLE001
            return self._env_err("upload_file", f"upload_file failed: {e!r}")

    # ---- canonical task-plane (Command API) ------------------------------
    def start_new_task(
        self, project_id: str, prompt: str, model_profile: str = "standard"
    ) -> ToolEnvelope:
        # project_id/model_profile accepted for signature-parity with the online
        # backend (dispatched POSITIONALLY by the hub, so ORDER matches the ABC).
        # On Databricks the "project" is the local metadata store and every task
        # shares the one cluster; model_profile could later select an LLM tier via
        # self.llm_model. ``message_id``/``model_profile`` are surfaced in ``data``
        # so the envelope is field-identical to the online backend.
        boot_err = self._ensure_booted()
        if boot_err:
            return self._env_err(
                "start_new_task", boot_err.get("error", "boot failed")
            )
        scope, key = self.llm_secret.split("/", 1)
        out = self._exec(f"hub_start_task({prompt!r}, {scope!r}, {key!r})")
        emit = self._parse_emit(out)
        if "task_id" not in emit:
            return self._env_err(
                "start_new_task", f"no task_id in driver emit: {emit}"
            )
        return self._env_ok(
            "start_new_task",
            data={
                "task_id": emit["task_id"],
                "project_id": project_id,
                "message_id": None,  # databricks has no per-message id; parity key
                "status": emit.get("status"),
                "model_profile": model_profile,
            },
            biomni_url=self._run_page_url(),
            display_instruction="Poll wait_for_next_update(task_id); "
            "Biomni tasks run 30s-10min+.",
        )

    def _run_page_url(self) -> str:
        try:
            host = self._client().config.host.rstrip("/")
        except Exception:  # noqa: BLE001
            return ""
        return f"{host}/#setting/clusters/{self.cluster_id}"

    def send_message(self, task_id: str, content: str) -> ToolEnvelope:
        out = self._exec(f"hub_send_message({task_id!r}, {content!r})")
        emit = self._parse_emit(out)
        if emit.get("error"):
            return self._env_err("send_message", str(emit["error"]))
        return self._env_ok("send_message", data=emit)

    def wait_for_next_update(
        self, task_id: str, timeout_seconds: float = 60.0, *,
        since: int | None = None,
    ) -> ToolEnvelope:
        # timeout_seconds accepted for signature-parity with online (dispatched
        # positionally). The databricks task runs on a driver thread and the
        # registry is polled instantly, so this returns the latest delta
        # immediately rather than long-polling. ``since`` (keyword-only) is the
        # resume cursor. ``new_messages``/``biomni_url``/``display_instruction``/
        # ``result_files`` are surfaced for field-parity with the online backend.
        arg = "None" if since is None else str(int(since))
        out = self._exec(f"hub_wait_update({task_id!r}, {arg})")
        emit = self._parse_emit(out)
        if emit.get("error"):
            return self._env_err("wait_for_next_update", str(emit["error"]))
        status = str(emit.get("status", "")).lower()
        done = status in ("completed", "failed")
        new_log = emit.get("new_log", [])
        data: dict[str, Any] = {
            "task_id": emit.get("task_id", task_id),
            "status": emit.get("status", "unknown"),
            "cursor": emit.get("cursor"),
            "done": done,
            "new_log": new_log,
            "new_messages": list(new_log),  # parity: online splits msgs vs log
        }
        if done:
            rf = self._do_list_result_files(task_id)
            if rf.get("ok"):
                data["result_files"] = rf["result_files"]
        instruction = (
            "Task finished; call list_result_files(task_id) for outputs."
            if done else "Poll wait_for_next_update(task_id); Biomni tasks run "
            "30s-10min+."
        )
        return self._env_ok(
            "wait_for_next_update", data=data,
            biomni_url=self._run_page_url(),
            display_instruction=instruction,
        )

    def list_tasks(self, project_id: str = "") -> ToolEnvelope:
        # project_id accepted for parity; the warm context holds ALL tasks.
        out = self._exec("hub_list_tasks()")
        emit = self._parse_emit(out)
        return self._env_ok(
            "list_tasks", data={"project_id": project_id or None, **emit}
        )

    def _do_list_result_files(self, task_id: str) -> dict[str, Any]:
        """DBFS listing normalized through :class:`schema.ResultFile` rows keyed
        by the canonical ``task_id`` (parity with the online backend)."""
        try:
            w = self._client()
            tasks_root = self.data_root.rstrip("/") + "/tasks"
            targets = ([task_id] if task_id
                       else [os.path.basename(d.path.rstrip("/"))
                             for d in w.dbfs.list(tasks_root)
                             if getattr(d, "is_dir", False)])
            files: list[dict[str, Any]] = []
            for tid in targets:
                try:
                    for f in w.dbfs.list(f"{tasks_root}/{tid}"):
                        if not getattr(f, "is_dir", False):
                            rf = ResultFile(
                                name=os.path.basename(f.path),
                                size=_coerce_size(getattr(f, "file_size", None)),
                                task_id=tid,
                                path=f.path,
                            )
                            files.append(rf.model_dump())
                except Exception:  # noqa: BLE001 - task dir may not exist yet
                    continue
            return _ok(task_id=task_id or None, result_files=files)
        except Exception as e:  # noqa: BLE001
            return _err(f"list_result_files failed: {e!r}")

    def list_result_files(self, task_id: str = "") -> ToolEnvelope:
        r = self._do_list_result_files(task_id)
        if not r.get("ok"):
            return self._env_err(
                "list_result_files", r.get("error", "list_result_files failed")
            )
        return self._env_ok(
            "list_result_files",
            data={"task_id": r.get("task_id"), "result_files": r["result_files"]},
        )

    def fetch_artifact(self, task_id: str, name: str,
                       **_: Any) -> dict[str, Any]:
        """Return REAL bytes of a result file (base64) via the Files/DBFS API."""
        try:
            w = self._client()
            path = self.data_root.rstrip("/") + f"/tasks/{task_id}/{name}"
            # dbfs.read returns base64 in ~1MB chunks; loop for larger files.
            chunks, offset, length = [], 0, 1024 * 1024
            while True:
                r = w.dbfs.read(path, offset=offset, length=length)
                if not r.bytes_read:
                    break
                chunks.append(r.data)  # already base64
                offset += r.bytes_read
                if r.bytes_read < length:
                    break
            raw = b"".join(base64.b64decode(c) for c in chunks)
            return _ok(task_id=task_id, name=name, size=len(raw),
                       content_base64=base64.b64encode(raw).decode())
        except Exception as e:  # noqa: BLE001
            return _err(f"fetch_artifact failed: {e!r}")

    def teardown(self) -> dict[str, Any]:
        """Drop the execution context (cluster autoterminates on its own)."""
        try:
            if self._context_id:
                self._client().command_execution.destroy(
                    cluster_id=self.cluster_id, context_id=self._context_id)
            self._context_id = None
            self._booted = False
            return _ok()
        except Exception as e:  # noqa: BLE001
            return _err(f"teardown failed: {e!r}")


# Factory the hub's backend selector calls.
def build_adapter(**overrides: Any) -> DatabricksBiomniAdapter:
    return DatabricksBiomniAdapter(**overrides)


# Canonical factory alias accepted by backends._ADAPTER_SPECS.
def get_backend(**overrides: Any) -> DatabricksBiomniAdapter:
    return DatabricksBiomniAdapter(**overrides)
