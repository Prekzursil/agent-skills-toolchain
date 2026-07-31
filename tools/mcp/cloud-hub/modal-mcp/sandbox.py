#!/usr/bin/env python3
"""Modal **SDK** tools for the Modal MCP wrapper: Sandboxes + Functions.

These wrap the ``modal`` Python SDK (not the CLI) because container engagement
-- create a container, exec in it, stream output, read/write files, snapshot it
-- has no CLI surface. Signatures target ``modal`` 1.x
(``Sandbox.create``/``exec``/``open``/``ls``/``mkdir``/``rm``/``terminate``/
``poll``/``wait``/``snapshot_filesystem``/``from_id``/``list``/``set_tags``,
``Function.from_name``, ``FunctionCall.from_id``).

The server is STATELESS across calls: every tool takes a ``sandbox_id`` (or
``function_call_id``) and reattaches via ``from_id`` -- nothing is cached in
process, so a sandbox created in one call is usable from any later call.

Rotation: every tool takes an optional ``account`` (profile). When set, a fresh
``modal.Client.from_credentials(...)`` is built for THAT call and threaded via
``client=`` (see ``_modal_common.sdk_ctx``); no global profile is mutated.

Cost: creating a sandbox with a ``gpu`` (or calling a GPU function) is BILLABLE
per second until it stops -- always ``modal_sandbox_terminate`` when done.
"""

from __future__ import annotations

import base64
import functools
import json
import os

import anyio.to_thread

import _modal_common as _c

_MAX = 8000  # cap captured file/stdout payloads in a JSON reply


def _sandbox(modal, sandbox_id: str, client):
    """Reattach to a live sandbox by id (the stateless-server primitive)."""
    return modal.Sandbox.from_id(sandbox_id, client=client)


def _result_payload(value) -> dict:
    """JSON-embed a function result if serializable, else its ``repr``."""
    try:
        json.dumps(value, ensure_ascii=False)
        return {"result": value}
    except (TypeError, ValueError):
        return {"result_repr": repr(value)[:_MAX]}


# --------------------------------------------------------------------------- #
# TIER-1: Sandboxes (container engagement).                                    #
# --------------------------------------------------------------------------- #
def modal_sandbox_create(
    app_name: str = "mcp-sandbox",
    image: str = "",
    command: list[str] | None = None,
    gpu: str = "",
    cpu: float = 0.0,
    memory: int = 0,
    timeout: int = 300,
    workdir: str = "",
    volumes: dict[str, str] | None = None,
    cloud_bucket_mounts: list[dict] | None = None,
    secrets: list[str] | None = None,
    env: dict[str, str] | None = None,
    tags: dict[str, str] | None = None,
    region: str = "",
    block_network: bool = False,
    environment: str = "",
    account: str = "",
) -> str:
    """Create a Modal Sandbox (a live container) and return its ``sandbox_id``.

    ``image`` is a registry tag (default ``debian_slim``); ``command`` runs an
    entrypoint (omit for an idle box you ``exec`` into until ``timeout``).
    ``volumes`` maps ``mount_path -> volume_name`` (created if missing);
    ``cloud_bucket_mounts`` takes entries from ``modal_cloud_bucket_mount_config``
    to mount an S3/GCS/R2 bucket. **A ``gpu`` (e.g. ``"a100"``, ``"h100"``,
    ``"t4"``, ``"a100:2"``) is BILLABLE per second** until terminated.
    ``account`` selects a per-call credential profile.
    """
    modal, err = _c.load_sdk()
    if err:
        return _c.fail(err)
    try:
        with _c.quiet():
            client, env_name = _c.sdk_ctx(modal, account, environment)
            app = modal.App.lookup(
                app_name,
                client=client,
                environment_name=env_name,
                create_if_missing=True,
            )
            img = (
                modal.Image.from_registry(image) if image else modal.Image.debian_slim()
            )
            vols: dict[str, object] = {}
            for mount_path, vol_name in (volumes or {}).items():
                vols[mount_path] = modal.Volume.from_name(
                    vol_name,
                    environment_name=env_name,
                    create_if_missing=True,
                    client=client,
                )
            for cfg in cloud_bucket_mounts or []:
                secret_name = cfg.get("secret") or ""
                vols[cfg["mount_path"]] = modal.CloudBucketMount(
                    bucket_name=cfg["bucket_name"],
                    bucket_endpoint_url=cfg.get("bucket_endpoint_url") or None,
                    key_prefix=cfg.get("key_prefix") or None,
                    read_only=bool(cfg.get("read_only", False)),
                    requester_pays=bool(cfg.get("requester_pays", False)),
                    secret=(
                        modal.Secret.from_name(secret_name, client=client)
                        if secret_name
                        else None
                    ),
                )
            secret_objs = [
                modal.Secret.from_name(name, environment_name=env_name, client=client)
                for name in secrets or []
            ]
            kwargs: dict[str, object] = {
                "app": app,
                "image": img,
                "timeout": timeout,
                "client": client,
                "environment_name": env_name,
            }
            if workdir:
                kwargs["workdir"] = workdir
            if gpu:
                kwargs["gpu"] = gpu
            if cpu:
                kwargs["cpu"] = cpu
            if memory:
                kwargs["memory"] = memory
            if region:
                kwargs["region"] = region
            if block_network:
                kwargs["block_network"] = True
            if vols:
                kwargs["volumes"] = vols
            if secret_objs:
                kwargs["secrets"] = secret_objs
            if env:
                kwargs["env"] = env
            if tags:
                kwargs["tags"] = tags
            sandbox = modal.Sandbox.create(*(command or ()), **kwargs)
            sandbox_id = sandbox.object_id
        return _c.ok(sandbox_id=sandbox_id, app=app_name, gpu=gpu or None)
    except Exception as exc:  # noqa: BLE001
        return _c.fail(f"sandbox_create failed: {exc}")


