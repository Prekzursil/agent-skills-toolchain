#!/usr/bin/env python3
"""Modal MCP wrapper -- a thin FastMCP server over the ``modal`` CLI.

Tool names are PRE-NAMESPACED (``modal_*``) so the cloud-hub's collision-prefix
never has to fire for this backend. The ``modal`` CLI is resolved and invoked
lazily inside each tool, so ``tools/list`` enumerates with zero credentials; a
call without ``MODAL_TOKEN_ID``/``MODAL_TOKEN_SECRET`` (or ``~/.modal.toml``)
returns a clear error instead of crashing.

GPU cost awareness: ``modal_run``/``modal_deploy`` can start billable compute.
Confirm intent before running; ``modal_app_stop`` is the off-switch.
"""
from __future__ import annotations

import json
import shutil
import subprocess

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("modal")
_TIMEOUT = 900  # seconds; modal run/deploy can build images


def _modal(*args: str, timeout: int = _TIMEOUT) -> dict:
    """Invoke the modal CLI, capturing output. Never raises."""
    exe = shutil.which("modal")
    if not exe:
        return {"ok": False, "error": "modal CLI not found; `pip install modal` "
                "and set MODAL_TOKEN_ID + MODAL_TOKEN_SECRET (or ~/.modal.toml)"}
    try:
        proc = subprocess.run([exe, *args], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": f"modal {' '.join(args)} failed: {exc}"}
    return {"ok": proc.returncode == 0, "returncode": proc.returncode,
            "stdout": (proc.stdout or "").strip()[:8000],
            "stderr": (proc.stderr or "").strip()[:2000]}


@mcp.tool()
def modal_app_list() -> str:
    """List deployed/running Modal apps (``modal app list``)."""
    return json.dumps(_modal("app", "list"), ensure_ascii=False)


@mcp.tool()
def modal_app_stop(app: str) -> str:
    """Stop a running Modal app by id or name (``modal app stop``)."""
    return json.dumps(_modal("app", "stop", app), ensure_ascii=False)


@mcp.tool()
def modal_run(target: str, detach: bool = False) -> str:
    """Run a Modal entrypoint, e.g. ``app.py::main`` (``modal run``).

    May start billable compute. Set ``detach=True`` to return without streaming.
    """
    args = ["run"] + (["--detach"] if detach else []) + [target]
    return json.dumps(_modal(*args), ensure_ascii=False)


@mcp.tool()
def modal_deploy(target: str, name: str = "") -> str:
    """Deploy a Modal app from a file/ref (``modal deploy``)."""
    args = ["deploy", target] + (["--name", name] if name else [])
    return json.dumps(_modal(*args), ensure_ascii=False)


@mcp.tool()
def modal_volume_ls(volume: str = "", path: str = "/") -> str:
    """List Modal volumes, or files inside one volume (``modal volume list|ls``)."""
    if volume:
        return json.dumps(_modal("volume", "ls", volume, path), ensure_ascii=False)
    return json.dumps(_modal("volume", "list"), ensure_ascii=False)


@mcp.tool()
def modal_secret_list() -> str:
    """List Modal secret names (``modal secret list``)."""
    return json.dumps(_modal("secret", "list"), ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
