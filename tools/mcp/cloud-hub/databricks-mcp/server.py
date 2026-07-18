#!/usr/bin/env python3
"""Databricks MCP wrapper -- a thin FastMCP server over ``databricks-sdk``.

Tool names are PRE-NAMESPACED (``dbx_*``) so the cloud-hub's collision-prefix
never has to fire for this backend. ``databricks-sdk`` is imported LAZILY inside
each tool (behind ``_sdk()``), so ``tools/list`` enumerates even when the SDK is
not installed; a call without it -- or without credentials -- returns a clear
install/auth hint instead of crashing.

Auth (SDK unified auth resolves both): OAuth **M2M service-principal** is the
default -- ``DATABRICKS_HOST`` + ``DATABRICKS_CLIENT_ID`` + ``DATABRICKS_CLIENT_SECRET``;
**PAT** is the fallback -- ``DATABRICKS_HOST`` + ``DATABRICKS_TOKEN``. A
``~/.databrickscfg`` profile (``DATABRICKS_CONFIG_PROFILE``) also works.

stdio purity: the SDK logs via ``logging`` and can print to stdout; this server
(a) routes the ``databricks``/``urllib3`` loggers to a ``NullHandler`` at
CRITICAL and (b) wraps every SDK call in ``redirect_stdout(sys.stderr)`` so the
JSON-RPC stream on stdout is never corrupted.

$$$ cost + destruction awareness: creating/starting clusters and warehouses,
running commands, and serving endpoints bill real money -- confirm intent, set
``autotermination_minutes``, and stop/terminate when done. The genuinely
destructive or code-executing tools (``dbx_cluster_terminate``,
``dbx_cluster_permanent_delete``, ``dbx_warehouse_delete``, ``dbx_exec``,
``dbx_run_on_cluster``) are gated behind ``confirm=True`` and otherwise return a
dry-run preview. Cluster/warehouse lifecycle calls expose an opt-in ``wait``
flag (the SDK ``*_and_wait`` variants) that blocks until the target state.

Command Execution (``dbx_ctx_*``/``dbx_exec``/``dbx_run_on_cluster``) works ONLY
on classic all-purpose clusters (not serverless/jobs compute). ``dbx_api_raw``
is the escape hatch to ANY Databricks REST endpoint.
"""

from __future__ import annotations

import base64
import contextlib
import io
import json
import logging
import sys

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("databricks")

# Caps so a single tool result can never flood the JSON-RPC stream.
_MAX_ITEMS = 500  # list/iterator pagination cap
_MAX_READ = 900_000  # bytes returned by a dbfs/volume read (DBFS read caps ~1MB)

_LOGGING_SILENCED = False


# --------------------------------------------------------------------------- #
# SDK access + stdio-purity helpers
# --------------------------------------------------------------------------- #
def _silence_logging() -> None:
    """Route the SDK's loggers to a NullHandler so nothing reaches stdout."""
    global _LOGGING_SILENCED
    if _LOGGING_SILENCED:
        return
    for name in ("databricks", "databricks.sdk", "urllib3"):
        lg = logging.getLogger(name)
        lg.setLevel(logging.CRITICAL)
        lg.handlers = [logging.NullHandler()]
        lg.propagate = False
    _LOGGING_SILENCED = True


def _sdk():
    """Import ``databricks.sdk`` lazily; return (module, error_message)."""
    try:
        import databricks.sdk as dbx  # noqa: PLC0415  (lazy on purpose)
    except Exception as exc:  # noqa: BLE001  (surface any import failure as text)
        return None, (
            "databricks-sdk not available; `pip install databricks-sdk` and set "
            "DATABRICKS_HOST + (DATABRICKS_CLIENT_ID/_SECRET for OAuth M2M or "
            f"DATABRICKS_TOKEN for a PAT) ({exc})"
        )
    _silence_logging()
    return dbx, None


def _client():
    """Build a ``WorkspaceClient`` (unified auth); return (client, error)."""
    dbx, err = _sdk()
    if err:
        return None, err
    try:
        with contextlib.redirect_stdout(sys.stderr):
            return dbx.WorkspaceClient(), None
    except Exception as exc:  # noqa: BLE001
        return None, (
            "Databricks auth/init failed; set DATABRICKS_HOST + "
            "(DATABRICKS_CLIENT_ID/_SECRET for OAuth M2M or DATABRICKS_TOKEN for a "
            f"PAT), or a ~/.databrickscfg profile ({type(exc).__name__}: {exc})"
        )


def _fail(error: str) -> str:
    return json.dumps({"ok": False, "error": error}, ensure_ascii=False)


def _run(fn) -> str:
    """Run ``fn(workspace_client)`` under stdout-silencing + uniform errors.

    ``fn`` returns a JSON-able payload (use ``_dump``/``_collect`` inside). All
    exceptions become a ``{"ok": false, "error": ...}`` string -- the wrapper
    never raises, mirroring the modal/lightning backends.
    """
    client, err = _client()
    if err:
        return _fail(err)
    try:
        with contextlib.redirect_stdout(sys.stderr):
            data = fn(client)
    except Exception as exc:  # noqa: BLE001
        return _fail(f"{type(exc).__name__}: {exc}")
    return json.dumps({"ok": True, "data": data}, ensure_ascii=False, default=str)


