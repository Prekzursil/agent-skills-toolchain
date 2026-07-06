#!/usr/bin/env python3
"""Lightning AI MCP wrapper -- a thin FastMCP server over ``lightning_sdk``.

Tool names are PRE-NAMESPACED (``lightning_*``) so the cloud-hub's
collision-prefix never has to fire for this backend. ``lightning_sdk`` is
imported lazily inside each tool, so ``tools/list`` enumerates even when the SDK
is not installed; a call then returns a clear install/auth hint instead of
crashing.

Auth: ``LIGHTNING_USER_ID`` + ``LIGHTNING_API_KEY`` (from the Lightning AI
account settings). GPU cost awareness: starting a Studio machine or submitting a
Job bills by the second -- confirm intent, and stop Studios/Jobs when done.
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("lightning")

# Representative Studio machine types (used as a fallback when the SDK is absent).
_KNOWN_MACHINES = [
    "CPU",
    "CPU_SMALL",
    "DATA_PREP",
    "T4",
    "T4_X_4",
    "L4",
    "L4_X_4",
    "A10G",
    "A10G_X_4",
    "L40S",
    "L40S_X_4",
    "A100_X_8",
    "H100_X_8",
]


def _sdk():
    """Import lightning_sdk lazily; return (module, error_message)."""
    try:
        import lightning_sdk  # noqa: PLC0415  (lazy on purpose)

        return lightning_sdk, None
    except Exception as exc:  # noqa: BLE001  (surface any import failure as text)
        return None, (
            "lightning_sdk not available; `pip install lightning-sdk` "
            f"and set LIGHTNING_USER_ID + LIGHTNING_API_KEY ({exc})"
        )


def _studio(sdk, name: str, teamspace: str):
    return sdk.Studio(name, teamspace=teamspace or None)


def _fail(error: str) -> str:
    return json.dumps({"ok": False, "error": error}, ensure_ascii=False)


@mcp.tool()
def lightning_machine_types() -> str:
    """List the Studio/Job machine (GPU) types available in the SDK."""
    sdk, err = _sdk()
    if err:
        return json.dumps(
            {"ok": False, "error": err, "known_machines": _KNOWN_MACHINES},
            ensure_ascii=False,
        )
    machines = sorted(m for m in dir(sdk.Machine) if m.isupper())
    return json.dumps(
        {"ok": True, "machine_types": machines or _KNOWN_MACHINES}, ensure_ascii=False
    )


@mcp.tool()
def lightning_studio_start(name: str, machine: str = "CPU", teamspace: str = "") -> str:
    """Start (or attach a machine to) a Lightning Studio. Bills by the second."""
    sdk, err = _sdk()
    if err:
        return _fail(err)
    try:
        studio = _studio(sdk, name, teamspace)
        studio.start(machine=getattr(sdk.Machine, machine, machine))
        return json.dumps(
            {
                "ok": True,
                "studio": name,
                "machine": machine,
                "status": str(getattr(studio, "status", "started")),
            },
            ensure_ascii=False,
        )
    except Exception as exc:  # noqa: BLE001
        return _fail(f"studio_start failed: {exc}")


@mcp.tool()
def lightning_studio_stop(name: str, teamspace: str = "") -> str:
    """Stop a running Lightning Studio (releases the billed machine)."""
    sdk, err = _sdk()
    if err:
        return _fail(err)
    try:
        _studio(sdk, name, teamspace).stop()
        return json.dumps(
            {"ok": True, "studio": name, "status": "stopped"}, ensure_ascii=False
        )
    except Exception as exc:  # noqa: BLE001
        return _fail(f"studio_stop failed: {exc}")


@mcp.tool()
def lightning_studio_run(name: str, command: str, teamspace: str = "") -> str:
    """Run a shell command inside a started Lightning Studio."""
    sdk, err = _sdk()
    if err:
        return _fail(err)
    try:
        out = _studio(sdk, name, teamspace).run(command)
        return json.dumps(
            {"ok": True, "studio": name, "output": str(out)[:8000]}, ensure_ascii=False
        )
    except Exception as exc:  # noqa: BLE001
        return _fail(f"studio_run failed: {exc}")


@mcp.tool()
def lightning_studio_switch_machine(
    name: str, machine: str, teamspace: str = "", interruptible: bool = False
) -> str:
    """Hot-swap a running Studio to a different machine (GPU) type in place.

    Keeps the Studio's filesystem; only the attached compute changes. Bills the
    new machine by the second -- stop the Studio when done.
    """
    sdk, err = _sdk()
    if err:
        return _fail(err)
    try:
        studio = _studio(sdk, name, teamspace)
        studio.switch_machine(
            getattr(sdk.Machine, machine, machine), interruptible=interruptible
        )
        return json.dumps(
            {
                "ok": True,
                "studio": name,
                "machine": machine,
                "status": str(getattr(studio, "status", "switched")),
            },
            ensure_ascii=False,
        )
    except Exception as exc:  # noqa: BLE001
        return _fail(f"studio_switch_machine failed: {exc}")


@mcp.tool()
def lightning_studio_upload_file(
    name: str, file_path: str, remote_path: str = "", teamspace: str = ""
) -> str:
    """Upload a local file into a started Studio's filesystem.

    ``remote_path`` defaults to the basename in the Studio home. The Studio must
    be started (a machine attached) for the upload to land. The SDK progress bar
    is disabled so it cannot corrupt this server's stdio JSON-RPC stream.
    """
    sdk, err = _sdk()
    if err:
        return _fail(err)
    try:
        _studio(sdk, name, teamspace).upload_file(
            file_path, remote_path or None, progress_bar=False
        )
        return json.dumps(
            {
                "ok": True,
                "studio": name,
                "file": file_path,
                "remote_path": remote_path or None,
            },
            ensure_ascii=False,
        )
    except Exception as exc:  # noqa: BLE001
        return _fail(f"studio_upload_file failed: {exc}")


@mcp.tool()
def lightning_job_submit(
    name: str, command: str, machine: str = "T4", teamspace: str = "", studio: str = ""
) -> str:
    """Submit an async Lightning Job on a machine. Bills while running."""
    sdk, err = _sdk()
    if err:
        return _fail(err)
    try:
        job = sdk.Job.run(
            name=name,
            command=command,
            machine=getattr(sdk.Machine, machine, machine),
            teamspace=teamspace or None,
            studio=studio or None,
        )
        return json.dumps(
            {
                "ok": True,
                "job": name,
                "status": str(getattr(job, "status", "submitted")),
            },
            ensure_ascii=False,
        )
    except Exception as exc:  # noqa: BLE001
        return _fail(f"job_submit failed: {exc}")


@mcp.tool()
def lightning_job_status(name: str, teamspace: str = "") -> str:
    """Get the status of a Lightning Job by name."""
    sdk, err = _sdk()
    if err:
        return _fail(err)
    try:
        job = sdk.Job(name=name, teamspace=teamspace or None)
        return json.dumps(
            {"ok": True, "job": name, "status": str(getattr(job, "status", "unknown"))},
            ensure_ascii=False,
        )
    except Exception as exc:  # noqa: BLE001
        return _fail(f"job_status failed: {exc}")


@mcp.tool()
def lightning_job_stop(name: str, teamspace: str = "") -> str:
    """Stop a running Lightning Job by name."""
    sdk, err = _sdk()
    if err:
        return _fail(err)
    try:
        job = sdk.Job(name=name, teamspace=teamspace or None)
        job.stop()
        return json.dumps(
            {"ok": True, "job": name, "status": "stopped"}, ensure_ascii=False
        )
    except Exception as exc:  # noqa: BLE001
        return _fail(f"job_stop failed: {exc}")


if __name__ == "__main__":
    mcp.run()