def modal_sandbox_exec(
    sandbox_id: str,
    command: str,
    workdir: str = "",
    timeout: int = 0,
    account: str = "",
) -> str:
    """Run a shell ``command`` (via ``sh -c``) inside a sandbox; capture output.

    Returns ``{returncode, stdout, stderr}``. Use ``modal_sandbox_exec_stream``
    for line-buffered output of a long command.
    """
    modal, err = _c.load_sdk()
    if err:
        return _c.fail(err)
    try:
        with _c.quiet():
            client, _env = _c.sdk_ctx(modal, account)
            sandbox = _sandbox(modal, sandbox_id, client)
            proc = sandbox.exec(
                "sh",
                "-c",
                command,
                workdir=workdir or None,
                timeout=timeout or None,
            )
            stdout = proc.stdout.read()
            stderr = proc.stderr.read()
            returncode = proc.wait()
        return _c.dumps(
            {
                "ok": returncode == 0,
                "returncode": returncode,
                "stdout": (stdout or "")[:_MAX],
                "stderr": (stderr or "")[:2000],
            }
        )
    except Exception as exc:  # noqa: BLE001
        return _c.fail(f"sandbox_exec failed: {exc}")


def modal_sandbox_exec_stream(
    sandbox_id: str,
    command: str,
    workdir: str = "",
    timeout: int = 0,
    max_lines: int = 200,
    account: str = "",
) -> str:
    """Run ``command`` and collect up to ``max_lines`` of streamed stdout lines.

    True token-streaming is impossible over a single MCP request/response; this
    reads the process's stdout stream line-by-line and returns the collected
    window plus the exit code (``truncated`` if ``max_lines`` was hit).
    """
    modal, err = _c.load_sdk()
    if err:
        return _c.fail(err)
    try:
        with _c.quiet():
            client, _env = _c.sdk_ctx(modal, account)
            sandbox = _sandbox(modal, sandbox_id, client)
            proc = sandbox.exec(
                "sh",
                "-c",
                command,
                workdir=workdir or None,
                timeout=timeout or None,
            )
            lines: list[str] = []
            truncated = False
            for line in proc.stdout:
                lines.append(line.rstrip("\n"))
                if len(lines) >= max_lines:
                    truncated = True
                    break
            returncode = proc.wait()
        return _c.dumps(
            {
                "ok": returncode == 0,
                "returncode": returncode,
                "lines": lines,
                "truncated": truncated,
            }
        )
    except Exception as exc:  # noqa: BLE001
        return _c.fail(f"sandbox_exec_stream failed: {exc}")