def _dump(obj):
    """Best-effort JSON-able view of an SDK object (``.as_dict()`` when present)."""
    if obj is None or isinstance(obj, (str, int, float, bool, dict)):
        return obj
    if hasattr(obj, "as_dict"):
        try:
            return obj.as_dict()
        except Exception:  # noqa: BLE001
            return str(obj)
    if isinstance(obj, (list, tuple)):
        return [_dump(x) for x in obj]
    return str(obj)


def _collect(iterable, limit: int = _MAX_ITEMS) -> list:
    """Materialize an SDK iterator into a capped list of dumped items."""
    out: list = []
    for idx, item in enumerate(iterable):
        if idx >= limit:
            out.append({"_truncated": f"more than {limit} items; refine the query"})
            break
        out.append(_dump(item))
    return out


def _ack(_result, ack: dict) -> dict:
    """Ignore a void/opaque SDK return and surface a fixed acknowledgement."""
    return ack


def _guard(action: str, target: str, confirm: bool) -> str | None:
    """Return a dry-run JSON string unless ``confirm`` is True (then None)."""
    if confirm:
        return None
    return json.dumps(
        {
            "ok": False,
            "dry_run": True,
            "action": action,
            "target": target,
            "hint": f"destructive/billable: re-call with confirm=true to {action} "
            f"'{target}'",
        },
        ensure_ascii=False,
    )


def _to_enum(enum_cls, value: str):
    """Construct an SDK enum from its string VALUE, else its first member."""
    try:
        return enum_cls(value)
    except ValueError:
        return next(iter(enum_cls))


def _read_stream(stream) -> dict:
    """Read a binary stream (capped); decode utf-8 text, else base64."""
    raw = stream.read() if hasattr(stream, "read") else bytes(stream)
    truncated = len(raw) > _MAX_READ
    raw = raw[:_MAX_READ]
    try:
        return {"text": raw.decode("utf-8"), "truncated": truncated}
    except UnicodeDecodeError:
        return {"base64": base64.b64encode(raw).decode("ascii"), "truncated": truncated}


def _raw(client, method: str, path: str, body_json: str = "", query_json: str = ""):
    """Call ``api_client.do`` with optional JSON string body/query."""
    body = json.loads(body_json) if body_json else None
    query = json.loads(query_json) if query_json else None
    return client.api_client.do(method.upper(), path, body=body, query=query)


# --------------------------------------------------------------------------- #
# Clusters (all-purpose compute; GPU via node_type_id + a *-gpu-ml spark_version)
# --------------------------------------------------------------------------- #
@mcp.tool()
def dbx_cluster_list() -> str:
    """List all-purpose clusters in the workspace (``w.clusters.list``)."""
    return _run(lambda w: _collect(w.clusters.list()))


@mcp.tool()
def dbx_cluster_get(cluster_id: str) -> str:
    """Get one cluster's full details/state by id (``w.clusters.get``)."""
    return _run(lambda w: _dump(w.clusters.get(cluster_id)))


@mcp.tool()
def dbx_cluster_create(
    cluster_name: str,
    spark_version: str,
    node_type_id: str,
    num_workers: int = 0,
    autoscale_min: int = 0,
    autoscale_max: int = 0,
    driver_node_type_id: str = "",
    autotermination_minutes: int = 0,
    policy_id: str = "",
    spark_conf_json: str = "",
    custom_tags_json: str = "",
    wait: bool = False,
) -> str:
    """Create an all-purpose cluster. $$$ bills while RUNNING.

    GPU: set ``node_type_id`` to a GPU instance (AWS ``g4dn.xlarge``/``g5.xlarge``,
    Azure ``Standard_NC*``, GCP ``a2-*``) and ``spark_version`` to a ``*-gpu-ml``
    image from ``dbx_spark_versions``. Give ``num_workers`` OR both ``autoscale_min``
    and ``autoscale_max``. Set ``autotermination_minutes`` so an idle cluster
    stops itself. ``wait=True`` blocks until RUNNING. Advanced fields (Docker
    image, data_security_mode, cloud attrs) -> ``dbx_api_raw POST
    /api/2.1/clusters/create``.
    """

    def op(w):
        from databricks.sdk.service import compute  # noqa: PLC0415

        kwargs: dict = {
            "cluster_name": cluster_name,
            "spark_version": spark_version,
            "node_type_id": node_type_id,
        }
        if autoscale_min and autoscale_max:
            kwargs["autoscale"] = compute.AutoScale(
                min_workers=autoscale_min, max_workers=autoscale_max
            )
        else:
            kwargs["num_workers"] = num_workers
        if driver_node_type_id:
            kwargs["driver_node_type_id"] = driver_node_type_id
        if autotermination_minutes:
            kwargs["autotermination_minutes"] = autotermination_minutes
        if policy_id:
            kwargs["policy_id"] = policy_id
        if spark_conf_json:
            kwargs["spark_conf"] = json.loads(spark_conf_json)
        if custom_tags_json:
            kwargs["custom_tags"] = json.loads(custom_tags_json)
        if wait:
            return _dump(w.clusters.create_and_wait(**kwargs))
        res = w.clusters.create(**kwargs)
        return {"cluster_id": getattr(res, "cluster_id", None), "waited": False}

    return _run(op)


