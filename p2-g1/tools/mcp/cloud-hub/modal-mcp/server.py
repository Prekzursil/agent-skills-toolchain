#!/usr/bin/env python3
"""Modal MCP wrapper -- a FastMCP server over the ``modal`` CLI **and** SDK.

Tool names are PRE-NAMESPACED (``modal_*``) so the cloud-hub's collision-prefix
never has to fire for this backend. Two paths share one surface:

* **CLI path** (this file): thin wrappers over the ``modal`` CLI for apps,
  volumes, secrets, containers, logs, identity -- resolved and invoked lazily so
  ``tools/list`` enumerates with zero credentials.
* **SDK path** (``sandbox.py``): ``modal.Sandbox``/``Function`` tools for
  container engagement (create/exec/file-I/O/snapshot/terminate) that have no
  CLI, registered onto this same server via ``sandbox.register(mcp)``.

Shared helpers live in ``_modal_common`` (CLI runner, lazy SDK gate, per-call
credential rotation, stdio-purity guard, destructive-op gating, cost table).

Rotation is per-invocation: every tool takes an optional ``account`` (profile);
when set, that call uses that account's credentials WITHOUT mutating any shared
"active profile" (concurrency-safe). ``environment`` threads ``MODAL_ENVIRONMENT``
/ the CLI ``--env`` for Modal workspaces with named environments.

GPU cost awareness: ``modal_run``/``modal_deploy`` and any ``gpu=`` sandbox/
function start BILLABLE compute; destructive ops (``sandbox_terminate``,
``container_stop``, ``volume_rm``, ``volume_delete``) are gated behind
``confirm``/``dry_run``.
"""

from __future__ import annotations

import shlex

from mcp.server.fastmcp import FastMCP

import _modal_common as _c
import sandbox

mcp = FastMCP("modal")


def _modal(*args: str, profile: str = "", environment: str = "") -> dict:
    """Invoke the modal CLI (per-call rotation aware). Never raises.

    Retained as the backend's CLI helper; delegates to ``_modal_common.run_cli``
    so the CLI + SDK paths share one runner + rotation implementation.
    """
    return _c.run_cli(*args, profile=profile, environment=environment)


# --------------------------------------------------------------------------- #
# Apps / run / deploy (the original 6 tools, now rotation-aware).              #
# --------------------------------------------------------------------------- #
@mcp.tool()
def modal_app_list(account: str = "", environment: str = "") -> str:
    """List deployed/running Modal apps (``modal app list``)."""
    return _c.dumps(_modal("app", "list", profile=account, environment=environment))


@mcp.tool()
def modal_app_stop(app: str, account: str = "", environment: str = "") -> str:
    """Stop a running Modal app by id or name (``modal app stop``)."""
    return _c.dumps(
        _modal("app", "stop", app, profile=account, environment=environment)
    )


@mcp.tool()
def modal_run(
    target: str, detach: bool = False, account: str = "", environment: str = ""
) -> str:
    """Run a Modal entrypoint, e.g. ``app.py::main`` (``modal run``).

    May start billable compute. Set ``detach=True`` to return without streaming.
    """
    args = ["run"] + (["--detach"] if detach else []) + [target]
    return _c.dumps(_modal(*args, profile=account, environment=environment))


@mcp.tool()
def modal_deploy(
    target: str, name: str = "", account: str = "", environment: str = ""
) -> str:
    """Deploy a Modal app from a file/ref (``modal deploy``)."""
    args = ["deploy", target] + (["--name", name] if name else [])
    return _c.dumps(_modal(*args, profile=account, environment=environment))


@mcp.tool()
def modal_volume_ls(
    volume: str = "", path: str = "/", account: str = "", environment: str = ""
) -> str:
    """List Modal volumes, or files inside one volume (``modal volume list|ls``)."""
    if volume:
        return _c.dumps(
            _modal(
                "volume", "ls", volume, path, profile=account, environment=environment
            )
        )
    return _c.dumps(_modal("volume", "list", profile=account, environment=environment))


@mcp.tool()
def modal_secret_list(account: str = "", environment: str = "") -> str:
    """List Modal secret names (``modal secret list``)."""
    return _c.dumps(_modal("secret", "list", profile=account, environment=environment))