def modal_sandbox_write_file(
    sandbox_id: str, path: str, content: str, account: str = ""
) -> str:
    """Write UTF-8 text ``content`` to ``path`` inside the sandbox filesystem."""
    modal, err = _c.load_sdk()
    if err:
        return _c.fail(err)
    try:
        with _c.quiet():
            client, _env = _c.sdk_ctx(modal, account)
            sandbox = _sandbox(modal, sandbox_id, client)
            handle = sandbox.open(path, "w")
            try:
                handle.write(content)
            finally:
                handle.close()
        return _c.ok(path=path, bytes=len(content.encode("utf-8")))
    except Exception as exc:  # noqa: BLE001
        return _c.fail(f"sandbox_write_file failed: {exc}")


def modal_sandbox_read_file(
    sandbox_id: str, path: str, binary: bool = False, account: str = ""
) -> str:
    """Read ``path`` from the sandbox (UTF-8 text, or base64 when ``binary``)."""
    modal, err = _c.load_sdk()
    if err:
        return _c.fail(err)
    try:
        with _c.quiet():
            client, _env = _c.sdk_ctx(modal, account)
            sandbox = _sandbox(modal, sandbox_id, client)
            handle = sandbox.open(path, "rb" if binary else "r")
            try:
                data = handle.read()
            finally:
                handle.close()
        if binary:
            encoded = base64.b64encode(data).decode("ascii")
            return _c.ok(
                path=path, base64=encoded[:_MAX], truncated=len(encoded) > _MAX
            )
        return _c.ok(path=path, content=data[:_MAX], truncated=len(data) > _MAX)
    except Exception as exc:  # noqa: BLE001
        return _c.fail(f"sandbox_read_file failed: {exc}")


def modal_sandbox_upload(
    sandbox_id: str, local_path: str, remote_path: str, account: str = ""
) -> str:
    """Upload a LOCAL file to ``remote_path`` inside the sandbox."""
    modal, err = _c.load_sdk()
    if err:
        return _c.fail(err)
    if not os.path.isfile(local_path):
        return _c.fail(f"local file not found: {local_path!r}")
    try:
        with open(local_path, "rb") as fh:
            data = fh.read()
        with _c.quiet():
            client, _env = _c.sdk_ctx(modal, account)
            sandbox = _sandbox(modal, sandbox_id, client)
            handle = sandbox.open(remote_path, "wb")
            try:
                handle.write(data)
            finally:
                handle.close()
        return _c.ok(remote_path=remote_path, bytes=len(data))
    except Exception as exc:  # noqa: BLE001
        return _c.fail(f"sandbox_upload failed: {exc}")