@mcp.tool()
def dbx_cluster_edit(
    cluster_id: str,
    spark_version: str,
    node_type_id: str,
    num_workers: int = 0,
    autoscale_min: int = 0,
    autoscale_max: int = 0,
    driver_node_type_id: str = "",
    autotermination_minutes: int = 0,
    spark_conf_json: str = "",
    custom_tags_json: str = "",
    wait: bool = False,
) -> str:
    """Edit an existing cluster's config (``w.clusters.edit``); full new spec.

    The cluster must be TERMINATED or RUNNING; edit replaces the configuration.
    Same field shape as ``dbx_cluster_create``. ``wait=True`` blocks until RUNNING.
    """

    def op(w):
        from databricks.sdk.service import compute  # noqa: PLC0415

        kwargs: dict = {
            "cluster_id": cluster_id,
            "spark_version": spark_version,
            "node_type_id": node_type_id,
        }
        if autoscale_min and autoscale_max:
            kwargs["autoscale"] = compute.AutoScale(
                min_workers=autoscale_min, max_workers=autoscale_max
            )
        else:
            kwargs["num_workers"] = num_workers
        if driver_node_type_id:
            kwargs["driver_node_type_id"] = driver_node_type_id
        if autotermination_minutes:
            kwargs["autotermination_minutes"] = autotermination_minutes
        if spark_conf_json:
            kwargs["spark_conf"] = json.loads(spark_conf_json)
        if custom_tags_json:
            kwargs["custom_tags"] = json.loads(custom_tags_json)
        if wait:
            return _dump(w.clusters.edit_and_wait(**kwargs))
        _ack(w.clusters.edit(**kwargs), {})
        return {"cluster_id": cluster_id, "edited": True, "waited": False}

    return _run(op)


@mcp.tool()
def dbx_cluster_start(cluster_id: str, wait: bool = False) -> str:
    """Start a terminated cluster (``w.clusters.start``). $$$ bills once RUNNING."""
    if wait:
        return _run(lambda w: _dump(w.clusters.start_and_wait(cluster_id)))
    return _run(
        lambda w: _ack(
            w.clusters.start(cluster_id), {"cluster_id": cluster_id, "waited": False}
        )
    )


@mcp.tool()
def dbx_cluster_restart(cluster_id: str, wait: bool = False) -> str:
    """Restart a running cluster (``w.clusters.restart``)."""
    if wait:
        return _run(lambda w: _dump(w.clusters.restart_and_wait(cluster_id)))
    return _run(
        lambda w: _ack(
            w.clusters.restart(cluster_id), {"cluster_id": cluster_id, "waited": False}
        )
    )


@mcp.tool()
def dbx_cluster_resize(
    cluster_id: str,
    num_workers: int = 0,
    autoscale_min: int = 0,
    autoscale_max: int = 0,
    wait: bool = False,
) -> str:
    """Resize a running cluster (``w.clusters.resize``): fixed workers or autoscale."""

    def op(w):
        from databricks.sdk.service import compute  # noqa: PLC0415

        kwargs: dict = {}
        if autoscale_min and autoscale_max:
            kwargs["autoscale"] = compute.AutoScale(
                min_workers=autoscale_min, max_workers=autoscale_max
            )
        else:
            kwargs["num_workers"] = num_workers
        if wait:
            return _dump(w.clusters.resize_and_wait(cluster_id, **kwargs))
        _ack(w.clusters.resize(cluster_id, **kwargs), {})
        return {"cluster_id": cluster_id, "resized": True, "waited": False}

    return _run(op)


@mcp.tool()
def dbx_cluster_terminate(cluster_id: str, confirm: bool = False) -> str:
    """Terminate (stop) a cluster, keeping its config (``w.clusters.delete``).

    Guardrail: pass ``confirm=True`` to actually terminate. The cluster can be
    restarted later with ``dbx_cluster_start``.
    """
    dry = _guard("terminate cluster", cluster_id, confirm)
    if dry:
        return dry
    return _run(
        lambda w: _ack(w.clusters.delete(cluster_id), {"terminated": cluster_id})
    )


@mcp.tool()
def dbx_cluster_permanent_delete(cluster_id: str, confirm: bool = False) -> str:
    """PERMANENTLY delete a cluster + its config (``w.clusters.permanent_delete``).

    Guardrail: pass ``confirm=True``. Irreversible -- the cluster cannot be
    restarted afterwards (unlike ``dbx_cluster_terminate``).
    """
    dry = _guard("permanently delete cluster", cluster_id, confirm)
    if dry:
        return dry
    return _run(
        lambda w: _ack(
            w.clusters.permanent_delete(cluster_id),
            {"permanently_deleted": cluster_id},
        )
    )


@mcp.tool()
def dbx_node_types() -> str:
    """List available node (instance) types incl. GPU (``w.clusters.list_node_types``)."""
    return _run(lambda w: _dump(w.clusters.list_node_types()))


@mcp.tool()
def dbx_spark_versions() -> str:
    """List available Databricks Runtime (Spark) versions (``w.clusters.spark_versions``).

    GPU clusters need a ``*-gpu-ml`` runtime (e.g. ``13.3.x-gpu-ml-scala2.12``).
    """
    return _run(lambda w: _dump(w.clusters.spark_versions()))