# --------------------------------------------------------------------------- #
# Containers (already-running) + app logs.                                     #
# --------------------------------------------------------------------------- #
@mcp.tool()
def modal_app_logs(
    app: str, timeout: int = 30, account: str = "", environment: str = ""
) -> str:
    """Fetch a bounded window of an App's streaming logs (``modal app logs``).

    ``modal app logs`` follows the stream; this captures up to ``timeout`` s then
    returns the window (``truncated`` if the stream was still open).
    """
    return _c.dumps(
        _c.run_cli_stream(
            "app",
            "logs",
            app,
            profile=account,
            environment=environment,
            timeout=timeout,
        )
    )


@mcp.tool()
def modal_container_list(account: str = "", environment: str = "") -> str:
    """List currently-running Modal containers (``modal container list``)."""
    return _c.dumps(
        _modal("container", "list", profile=account, environment=environment)
    )


@mcp.tool()
def modal_container_exec(
    container_id: str, command: str, account: str = "", environment: str = ""
) -> str:
    """Execute a command in a running container (``modal container exec``).

    ``command`` is split shell-style (``shlex``) into argv for the container.
    """
    argv = shlex.split(command, posix=True)
    return _c.dumps(
        _modal(
            "container",
            "exec",
            container_id,
            *argv,
            profile=account,
            environment=environment,
        )
    )


@mcp.tool()
def modal_container_logs(
    container_id: str, timeout: int = 30, account: str = "", environment: str = ""
) -> str:
    """Fetch a bounded window of a container's logs (``modal container logs``)."""
    return _c.dumps(
        _c.run_cli_stream(
            "container",
            "logs",
            container_id,
            profile=account,
            environment=environment,
            timeout=timeout,
        )
    )


@mcp.tool()
def modal_container_stop(
    container_id: str,
    confirm: bool = False,
    dry_run: bool = False,
    account: str = "",
    environment: str = "",
) -> str:
    """Terminate a running container (``modal container stop``). Gated.

    Destructive: gated behind ``confirm``/``dry_run``.
    """
    blocked = _c.guard_destructive("stop container", container_id, confirm, dry_run)
    if blocked is not None:
        return blocked
    return _c.dumps(
        _modal(
            "container", "stop", container_id, profile=account, environment=environment
        )
    )


# --------------------------------------------------------------------------- #
# Volumes (create / put / get / rm / delete).                                  #
# --------------------------------------------------------------------------- #
@mcp.tool()
def modal_volume_create(name: str, account: str = "", environment: str = "") -> str:
    """Create a named, persistent Modal Volume (``modal volume create``)."""
    return _c.dumps(
        _modal("volume", "create", name, profile=account, environment=environment)
    )


@mcp.tool()
def modal_volume_put(
    volume: str,
    local_path: str,
    remote_path: str = "/",
    force: bool = False,
    account: str = "",
    environment: str = "",
) -> str:
    """Upload a local file/dir into a Volume (``modal volume put``)."""
    args = ["volume", "put", volume, local_path, remote_path] + (
        ["--force"] if force else []
    )
    return _c.dumps(_modal(*args, profile=account, environment=environment))


@mcp.tool()
def modal_volume_get(
    volume: str,
    remote_path: str,
    local_path: str = ".",
    force: bool = False,
    account: str = "",
    environment: str = "",
) -> str:
    """Download a path from a Volume to local (``modal volume get``)."""
    args = ["volume", "get", volume, remote_path, local_path] + (
        ["--force"] if force else []
    )
    return _c.dumps(_modal(*args, profile=account, environment=environment))


@mcp.tool()
def modal_volume_rm(
    volume: str,
    remote_path: str,
    recursive: bool = False,
    confirm: bool = False,
    dry_run: bool = False,
    account: str = "",
    environment: str = "",
) -> str:
    """Delete a file/dir INSIDE a Volume (``modal volume rm``). Gated.

    Destructive: gated behind ``confirm``/``dry_run``.
    """
    blocked = _c.guard_destructive(
        "rm from volume", f"{volume}:{remote_path}", confirm, dry_run
    )
    if blocked is not None:
        return blocked
    args = ["volume", "rm", volume, remote_path] + (["-r"] if recursive else [])
    return _c.dumps(_modal(*args, profile=account, environment=environment))