def modal_sandbox_download(
    sandbox_id: str, remote_path: str, local_path: str, account: str = ""
) -> str:
    """Download ``remote_path`` from the sandbox to a LOCAL file."""
    modal, err = _c.load_sdk()
    if err:
        return _c.fail(err)
    try:
        with _c.quiet():
            client, _env = _c.sdk_ctx(modal, account)
            sandbox = _sandbox(modal, sandbox_id, client)
            handle = sandbox.open(remote_path, "rb")
            try:
                data = handle.read()
            finally:
                handle.close()
        parent = os.path.dirname(local_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(local_path, "wb") as fh:
            fh.write(data)
        return _c.ok(local_path=local_path, bytes=len(data))
    except Exception as exc:  # noqa: BLE001
        return _c.fail(f"sandbox_download failed: {exc}")


def modal_sandbox_ls(sandbox_id: str, path: str = "/", account: str = "") -> str:
    """List directory entries at ``path`` inside the sandbox."""
    modal, err = _c.load_sdk()
    if err:
        return _c.fail(err)
    try:
        with _c.quiet():
            client, _env = _c.sdk_ctx(modal, account)
            entries = _sandbox(modal, sandbox_id, client).ls(path)
        return _c.ok(path=path, entries=list(entries))
    except Exception as exc:  # noqa: BLE001
        return _c.fail(f"sandbox_ls failed: {exc}")


def modal_sandbox_mkdir(
    sandbox_id: str, path: str, parents: bool = True, account: str = ""
) -> str:
    """Create directory ``path`` inside the sandbox (``parents`` = ``mkdir -p``)."""
    modal, err = _c.load_sdk()
    if err:
        return _c.fail(err)
    try:
        with _c.quiet():
            client, _env = _c.sdk_ctx(modal, account)
            _sandbox(modal, sandbox_id, client).mkdir(path, parents=parents)
        return _c.ok(path=path)
    except Exception as exc:  # noqa: BLE001
        return _c.fail(f"sandbox_mkdir failed: {exc}")


def modal_sandbox_rm(
    sandbox_id: str, path: str, recursive: bool = False, account: str = ""
) -> str:
    """Remove ``path`` inside the sandbox (``recursive`` for a directory tree)."""
    modal, err = _c.load_sdk()
    if err:
        return _c.fail(err)
    try:
        with _c.quiet():
            client, _env = _c.sdk_ctx(modal, account)
            _sandbox(modal, sandbox_id, client).rm(path, recursive=recursive)
        return _c.ok(path=path, recursive=recursive)
    except Exception as exc:  # noqa: BLE001
        return _c.fail(f"sandbox_rm failed: {exc}")


def modal_sandbox_stat(sandbox_id: str, path: str, account: str = "") -> str:
    """Stat ``path`` inside the sandbox (runs ``stat`` -- needs coreutils)."""
    modal, err = _c.load_sdk()
    if err:
        return _c.fail(err)
    try:
        with _c.quiet():
            client, _env = _c.sdk_ctx(modal, account)
            sandbox = _sandbox(modal, sandbox_id, client)
            proc = sandbox.exec("stat", path)
            stdout = proc.stdout.read()
            stderr = proc.stderr.read()
            returncode = proc.wait()
        if returncode != 0:
            return _c.fail(
                f"stat exited {returncode}",
                stderr=(stderr or "")[:2000],
                path=path,
            )
        return _c.ok(path=path, stat=(stdout or "")[:2000])
    except Exception as exc:  # noqa: BLE001
        return _c.fail(f"sandbox_stat failed: {exc}")


def modal_sandbox_list(
    sandbox_id: str = "",
    app_name: str = "",
    tags: dict[str, str] | None = None,
    account: str = "",
) -> str:
    """List running sandboxes, optionally filtered by ``app_name`` / ``tags``.

    (``sandbox_id`` is accepted but ignored -- listing is by app/tags; use
    ``modal_sandbox_from_id`` to inspect one sandbox.)
    """
    modal, err = _c.load_sdk()
    if err:
        return _c.fail(err)
    try:
        with _c.quiet():
            client, env_name = _c.sdk_ctx(modal, account)
            app_id = None
            if app_name:
                app_id = modal.App.lookup(
                    app_name, client=client, environment_name=env_name
                ).app_id
            items = []
            for sandbox in modal.Sandbox.list(
                app_id=app_id, tags=tags or None, client=client
            ):
                items.append(sandbox.object_id)
                if len(items) >= 100:
                    break
        return _c.ok(sandboxes=items, count=len(items))
    except Exception as exc:  # noqa: BLE001
        return _c.fail(f"sandbox_list failed: {exc}")


def modal_sandbox_from_id(sandbox_id: str, account: str = "") -> str:
    """Reattach to a sandbox by id and report its liveness + tags."""
    modal, err = _c.load_sdk()
    if err:
        return _c.fail(err)
    try:
        with _c.quiet():
            client, _env = _c.sdk_ctx(modal, account)
            sandbox = _sandbox(modal, sandbox_id, client)
            returncode = sandbox.poll()
            tags = sandbox.get_tags()
        return _c.ok(
            sandbox_id=sandbox_id,
            running=returncode is None,
            returncode=returncode,
            tags=tags,
        )
    except Exception as exc:  # noqa: BLE001
        return _c.fail(f"sandbox_from_id failed: {exc}")


def modal_sandbox_poll(sandbox_id: str, account: str = "") -> str:
    """Poll a sandbox: returncode if exited, else ``running`` (non-blocking)."""
    modal, err = _c.load_sdk()
    if err:
        return _c.fail(err)
    try:
        with _c.quiet():
            client, _env = _c.sdk_ctx(modal, account)
            returncode = _sandbox(modal, sandbox_id, client).poll()
        return _c.ok(
            sandbox_id=sandbox_id, running=returncode is None, returncode=returncode
        )
    except Exception as exc:  # noqa: BLE001
        return _c.fail(f"sandbox_poll failed: {exc}")


def modal_sandbox_wait(sandbox_id: str, account: str = "") -> str:
    """Block until the sandbox's entrypoint exits, then return its returncode."""
    modal, err = _c.load_sdk()
    if err:
        return _c.fail(err)
    try:
        with _c.quiet():
            client, _env = _c.sdk_ctx(modal, account)
            sandbox = _sandbox(modal, sandbox_id, client)
            sandbox.wait(raise_on_termination=False)
            returncode = sandbox.poll()
        return _c.ok(sandbox_id=sandbox_id, returncode=returncode)
    except Exception as exc:  # noqa: BLE001
        return _c.fail(f"sandbox_wait failed: {exc}")


def modal_sandbox_terminate(
    sandbox_id: str,
    confirm: bool = False,
    dry_run: bool = False,
    account: str = "",
) -> str:
    """Terminate a sandbox (stops billing). Gated behind ``confirm``/``dry_run``."""
    blocked = _c.guard_destructive("terminate sandbox", sandbox_id, confirm, dry_run)
    if blocked is not None:
        return blocked
    modal, err = _c.load_sdk()
    if err:
        return _c.fail(err)
    try:
        with _c.quiet():
            client, _env = _c.sdk_ctx(modal, account)
            _sandbox(modal, sandbox_id, client).terminate()
        return _c.ok(sandbox_id=sandbox_id, terminated=True)
    except Exception as exc:  # noqa: BLE001
        return _c.fail(f"sandbox_terminate failed: {exc}")


def modal_sandbox_tags(
    sandbox_id: str, tags: dict[str, str] | None = None, account: str = ""
) -> str:
    """Get the sandbox's tags, or SET them when ``tags`` is provided.

    Tags let a stateless server find sandboxes later (``modal_sandbox_list``).
    """
    modal, err = _c.load_sdk()
    if err:
        return _c.fail(err)
    try:
        with _c.quiet():
            client, _env = _c.sdk_ctx(modal, account)
            sandbox = _sandbox(modal, sandbox_id, client)
            if tags:
                sandbox.set_tags(tags, client=client)
            current = sandbox.get_tags()
        return _c.ok(sandbox_id=sandbox_id, tags=current, updated=bool(tags))
    except Exception as exc:  # noqa: BLE001
        return _c.fail(f"sandbox_tags failed: {exc}")


def modal_sandbox_snapshot(sandbox_id: str, account: str = "") -> str:
    """Snapshot the sandbox filesystem to a reusable Image; return its image id.

    Use to bake a post-install image (e.g. after a Schrodinger Suite install) so
    later sandboxes skip the install: pass the id as ``image`` to a create call.
    """
    modal, err = _c.load_sdk()
    if err:
        return _c.fail(err)
    try:
        with _c.quiet():
            client, _env = _c.sdk_ctx(modal, account)
            image = _sandbox(modal, sandbox_id, client).snapshot_filesystem()
            image_id = image.object_id
        return _c.ok(sandbox_id=sandbox_id, image_id=image_id)
    except Exception as exc:  # noqa: BLE001
        return _c.fail(f"sandbox_snapshot failed: {exc}")


# --------------------------------------------------------------------------- #
# TIER-2: Function / FunctionCall (SDK).                                       #
# --------------------------------------------------------------------------- #
def modal_function_call(
    app_name: str,
    function_name: str,
    args: list | None = None,
    kwargs: dict | None = None,
    environment: str = "",
    account: str = "",
) -> str:
    """Call a deployed Modal Function synchronously (``.remote``) and return it.

    **May start billable (GPU) compute.** Use ``modal_function_spawn`` +
    ``modal_functioncall_get`` for long jobs you do not want to block on.
    """
    modal, err = _c.load_sdk()
    if err:
        return _c.fail(err)
    try:
        with _c.quiet():
            client, env_name = _c.sdk_ctx(modal, account, environment)
            fn = modal.Function.from_name(
                app_name, function_name, environment_name=env_name, client=client
            )
            value = fn.remote(*(args or []), **(kwargs or {}))
        return _c.dumps({"ok": True, **_result_payload(value)})
    except Exception as exc:  # noqa: BLE001
        return _c.fail(f"function_call failed: {exc}")


def modal_function_spawn(
    app_name: str,
    function_name: str,
    args: list | None = None,
    kwargs: dict | None = None,
    environment: str = "",
    account: str = "",
) -> str:
    """Spawn a deployed Function async (``.spawn``); return a function_call_id.

    Poll/collect the result later with ``modal_functioncall_get``. **May start
    billable compute.**
    """
    modal, err = _c.load_sdk()
    if err:
        return _c.fail(err)
    try:
        with _c.quiet():
            client, env_name = _c.sdk_ctx(modal, account, environment)
            fn = modal.Function.from_name(
                app_name, function_name, environment_name=env_name, client=client
            )
            call = fn.spawn(*(args or []), **(kwargs or {}))
            call_id = call.object_id
        return _c.ok(function_call_id=call_id)
    except Exception as exc:  # noqa: BLE001
        return _c.fail(f"function_spawn failed: {exc}")


def modal_functioncall_get(
    function_call_id: str, timeout: int = 0, account: str = ""
) -> str:
    """Fetch a spawned call's result by id (``timeout=0`` blocks until ready)."""
    modal, err = _c.load_sdk()
    if err:
        return _c.fail(err)
    try:
        with _c.quiet():
            client, _env = _c.sdk_ctx(modal, account)
            call = modal.FunctionCall.from_id(function_call_id, client=client)
            value = call.get(timeout=timeout or None)
        return _c.dumps({"ok": True, **_result_payload(value)})
    except Exception as exc:  # noqa: BLE001
        return _c.fail(f"functioncall_get failed: {exc}")


# The SDK tools registered onto the shared FastMCP instance by ``server.py``.
SDK_TOOLS = (
    modal_sandbox_create,
    modal_sandbox_exec,
    modal_sandbox_exec_stream,
    modal_sandbox_write_file,
    modal_sandbox_read_file,
    modal_sandbox_upload,
    modal_sandbox_download,
    modal_sandbox_ls,
    modal_sandbox_mkdir,
    modal_sandbox_rm,
    modal_sandbox_stat,
    modal_sandbox_list,
    modal_sandbox_from_id,
    modal_sandbox_poll,
    modal_sandbox_wait,
    modal_sandbox_terminate,
    modal_sandbox_tags,
    modal_sandbox_snapshot,
    modal_function_call,
    modal_function_spawn,
    modal_functioncall_get,
)


def _offloaded(fn):
    """Wrap a blocking SDK tool as a coroutine that runs it on a worker thread.

    FastMCP invokes a SYNCHRONOUS handler inline on the server's event loop
    (``mcp`` 1.23.x ``utilities/func_metadata.py``: ``return fn(**arguments)``),
    so one blocking Modal call froze the whole child server. The concrete
    circularity: ``modal_sandbox_wait`` blocks in ``sandbox.wait()`` and
    ``modal_sandbox_terminate`` -- the very call that would make that wait return
    -- could not be dispatched until it did, leaving a billable sandbox live.

    ``functools.wraps`` keeps ``__name__``/``__doc__``/``__wrapped__``, so
    ``inspect.signature`` still reports the original parameters and the generated
    MCP tool schema is unchanged. The tools themselves stay plain synchronous
    functions (directly callable and unit-testable); only registration offloads.
    """

    @functools.wraps(fn)
    async def _async(*args, **kwargs):
        return await anyio.to_thread.run_sync(functools.partial(fn, *args, **kwargs))

    return _async


def register(mcp) -> None:
    """Register every SDK tool onto the server's FastMCP instance."""
    for fn in SDK_TOOLS:
        mcp.tool()(_offloaded(fn))