# --------------------------------------------------------------------------- #
# Command Execution (classic all-purpose clusters ONLY) -- the compute primitive
# --------------------------------------------------------------------------- #
def _language(compute, language: str):
    """Map a language string ('python'|'sql'|'scala'|'r') to the SDK enum."""
    return _to_enum(compute.Language, language.lower())


@mcp.tool()
def dbx_ctx_create(cluster_id: str, language: str = "python") -> str:
    """Create an execution context on a running cluster (blocks until ready).

    Returns the ``context_id`` used by ``dbx_exec``. ``language`` is one of
    python|sql|scala|r. Works only on classic all-purpose clusters.
    """

    def op(w):
        from databricks.sdk.service import compute  # noqa: PLC0415

        ctx = w.command_execution.create_and_wait(
            cluster_id=cluster_id, language=_language(compute, language)
        )
        return _dump(ctx)

    return _run(op)


@mcp.tool()
def dbx_ctx_status(cluster_id: str, context_id: str) -> str:
    """Get an execution context's status (``w.command_execution.context_status``)."""
    return _run(
        lambda w: _dump(
            w.command_execution.context_status(
                cluster_id=cluster_id, context_id=context_id
            )
        )
    )


@mcp.tool()
def dbx_ctx_destroy(cluster_id: str, context_id: str) -> str:
    """Destroy an execution context (``w.command_execution.destroy``)."""
    return _run(
        lambda w: _ack(
            w.command_execution.destroy(cluster_id=cluster_id, context_id=context_id),
            {"destroyed_context": context_id, "cluster_id": cluster_id},
        )
    )


@mcp.tool()
def dbx_exec(
    cluster_id: str,
    context_id: str,
    command: str,
    language: str = "python",
    confirm: bool = False,
) -> str:
    """Run a command in an existing context and wait for the result.

    Guardrail: executes arbitrary code on the cluster -- pass ``confirm=True``.
    ``language`` is python|sql|scala|r. Create the context first with
    ``dbx_ctx_create`` (or use ``dbx_run_on_cluster`` for the whole cycle).
    """
    dry = _guard("execute code on cluster", cluster_id, confirm)
    if dry:
        return dry

    def op(w):
        from databricks.sdk.service import compute  # noqa: PLC0415

        res = w.command_execution.execute_and_wait(
            cluster_id=cluster_id,
            context_id=context_id,
            language=_language(compute, language),
            command=command,
        )
        return _dump(res)

    return _run(op)


@mcp.tool()
def dbx_run_on_cluster(
    cluster_id: str,
    command: str,
    language: str = "python",
    confirm: bool = False,
) -> str:
    """Convenience: create context -> execute -> collect -> destroy, in one call.

    Guardrail: executes arbitrary code -- pass ``confirm=True``. The context is
    always destroyed afterwards, even on error. Classic all-purpose clusters only.
    """
    dry = _guard("execute code on cluster", cluster_id, confirm)
    if dry:
        return dry

    def op(w):
        from databricks.sdk.service import compute  # noqa: PLC0415

        lang = _language(compute, language)
        ctx = w.command_execution.create_and_wait(cluster_id=cluster_id, language=lang)
        try:
            res = w.command_execution.execute_and_wait(
                cluster_id=cluster_id,
                context_id=ctx.id,
                language=lang,
                command=command,
            )
            return {"context_id": ctx.id, "result": _dump(res)}
        finally:
            with contextlib.suppress(Exception):
                w.command_execution.destroy(cluster_id=cluster_id, context_id=ctx.id)

    return _run(op)


# --------------------------------------------------------------------------- #
# Jobs + Runs (complex nested bodies use the raw REST path; ids use typed calls)
# --------------------------------------------------------------------------- #
@mcp.tool()
def dbx_job_create(settings_json: str) -> str:
    """Create a job from a full Jobs-API settings body (``POST /jobs/create``).

    ``settings_json`` is the Jobs REST 2.1 request body, e.g.
    ``{"name": "...", "tasks": [{"task_key": "...", "notebook_task": {...},
    "new_cluster": {...}}]}``. Returns the new ``job_id``.
    """
    return _run(lambda w: _raw(w, "POST", "/api/2.1/jobs/create", settings_json))


@mcp.tool()
def dbx_job_get(job_id: int) -> str:
    """Get a job's definition + settings by id (``w.jobs.get``)."""
    return _run(lambda w: _dump(w.jobs.get(job_id)))


@mcp.tool()
def dbx_job_list(limit: int = 25, name: str = "") -> str:
    """List jobs (``w.jobs.list``), optionally filtered by exact ``name``."""
    return _run(
        lambda w: _collect(w.jobs.list(name=name or None, limit=limit), limit=limit)
    )


@mcp.tool()
def dbx_job_update(job_id: int, new_settings_json: str) -> str:
    """Partially update a job's settings (``POST /jobs/update``).

    ``new_settings_json`` is the ``new_settings`` object (fields to overwrite).
    """
    body = json.dumps({"job_id": job_id, "new_settings": json.loads(new_settings_json)})
    return _run(lambda w: _raw(w, "POST", "/api/2.1/jobs/update", body))


@mcp.tool()
def dbx_job_delete(job_id: int) -> str:
    """Delete a job by id (``w.jobs.delete``)."""
    return _run(lambda w: _ack(w.jobs.delete(job_id), {"deleted_job": job_id}))


