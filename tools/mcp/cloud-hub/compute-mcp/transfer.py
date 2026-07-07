#!/usr/bin/env python3
"""File movement + remote command execution for the compute layer.

Two mechanisms, one selector:

* **scp / ssh** -- the ``ssh``/``scp`` binaries (Git-for-Windows OpenSSH, already
  on PATH) driven as subprocesses. Used to run commands (``ssh_run``) and copy
  files (``scp_copy``) against a provisioned box's public IP.
* **rclone RC** -- the local ``rclone rcd`` daemon (the same one the cloud-hub
  ``rclone`` backend fronts) over its HTTP remote-control API
  (``operations/copyfile`` for a single file, ``sync/copy`` for a tree). Used
  when either endpoint is an rclone *remote* (``name:path``).

``select_via`` picks the mechanism: an explicit ``via`` wins; otherwise a path
that looks like an rclone remote routes to rclone, else scp. No new deps:
subprocess + the stdlib HTTP seam in ``providers._http``.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Callable

RCLONE_RC_URL = "http://localhost:5572"
_SSH_OPTS = ("-o", "StrictHostKeyChecking=accept-new", "-o", "BatchMode=yes")
# A leading ``name:`` with 2+ chars is an rclone remote; a single char is a
# Windows drive letter (``C:\...``), which must NOT be treated as a remote.
_REMOTE = re.compile(r"^[A-Za-z0-9_-]{2,}:")

Runner = Callable[..., "subprocess.CompletedProcess[str]"]


@dataclass(frozen=True)
class SshTarget:
    """A resolved SSH endpoint for a provisioned box."""

    host: str
    port: int = 22
    user: str = "root"
    key: str = ""  # optional identity file

    def dest(self, remote_path: str) -> str:
        return f"{self.user}@{self.host}:{remote_path}"


def _run(argv: list[str], runner: Runner | None) -> "subprocess.CompletedProcess[str]":
    return (runner or subprocess.run)(
        argv,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )


def is_rclone_remote(path: str) -> bool:
    """True if ``path`` is an rclone ``remote:subpath`` (not a drive letter)."""
    return bool(isinstance(path, str) and _REMOTE.match(path))


def select_via(local_path: str, remote_path: str, via: str = "") -> str:
    """Choose ``'scp'`` or ``'rclone'`` (an explicit ``via`` always wins)."""
    if via in ("scp", "rclone"):
        return via
    if is_rclone_remote(local_path) or is_rclone_remote(remote_path):
        return "rclone"
    return "scp"


def ssh_run(target: SshTarget, command: str, runner: Runner | None = None) -> dict:
    """Run ``command`` on ``target`` over ssh -> stdout/stderr/exit_code."""
    argv = ["ssh", "-p", str(target.port), *_SSH_OPTS]
    if target.key:
        argv += ["-i", target.key]
    argv += [f"{target.user}@{target.host}", command]
    if not shutil.which("ssh"):
        return {"ok": False, "error": "ssh not found on PATH"}
    try:
        proc = _run(argv, runner)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "error": f"ssh failed: {exc}"}
    return {
        "ok": proc.returncode == 0,
        "stdout": (proc.stdout or "")[:8000],
        "stderr": (proc.stderr or "")[:4000],
        "exit_code": proc.returncode,
    }


def scp_copy(
    direction: str,
    target: SshTarget,
    local_path: str,
    remote_path: str,
    runner: Runner | None = None,
) -> dict:
    """Copy a file to/from ``target`` with scp (``direction`` pull|push)."""
    if not shutil.which("scp"):
        return {"ok": False, "error": "scp not found on PATH"}
    argv = ["scp", "-P", str(target.port), *_SSH_OPTS]
    if target.key:
        argv += ["-i", target.key]
    remote = target.dest(remote_path)
    argv += [remote, local_path] if direction == "pull" else [local_path, remote]
    try:
        proc = _run(argv, runner)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "error": f"scp failed: {exc}"}
    return {
        "ok": proc.returncode == 0,
        "mechanism": "scp",
        "direction": direction,
        "stderr": (proc.stderr or "")[:4000],
        "exit_code": proc.returncode,
    }


def rclone_copy(
    src: str,
    dst: str,
    rc_url: str = RCLONE_RC_URL,
    single_file: bool = True,
) -> dict:
    """Copy via the rclone RC daemon (``operations/copyfile`` or ``sync/copy``).

    A single file uses ``operations/copyfile`` (needs fs+remote split on both
    sides); a directory tree uses ``sync/copy``. ``providers._http`` is imported
    lazily so this module stays stdlib-only at import time (the provider
    adapters import ``SshTarget`` from here, which would otherwise cycle).
    """
    from providers import _http  # noqa: PLC0415  (lazy: breaks import cycle)

    if single_file:
        src_fs, src_remote = _split_fs(src)
        dst_fs, dst_remote = _split_fs(dst)
        op = "operations/copyfile"
        payload = {
            "srcFs": src_fs,
            "srcRemote": src_remote,
            "dstFs": dst_fs,
            "dstRemote": dst_remote,
        }
    else:
        op = "sync/copy"
        payload = {"srcFs": src, "dstFs": dst}
    status, body = _http.request_json(
        "POST", f"{rc_url}/{op}", {"Content-Type": "application/json"}, payload
    )
    return {
        "ok": status == 200,
        "mechanism": "rclone",
        "op": op,
        "status": status,
        "result": body,
    }


def _split_fs(path: str) -> tuple[str, str]:
    """Split an rclone path into (fs, remote): ``s3:bucket/a/b`` -> fs ``s3:``.

    Local paths become ``(dir + os-sep, basename)`` so copyfile addresses one
    file within a local directory fs.
    """
    if is_rclone_remote(path):
        remote, _, rest = path.partition(":")
        head, _, tail = rest.rpartition("/")
        return f"{remote}:{head}" if head else f"{remote}:", tail
    head, _, tail = path.replace("\\", "/").rpartition("/")
    return (head or "."), tail