@mcp.tool()
def modal_volume_delete(
    volume: str,
    confirm: bool = False,
    dry_run: bool = False,
    account: str = "",
    environment: str = "",
) -> str:
    """Delete an ENTIRE named Volume and all its data (``modal volume delete``).

    Destructive: gated behind ``confirm``/``dry_run``.
    """
    blocked = _c.guard_destructive("delete volume", volume, confirm, dry_run)
    if blocked is not None:
        return blocked
    return _c.dumps(
        _modal(
            "volume",
            "delete",
            volume,
            "--yes",
            profile=account,
            environment=environment,
        )
    )


# --------------------------------------------------------------------------- #
# Secrets (create) + identity.                                                 #
# --------------------------------------------------------------------------- #
@mcp.tool()
def modal_secret_create(
    name: str,
    entries: dict[str, str],
    force: bool = False,
    account: str = "",
    environment: str = "",
) -> str:
    """Create/overwrite a named Modal Secret from ``entries`` (``modal secret create``).

    Prefer ``${ENV}``-sourced values. NOTE: values are passed as CLI argv, so on
    a shared host they may be briefly visible in the process list; ``force`` (=
    ``--force``) overwrites an existing secret of the same name.
    """
    if not entries:
        return _c.fail("provide a non-empty 'entries' map of KEY -> VALUE")
    pairs = [f"{key}={value}" for key, value in entries.items()]
    args = ["secret", "create", name, *pairs] + (["--force"] if force else [])
    return _c.dumps(_modal(*args, profile=account, environment=environment))


@mcp.tool()
def modal_whoami(account: str = "", environment: str = "") -> str:
    """Show the Modal identity/workspace in use (``modal token info``)."""
    return _c.dumps(_modal("token", "info", profile=account, environment=environment))


# --------------------------------------------------------------------------- #
# Local helpers (no API call): cost estimate + CloudBucketMount config.        #
# --------------------------------------------------------------------------- #
@mcp.tool()
def modal_estimate_cost(
    seconds: float,
    gpu: str = "",
    gpu_count: int = 1,
    cpu_cores: float = 0.125,
    memory_gib: float = 0.0,
    tier: str = "sandbox",
) -> str:
    """Estimate Modal compute cost from GPU/CPU/memory-seconds (LOCAL calc).

    ``gpu`` is a type (e.g. ``"a100"``, ``"h100"``, ``"t4"``) optionally with a
    count (``"a100:2"``). ``tier`` is ``"sandbox"`` (Sandboxes/Notebooks) or
    ``"standard"`` (Functions) -- CPU/memory bill higher on the sandbox tier.
    Modal exposes NO public billing API, so this is an estimate from list price.
    """
    return _c.dumps(
        _c.estimate_cost(
            seconds,
            gpu=gpu,
            gpu_count=gpu_count,
            cpu_cores=cpu_cores,
            memory_gib=memory_gib,
            tier=tier,
        )
    )


@mcp.tool()
def modal_cloud_bucket_mount_config(
    bucket_name: str,
    mount_path: str,
    key_prefix: str = "",
    secret: str = "",
    read_only: bool = False,
    requester_pays: bool = False,
    bucket_endpoint_url: str = "",
) -> str:
    """Build a CloudBucketMount config entry (LOCAL; no API call).

    Pass the returned object inside ``cloud_bucket_mounts=[...]`` of
    ``modal_sandbox_create`` to mount an S3/GCS/R2 bucket. ``secret`` names a
    Modal Secret holding the bucket credentials; ``bucket_endpoint_url`` targets
    GCS/R2/MinIO. ``key_prefix`` (if set) must end with ``/``.
    """
    if key_prefix and not key_prefix.endswith("/"):
        return _c.fail("key_prefix must end with '/'")
    return _c.dumps(
        {
            "ok": True,
            "cloud_bucket_mount": {
                "mount_path": mount_path,
                "bucket_name": bucket_name,
                "key_prefix": key_prefix,
                "secret": secret,
                "read_only": read_only,
                "requester_pays": requester_pays,
                "bucket_endpoint_url": bucket_endpoint_url,
            },
            "usage": "pass this object inside cloud_bucket_mounts=[...] of "
            "modal_sandbox_create",
        }
    )


# Register the SDK Sandbox/Function tools onto this same FastMCP surface.
sandbox.register(mcp)


if __name__ == "__main__":
    mcp.run()