@mcp.tool()
def dbx_job_run_now(job_id: int, params_json: str = "") -> str:
    """Trigger a job run now (``POST /jobs/run-now``). $$$ starts compute.

    ``params_json`` (optional) merges run params, e.g.
    ``{"notebook_params": {"k": "v"}}`` or ``{"python_params": ["--flag"]}``.
    Returns the new ``run_id``.
    """
    body = {"job_id": job_id}
    if params_json:
        body.update(json.loads(params_json))
    return _run(lambda w: _raw(w, "POST", "/api/2.1/jobs/run-now", json.dumps(body)))


@mcp.tool()
def dbx_run_submit(run_json: str) -> str:
    """Submit a one-off run without creating a job (``POST /jobs/runs/submit``).

    ``run_json`` is the runs-submit body, e.g. ``{"run_name": "...", "tasks":
    [{"task_key": "...", "notebook_task": {...}, "new_cluster": {...}}]}``.
    $$$ starts compute. Returns the new ``run_id``.
    """
    return _run(lambda w: _raw(w, "POST", "/api/2.1/jobs/runs/submit", run_json))


@mcp.tool()
def dbx_run_get(run_id: int) -> str:
    """Get a run's status + task tree (``w.jobs.get_run``)."""
    return _run(lambda w: _dump(w.jobs.get_run(run_id)))


@mcp.tool()
def dbx_run_get_output(run_id: int) -> str:
    """Get a completed run/task's output + logs (``w.jobs.get_run_output``).

    Pass a single-task run id (or a task run id), not a multi-task parent run id.
    """
    return _run(lambda w: _dump(w.jobs.get_run_output(run_id)))


@mcp.tool()
def dbx_run_list(job_id: int = 0, limit: int = 25, active_only: bool = False) -> str:
    """List runs (``w.jobs.list_runs``), optionally scoped to one ``job_id``."""
    return _run(
        lambda w: _collect(
            w.jobs.list_runs(
                job_id=job_id or None, active_only=active_only, limit=limit
            ),
            limit=limit,
        )
    )


@mcp.tool()
def dbx_run_cancel(run_id: int) -> str:
    """Cancel a running run (``w.jobs.cancel_run``)."""
    return _run(lambda w: _ack(w.jobs.cancel_run(run_id), {"cancelling_run": run_id}))


@mcp.tool()
def dbx_run_repair(run_id: int, params_json: str = "") -> str:
    """Repair (re-run failed tasks of) a run (``POST /jobs/runs/repair``).

    ``params_json`` (optional) e.g. ``{"rerun_all_failed_tasks": true}`` or
    ``{"rerun_tasks": ["task_key"], "notebook_params": {...}}``.
    """
    body = {"run_id": run_id}
    if params_json:
        body.update(json.loads(params_json))
    return _run(
        lambda w: _raw(w, "POST", "/api/2.1/jobs/runs/repair", json.dumps(body))
    )


# --------------------------------------------------------------------------- #
# Storage -- DBFS (put/read are base64, ~1MB cap) + Unity Catalog Volumes (Files)
# --------------------------------------------------------------------------- #
@mcp.tool()
def dbx_dbfs_list(path: str = "/") -> str:
    """List a DBFS path (``w.dbfs.list``), e.g. ``dbfs:/`` or ``/tmp``."""
    return _run(lambda w: _collect(w.dbfs.list(path)))


@mcp.tool()
def dbx_dbfs_put(path: str, contents: str, overwrite: bool = True) -> str:
    """Write UTF-8 text to a DBFS file (``w.dbfs.put``; base64, ~1MB cap).

    For larger/binary files use a Volume (``dbx_volume_upload``) or the raw API.
    """
    encoded = base64.b64encode(contents.encode("utf-8")).decode("ascii")
    return _run(
        lambda w: _ack(
            w.dbfs.put(path, contents=encoded, overwrite=overwrite),
            {"path": path, "bytes_written": len(contents.encode("utf-8"))},
        )
    )


@mcp.tool()
def dbx_dbfs_get(path: str) -> str:
    """Read a DBFS file (``w.dbfs.read``; up to ~1MB, base64-decoded to text)."""

    def op(w):
        res = w.dbfs.read(path, length=_MAX_READ)
        data = getattr(res, "data", None)
        out = {"path": path, "bytes_read": getattr(res, "bytes_read", None)}
        if data:
            raw = base64.b64decode(data)
            try:
                out["text"] = raw.decode("utf-8")
            except UnicodeDecodeError:
                out["base64"] = data
        return out

    return _run(op)


@mcp.tool()
def dbx_dbfs_mkdirs(path: str) -> str:
    """Recursively create a DBFS directory (``w.dbfs.mkdirs``)."""
    return _run(lambda w: _ack(w.dbfs.mkdirs(path), {"created_dir": path}))


@mcp.tool()
def dbx_dbfs_delete(path: str, recursive: bool = False, confirm: bool = False) -> str:
    """Delete a DBFS file or directory (``w.dbfs.delete``; ``recursive`` for dirs).

    Guardrail: pass ``confirm=True`` to actually delete. Irreversible -- with
    ``recursive=True`` this wipes an entire DBFS subtree.
    """
    dry = _guard("delete DBFS path", path, confirm)
    if dry:
        return dry
    return _run(
        lambda w: _ack(
            w.dbfs.delete(path, recursive=recursive),
            {"deleted": path, "recursive": recursive},
        )
    )


@mcp.tool()
def dbx_dbfs_move(source_path: str, destination_path: str) -> str:
    """Move/rename within DBFS (``w.dbfs.move``)."""
    return _run(
        lambda w: _ack(
            w.dbfs.move(source_path, destination_path),
            {"moved": source_path, "to": destination_path},
        )
    )


@mcp.tool()
def dbx_volume_upload(volume_path: str, contents: str, overwrite: bool = True) -> str:
    """Upload UTF-8 text to a Unity Catalog Volume file (``w.files.upload``).

    ``volume_path`` looks like ``/Volumes/<catalog>/<schema>/<volume>/file.txt``.
    """
    data = contents.encode("utf-8")
    return _run(
        lambda w: _ack(
            w.files.upload(volume_path, io.BytesIO(data), overwrite=overwrite),
            {"path": volume_path, "bytes_written": len(data)},
        )
    )


@mcp.tool()
def dbx_volume_download(volume_path: str) -> str:
    """Download a Volume file (``w.files.download``; utf-8 text or base64, capped)."""

    def op(w):
        resp = w.files.download(volume_path)
        stream = getattr(resp, "contents", resp)
        return {"path": volume_path, **_read_stream(stream)}

    return _run(op)


@mcp.tool()
def dbx_volume_ls(directory_path: str) -> str:
    """List a Volume directory (``w.files.list_directory_contents``)."""
    return _run(lambda w: _collect(w.files.list_directory_contents(directory_path)))


@mcp.tool()
def dbx_volume_mkdir(directory_path: str) -> str:
    """Create a Volume directory (``w.files.create_directory``)."""
    return _run(
        lambda w: _ack(
            w.files.create_directory(directory_path), {"created_dir": directory_path}
        )
    )


@mcp.tool()
def dbx_volume_rm(path: str, is_directory: bool = False, confirm: bool = False) -> str:
    """Delete a Volume file, or a directory when ``is_directory`` (``w.files.delete*``).

    Guardrail: pass ``confirm=True`` to actually delete. Irreversible.
    """
    dry = _guard("delete Volume path", path, confirm)
    if dry:
        return dry

    def op(w):
        if is_directory:
            w.files.delete_directory(path)
        else:
            w.files.delete(path)
        return {"deleted": path, "is_directory": is_directory}

    return _run(op)


# --------------------------------------------------------------------------- #
# SQL Warehouses + statement execution
# --------------------------------------------------------------------------- #
@mcp.tool()
def dbx_warehouse_list() -> str:
    """List SQL warehouses (``w.warehouses.list``)."""
    return _run(lambda w: _collect(w.warehouses.list()))


@mcp.tool()
def dbx_warehouse_get(warehouse_id: str) -> str:
    """Get one SQL warehouse's details/state (``w.warehouses.get``)."""
    return _run(lambda w: _dump(w.warehouses.get(warehouse_id)))


@mcp.tool()
def dbx_warehouse_create(
    name: str,
    cluster_size: str = "2X-Small",
    warehouse_type: str = "PRO",
    auto_stop_mins: int = 10,
    min_num_clusters: int = 1,
    max_num_clusters: int = 1,
    enable_serverless_compute: bool = False,
    wait: bool = False,
) -> str:
    """Create a SQL warehouse (``w.warehouses.create``). $$$ bills while running.

    ``cluster_size`` is a T-shirt size ('2X-Small'..'4X-Large'); ``warehouse_type``
    is PRO|CLASSIC. ``auto_stop_mins`` idles it off. ``wait=True`` blocks until
    RUNNING.
    """

    def op(w):
        from databricks.sdk.service import sql  # noqa: PLC0415

        kwargs = {
            "name": name,
            "cluster_size": cluster_size,
            "warehouse_type": _to_enum(
                sql.CreateWarehouseRequestWarehouseType, warehouse_type.upper()
            ),
            "auto_stop_mins": auto_stop_mins,
            "min_num_clusters": min_num_clusters,
            "max_num_clusters": max_num_clusters,
            "enable_serverless_compute": enable_serverless_compute,
        }
        if wait:
            return _dump(w.warehouses.create_and_wait(**kwargs))
        res = w.warehouses.create(**kwargs)
        return {"warehouse_id": getattr(res, "id", None), "waited": False}

    return _run(op)


@mcp.tool()
def dbx_warehouse_edit(
    warehouse_id: str,
    name: str = "",
    cluster_size: str = "",
    auto_stop_mins: int = 0,
    min_num_clusters: int = 0,
    max_num_clusters: int = 0,
) -> str:
    """Edit a SQL warehouse's config (``w.warehouses.edit``); only set fields change."""

    def op(w):
        kwargs: dict = {}
        if name:
            kwargs["name"] = name
        if cluster_size:
            kwargs["cluster_size"] = cluster_size
        if auto_stop_mins:
            kwargs["auto_stop_mins"] = auto_stop_mins
        if min_num_clusters:
            kwargs["min_num_clusters"] = min_num_clusters
        if max_num_clusters:
            kwargs["max_num_clusters"] = max_num_clusters
        _ack(w.warehouses.edit(warehouse_id, **kwargs), {})
        return {"warehouse_id": warehouse_id, "edited": True}

    return _run(op)


@mcp.tool()
def dbx_warehouse_delete(warehouse_id: str, confirm: bool = False) -> str:
    """Delete a SQL warehouse (``w.warehouses.delete``).

    Guardrail: pass ``confirm=True``. Prefer ``dbx_warehouse_stop`` if you only
    want to pause billing.
    """
    dry = _guard("delete warehouse", warehouse_id, confirm)
    if dry:
        return dry
    return _run(
        lambda w: _ack(w.warehouses.delete(warehouse_id), {"deleted": warehouse_id})
    )


@mcp.tool()
def dbx_warehouse_start(warehouse_id: str, wait: bool = False) -> str:
    """Start a SQL warehouse (``w.warehouses.start``). $$$ bills once RUNNING."""
    if wait:
        return _run(lambda w: _dump(w.warehouses.start_and_wait(warehouse_id)))
    return _run(
        lambda w: _ack(
            w.warehouses.start(warehouse_id),
            {"warehouse_id": warehouse_id, "waited": False},
        )
    )


@mcp.tool()
def dbx_warehouse_stop(warehouse_id: str, wait: bool = False) -> str:
    """Stop a SQL warehouse to pause billing (``w.warehouses.stop``)."""
    if wait:
        return _run(lambda w: _dump(w.warehouses.stop_and_wait(warehouse_id)))
    return _run(
        lambda w: _ack(
            w.warehouses.stop(warehouse_id),
            {"warehouse_id": warehouse_id, "waited": False},
        )
    )


@mcp.tool()
def dbx_sql_exec(
    warehouse_id: str,
    statement: str,
    catalog: str = "",
    schema: str = "",
    wait_timeout: str = "30s",
    row_limit: int = 0,
) -> str:
    """Run a SQL statement on a warehouse and return the result inline.

    ``w.statement_execution.execute_statement``. Set ``catalog``/``schema`` to
    scope; ``wait_timeout`` is '5s'..'50s' (or '0s' to poll); ``row_limit`` caps
    returned rows. For long queries the response includes a ``statement_id`` to
    fetch later via ``dbx_api_raw GET /api/2.0/sql/statements/{id}``.
    """
    return _run(
        lambda w: _dump(
            w.statement_execution.execute_statement(
                statement=statement,
                warehouse_id=warehouse_id,
                catalog=catalog or None,
                schema=schema or None,
                wait_timeout=wait_timeout,
                row_limit=row_limit or None,
            )
        )
    )


# --------------------------------------------------------------------------- #
# Model Serving (nested config/scoring bodies use the raw REST path)
# --------------------------------------------------------------------------- #
@mcp.tool()
def dbx_serving_create(config_json: str) -> str:
    """Create a model serving endpoint (``POST /serving-endpoints``). $$$ bills.

    ``config_json`` is the full create body, e.g. ``{"name": "...", "config":
    {"served_entities": [{"entity_name": "cat.sch.model", "entity_version": "1",
    "workload_size": "Small", "scale_to_zero_enabled": true}]}}``.
    """
    return _run(lambda w: _raw(w, "POST", "/api/2.0/serving-endpoints", config_json))


@mcp.tool()
def dbx_serving_update_config(name: str, config_json: str) -> str:
    """Update a serving endpoint's served entities/traffic (``PUT .../config``).

    ``config_json`` is the config body (``served_entities``/``traffic_config``).
    """
    return _run(
        lambda w: _raw(
            w, "PUT", f"/api/2.0/serving-endpoints/{name}/config", config_json
        )
    )


@mcp.tool()
def dbx_serving_get(name: str) -> str:
    """Get a serving endpoint's state + config (``w.serving_endpoints.get``)."""
    return _run(lambda w: _dump(w.serving_endpoints.get(name)))


@mcp.tool()
def dbx_serving_list() -> str:
    """List model serving endpoints (``w.serving_endpoints.list``)."""
    return _run(lambda w: _collect(w.serving_endpoints.list()))


@mcp.tool()
def dbx_serving_delete(name: str, confirm: bool = False) -> str:
    """Delete a serving endpoint (``w.serving_endpoints.delete``).

    Guardrail: pass ``confirm=True`` to actually delete.
    """
    dry = _guard("delete serving endpoint", name, confirm)
    if dry:
        return dry
    return _run(
        lambda w: _ack(w.serving_endpoints.delete(name), {"deleted_endpoint": name})
    )


@mcp.tool()
def dbx_serving_query(name: str, inputs_json: str) -> str:
    """Query (score) a serving endpoint (``POST .../invocations``). $$$ per call.

    ``inputs_json`` matches the endpoint's signature, e.g. ``{"inputs": [[...]]}``,
    ``{"dataframe_records": [{...}]}``, or ``{"messages": [{"role": "user",
    "content": "hi"}]}`` for a chat/LLM endpoint.
    """
    return _run(
        lambda w: _raw(w, "POST", f"/serving-endpoints/{name}/invocations", inputs_json)
    )


# --------------------------------------------------------------------------- #
# Secrets + Repos
# --------------------------------------------------------------------------- #
@mcp.tool()
def dbx_secret_scope_create(scope: str, initial_manage_principal: str = "") -> str:
    """Create a secret scope (``w.secrets.create_scope``).

    ``initial_manage_principal='users'`` grants all workspace users MANAGE.
    """
    return _run(
        lambda w: _ack(
            w.secrets.create_scope(
                scope, initial_manage_principal=initial_manage_principal or None
            ),
            {"created_scope": scope},
        )
    )


@mcp.tool()
def dbx_secret_scope_list() -> str:
    """List secret scopes (``w.secrets.list_scopes``)."""
    return _run(lambda w: _collect(w.secrets.list_scopes()))


@mcp.tool()
def dbx_secret_scope_delete(scope: str, confirm: bool = False) -> str:
    """Delete a secret scope and all its secrets (``w.secrets.delete_scope``).

    Guardrail: pass ``confirm=True`` to actually delete. Irreversible -- removes
    the scope and every secret in it.
    """
    dry = _guard("delete secret scope", scope, confirm)
    if dry:
        return dry
    return _run(lambda w: _ack(w.secrets.delete_scope(scope), {"deleted_scope": scope}))


@mcp.tool()
def dbx_secret_put(scope: str, key: str, string_value: str) -> str:
    """Put a string secret into a scope (``w.secrets.put_secret``).

    The value is write-only via the API; it is never echoed back by this tool.
    """
    return _run(
        lambda w: _ack(
            w.secrets.put_secret(scope, key, string_value=string_value),
            {"scope": scope, "key": key, "stored": True},
        )
    )


@mcp.tool()
def dbx_secret_get(scope: str, key: str) -> str:
    """Read a secret's value from a scope (``w.secrets.get_secret``).

    Returns the value decoded to utf-8 text when possible, else base64. Only
    works for Databricks-backed scopes the caller can read.
    """

    def op(w):
        res = w.secrets.get_secret(scope, key)
        out = {"scope": scope, "key": key}
        value = getattr(res, "value", None)
        if value:
            try:
                out["value"] = base64.b64decode(value).decode("utf-8")
            except (ValueError, UnicodeDecodeError):
                out["value_base64"] = value
        return out

    return _run(op)


@mcp.tool()
def dbx_repo_create(url: str, provider: str, path: str = "", branch: str = "") -> str:
    """Clone a Git repo into the workspace (``w.repos.create``).

    ``provider`` is gitHub|gitLab|bitbucketCloud|azureDevOpsServices|... ; ``path``
    is the workspace Repos path (e.g. ``/Repos/me/proj``). Needs a configured Git
    credential for private repos.
    """

    def op(w):
        kwargs: dict = {}
        if path:
            kwargs["path"] = path
        res = w.repos.create(url=url, provider=provider, **kwargs)
        repo_id = getattr(res, "id", None)
        if branch and repo_id is not None:
            with contextlib.suppress(Exception):
                w.repos.update(repo_id, branch=branch)
        return _dump(res)

    return _run(op)


@mcp.tool()
def dbx_repo_get(repo_id: int) -> str:
    """Get a workspace Repo's state (``w.repos.get``)."""
    return _run(lambda w: _dump(w.repos.get(repo_id)))


@mcp.tool()
def dbx_repo_list(path_prefix: str = "") -> str:
    """List workspace Repos (``w.repos.list``), optionally under ``path_prefix``."""
    return _run(lambda w: _collect(w.repos.list(path_prefix=path_prefix or None)))


@mcp.tool()
def dbx_repo_update(repo_id: int, branch: str = "", tag: str = "") -> str:
    """Check out a branch or tag in a Repo (``w.repos.update``)."""
    return _run(
        lambda w: _ack(
            w.repos.update(repo_id, branch=branch or None, tag=tag or None),
            {"repo_id": repo_id, "branch": branch or None, "tag": tag or None},
        )
    )


@mcp.tool()
def dbx_repo_delete(repo_id: int, confirm: bool = False) -> str:
    """Delete a workspace Repo (``w.repos.delete``).

    Guardrail: pass ``confirm=True`` to actually delete.
    """
    dry = _guard("delete workspace repo", str(repo_id), confirm)
    if dry:
        return dry
    return _run(lambda w: _ack(w.repos.delete(repo_id), {"deleted_repo": repo_id}))


# --------------------------------------------------------------------------- #
# Identity + raw escape hatch
# --------------------------------------------------------------------------- #
@mcp.tool()
def dbx_current_user() -> str:
    """Show the authenticated identity (``w.current_user.me``).

    Use to confirm which service principal / user the current credentials map to.
    """
    return _run(lambda w: _dump(w.current_user.me()))


@mcp.tool()
def dbx_api_raw(
    method: str, path: str, body_json: str = "", query_json: str = ""
) -> str:
    """Call ANY Databricks REST endpoint (``w.api_client.do``) -- the escape hatch.

    ``method`` GET|POST|PUT|PATCH|DELETE; ``path`` e.g. ``/api/2.1/clusters/list``;
    ``body_json``/``query_json`` are optional JSON strings. Use for endpoints
    without a purpose-built tool (Unity Catalog, pipelines, model registry, ...).
    """
    return _run(lambda w: _dump(_raw(w, method, path, body_json, query_json)))


if __name__ == "__main__":
    mcp.run()
